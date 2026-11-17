import os
import json
import re
from datetime import datetime, timezone, timedelta
import feedparser
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Nettoyage des clés (retire les espaces ou guillemets accidentels)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip(' "\'\r\n\t')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip(' "\'\r\n\t')

MONTHS_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]

# Sources RSS spécialisées par domaine pour le récapitulatif mensuel
FEEDS = {
    # 🛡️ Cybersécurité & Incidents Opérationnels
    "ZATAZ (Cyber & Fuites)": "https://www.zataz.com/feed/",
    "LeMagIT (Cyber Sécu)": "https://www.lemagit.fr/rss/Securite.xml",
    "InCyber (Menaces & OT)": "https://incyber.org/feed/",
    "The Hacker News (Cyber)": "https://feeds.feedburner.com/TheHackersNews",
    "BleepingComputer (Cyber)": "https://www.bleepingcomputer.com/feed/",
    "CERT-FR (Alertes Sécu)": "https://www.cert.ssi.gouv.fr/alerte/feed/",

    # ☁️ Infra & Cloud
    "Cloudflare Blog (Infra)": "https://blog.cloudflare.com/rss/",
    "DevOps.com (Infra)": "https://devops.com/feed/",

    # 💻 Dev & Technos
    "InfoQ (Dev & Arch)": "https://feed.infoq.com/",
    "Changelog (Dev)": "https://changelog.com/feed",
    "PHP Foundation (PHP)": "https://thephp.foundation/blog/feed.xml",
    "Laravel News (PHP)": "https://feed.laravel-news.com/",

    # 🌐 Tech généraliste
    "Next (Tech FR)": "https://next.ink/feed/",
    "Korben": "https://korben.info/feed",
    "Numerama": "https://www.numerama.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml"
}

def fetch_top_stories_monthly():
    """Récupère les meilleures actualités des 30 derniers jours (Hacker News Algolia + Flux Spécialisés)."""
    stories = []
    now = datetime.now(timezone.utc)
    cutoff_ts = int((now - timedelta(days=30)).timestamp())

    print("📊 1. Récupération des sujets les plus votés du mois sur Hacker News...")
    hn_url = f"https://hn.algolia.com/api/v1/search?tags=story&numericFilters=created_at_i>{cutoff_ts}&hitsPerPage=35"
    try:
        resp = requests.get(hn_url, timeout=20)
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            for h in hits:
                title = h.get("title")
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                points = h.get("points", 0)
                stories.append({
                    "source": "Hacker News (Top)",
                    "title": title,
                    "link": url,
                    "points": points
                })
            print(f"  ✓ {len(hits)} histoires majeures récupérées de Hacker News.")
    except Exception as e:
        print(f"  ✗ Erreur Hacker News : {e}")

    print("📰 2. Récupération des flux spécialisés (Cyber, Infra, Dev)...")
    cutoff_dt = now - timedelta(days=30)
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if not pub or pub > cutoff_dt:
                    stories.append({
                        "source": source,
                        "title": entry.title,
                        "link": entry.link,
                        "points": 0
                    })
                    count += 1
                    if count >= 6:
                        break
            print(f"  ✓ {source} : {count} articles récupérés.")
        except Exception as e:
            print(f"  ✗ Erreur {source} : {e}")

    return stories

def discover_available_gemini_model():
    """Interroge l'API pour lister les modèles réels autorisés et choisir le plus récent."""
    print("🔍 Détection du modèle Gemini...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            supported = [
                m["name"].replace("models/", "")
                for m in models
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            print(f"  ✓ Modèles disponibles : {', '.join(supported)}")
            # Préférer le nouveau modèle standard gemini-3.8-flash recommandé par l'API
            for pref in ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-3-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
                if pref in supported:
                    return pref
            # Sinon le premier contenant "3.8" ou "flash"
            for m in supported:
                if "3.8-flash" in m or "3.8" in m:
                    return m
            return supported[0] if supported else "gemini-3.8-flash"
        else:
            print(f"  ⚠️ Erreur détection modèles ({resp.status_code}) : {resp.text}")
    except Exception as e:
        print(f"  ⚠️ Exception de détection : {e}")

    return "gemini-3.8-flash"

def generate_monthly_digest(stories):
    """Demande à Gemini de créer une grande rétrospective mensuelle catégorisée avec Cyber, Infra, Dev et IA."""
    if not stories:
        return None

    model_to_use = discover_available_gemini_model()
    print(f"🧠 3. Analyse approfondie et rétrospective avec {model_to_use}...")

    current_month_name = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    prompt = f"""Tu es le rédacteur en chef d'une revue technologique et cybersécurité de référence.
Nous réalisons le GRAND BILAN TECH MENSUEL ({current_month_name} {current_year}).

Voici la sélection des sujets des 30 derniers jours (Hacker News, CERT-FR, BleepingComputer, Cloudflare, Dev, InfoQ...) :
{json.dumps(stories, ensure_ascii=False, indent=2)}

Mission :
Rédige une rétrospective claire, passionnante et synthétique en français.
Accorde une attention particulière aux cyberattaques et sabotages opérationnels réels, aux incidents d'infrastructure, aux sorties de frameworks/langages (PHP, Rust, etc.) et aux avancées IA.
Structure impérativement la réponse en un objet JSON avec cette structure exacte :

{{
  "intro": "Un paragraphe d'introduction résumant les grandes tendances qui ont dominé ce mois.",
  "categories": [
    {{
      "name": "🌐 Tech Générale, Hardware & Écosystème",
      "color_hex": "F59E0B",
      "highlights": [
        {{
          "title": "Nom de l'actu grand public / Big Tech",
          "summary": "- Faits clés\\n- Enjeux pour l'industrie",
          "link": "URL d'origine"
        }}
      ]
    }},
    {{
      "name": "🛡️ Cybersécurité & Failles Critiques",
      "color_hex": "EF4444",
      "highlights": [
        {{
          "title": "Nom de l'incident / faille / alerte",
          "summary": "- Faits clés\\n- Risques et mesures recommandées",
          "link": "URL d'origine"
        }}
      ]
    }},
    {{
      "name": "☁️ Infrastructure, Cloud & DevOps",
      "color_hex": "3B82F6",
      "highlights": [
        {{
          "title": "Nom du projet ou évolution infra",
          "summary": "- Ce qui a changé\\n- Impact pour les sysadmins / devops",
          "link": "URL d'origine"
        }}
      ]
    }},
    {{
      "name": "💻 Dev, Frameworks & Nouvelles Technos",
      "color_hex": "10B981",
      "highlights": [
        {{
          "title": "Nom de la techno / release",
          "summary": "- Nouveautés phares\\n- Ce que ça apporte aux développeurs",
          "link": "URL d'origine"
        }}
      ]
    }},
    {{
      "name": "🤖 Intelligence Artificielle & Recherche",
      "color_hex": "8B5CF6",
      "highlights": [
        {{
          "title": "Nom du modèle ou avancée",
          "summary": "- Découverte ou sortie majeure\\n- Enjeux",
          "link": "URL d'origine"
        }}
      ]
    }}
  ]
}}

Consignes :
- 1 à 2 'highlights' maximum par catégorie (uniquement les événements réellement majeurs).
- Les liens doivent impérativement provenir de la liste fournie.
- Les résumés doivent être percutants et clairs en 2 bullet points courts.
- Réponds UNIQUEMENT avec un JSON valide, sans balises Markdown."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_to_use}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code != 200:
            print(f"❌ Réponse Gemini ({resp.status_code}) : {resp.text}")
            return None

        raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)

        return json.loads(raw_text)
    except Exception as e:
        print(f"❌ Erreur lors du parsing JSON Gemini : {e}")
        return None

def send_monthly_to_discord(digest):
    """Formate et expédie le grand récapitulatif sur Discord en embeds thématiques."""
    if not digest:
        print("Aucun digest à envoyer.")
        return

    current_month = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    embeds = [{
        "title": f"📚 LE GRAND RÉCAP TECH & CYBER — {current_month.upper()} {current_year}",
        "description": f"**Ce qui a marqué l'industrie ce mois-ci :**\n{digest.get('intro', '')}",
        "color": 0xF59E0B,
        "footer": {"text": "Édition Mensuelle • Tech Watcher (Cyber • Infra • Dev • IA)"}
    }]

    color_map = {
        "F59E0B": 0xF59E0B,
        "EF4444": 0xEF4444,
        "3B82F6": 0x3B82F6,
        "10B981": 0x10B981,
        "8B5CF6": 0x8B5CF6
    }

    for cat in digest.get("categories", []):
        field_text = ""
        for h in cat.get("highlights", []):
            field_text += f"**[{h.get('title')}]({h.get('link')})**\n{h.get('summary')}\n\n"

        if field_text:
            hex_color = cat.get("color_hex", "3B82F6")
            color_int = color_map.get(hex_color, 0x3B82F6)
            embeds.append({
                "title": cat.get("name"),
                "description": field_text.strip(),
                "color": color_int
            })

    payload = {
        "username": "AI Monthly Tech & Cyber",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3281/3281323.png",
        "content": f"🎆 **Rétrospective Mensuelle ({current_month} {current_year})** disponible !",
        "embeds": embeds[:10]
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=20)
        if resp.status_code in (200, 204):
            print("✅ Grand récapitulatif mensuel posté sur Discord !")
        else:
            print(f"❌ Erreur Webhook Discord ({resp.status_code}) : {resp.text}")
    except Exception as e:
        print(f"❌ Erreur réseau Discord : {e}")

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL manquant.")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY manquant.")
        exit(1)

    stories = fetch_top_stories_monthly()
    print(f"-> {len(stories)} histoires collectées.")

    digest = generate_monthly_digest(stories)
    send_monthly_to_discord(digest)
