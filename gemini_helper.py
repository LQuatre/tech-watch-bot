import json
import re
import time
import requests

# Mots-clés des modèles non adaptés à la génération JSON texte pure
EXCLUDED_MODEL_TERMS = (
    "tts", "image", "banana", "lyria", "embedding", "live", "audio",
    "transcribe", "robotics", "computer-use", "omni", "imagen", "veo",
    "aqa", "learnlm", "deep-research", "gemma"
)

# Modèles connus pour être à 0/0 RPD sur le tier gratuit AI Studio
ZERO_FREE_QUOTA_TERMS = (
    "2.5-pro", "3.1-pro", "1.5-pro", "4-argon", "4-carbon", "2.0-flash", "2-flash"
)

# Ordre de préférence basé sur les quotas gratuits réels AI Studio :
# 1 & 2 : Flash-Lite (500 requêtes/jour chacun -> préserve le quota 20 RPD de 3.8-flash !)
# 3+    : Flash standards (20 requêtes/jour chacun en secours)
PRIORITY_PATTERNS = [
    "3.5-flash-lite",
    "3.5 flash lite",
    "3.1-flash-lite",
    "3.1 flash lite",
    "3.6-flash",
    "3.6 flash",
    "3.8-flash",
    "3.8 flash",
    "4-hydrogen",
    "4 hydrogen",
    "3-flash",
    "3 flash",
    "2.5-flash-lite",
    "2.5 flash lite",
    "2.5-flash",
    "2.5 flash",
]

_CACHED_MODELS = None


def discover_verified_models(api_key: str) -> list[str]:
    """
    Interroge directement GET /v1beta/models de Google pour récupérer les VRAIS
    identifiants exacts actifs sur cette clé API (zéro hallucination de nom de modèle).
    Cet appel GET ne consomme aucun token ni quota RPD.
    """
    global _CACHED_MODELS
    if _CACHED_MODELS is not None:
        return _CACHED_MODELS

    url = f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=100&key={api_key}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            err = resp.text[:200]
            print(f"⚠️ Impossible de lister /v1beta/models (HTTP {resp.status_code}): {err}")
            _CACHED_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash"]
            return _CACHED_MODELS

        raw_models = resp.json().get("models", [])
        candidates = []

        for m in raw_models:
            name = m.get("name", "")  # ex: "models/gemini-3.5-flash-lite-preview"
            if not name.startswith("models/"):
                continue
            model_id = name.split("models/", 1)[1]
            display_name = m.get("displayName", "")
            methods = m.get("supportedGenerationMethods", [])

            if "generateContent" not in methods:
                continue

            combined = f"{model_id} {display_name}".lower()
            if not model_id.lower().startswith("gemini-"):
                continue
            if any(term in combined for term in EXCLUDED_MODEL_TERMS):
                continue
            if any(term in combined for term in ZERO_FREE_QUOTA_TERMS):
                continue

            # Calcul du rang de priorité
            rank = 999
            for idx, pat in enumerate(PRIORITY_PATTERNS):
                if pat in combined:
                    rank = idx
                    break

            candidates.append((rank, model_id, display_name))

        candidates.sort(key=lambda x: (x[0], x[1]))
        verified_ids = []
        seen = set()
        for rank, mid, dname in candidates:
            if mid not in seen:
                seen.add(mid)
                verified_ids.append(mid)

        if verified_ids:
            print(f"🔎 Modèles réels vérifiés via l'API Google ({len(verified_ids)} trouvés) :")
            for mid in verified_ids[:6]:
                print(f"   • {mid}")
            _CACHED_MODELS = verified_ids
            return _CACHED_MODELS

    except Exception as e:
        print(f"⚠️ Exception lors de la découverte des modèles : {e}")

    _CACHED_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash"]
    return _CACHED_MODELS


def _extract_json(raw_text: str):
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Tentative d'extraction du premier bloc {...}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def generate_json_with_verified_gemini(api_key: str, prompt: str, label: str = "génération") -> dict | None:
    """
    Appelle Gemini en utilisant uniquement les identifiants vérifiés par l'API Google,
    en privilégiant les modèles Flash-Lite (500 RPD) pour ne pas toucher au quota 20 RPD.
    """
    models = discover_verified_models(api_key)

    for model_id in models[:6]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json",
            },
        }

        try:
            t0 = time.time()
            print(f"🤖 [{label}] Appel sur '{model_id}'...")
            resp = requests.post(url, json=payload, timeout=55)
            elapsed = time.time() - t0

            if resp.status_code == 200:
                body = resp.json()
                candidates = body.get("candidates", [])
                if not candidates:
                    print(f"  ↳ Réponse vide sur {model_id}, essai suivant...")
                    continue
                raw_text = candidates[0]["content"]["parts"][0]["text"]
                parsed = _extract_json(raw_text)
                usage = body.get("usageMetadata", {})
                tot_tok = usage.get("totalTokenCount", "?")
                print(f"  ✅ Succès avec '{model_id}' en {elapsed:.1f}s ({tot_tok} tokens)")
                return parsed

            # Lecture du message d'erreur exact renvoyé par Google
            try:
                err_msg = resp.json().get("error", {}).get("message", resp.text[:160])
            except Exception:
                err_msg = resp.text[:160]

            print(f"  ↳ HTTP {resp.status_code} sur '{model_id}' ({elapsed:.1f}s) : {err_msg[:140]}")
            # Pas de boucle inutile sur le même modèle : bascule immédiate sur le suivant
            continue

        except Exception as e:
            print(f"  ↳ Exception sur '{model_id}' : {e}")
            continue

    print(f"⚠️ Échec sur tous les modèles vérifiés pour [{label}].")
    return None
