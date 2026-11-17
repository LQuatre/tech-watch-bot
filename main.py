import os
import json
import re
import time
from datetime import datetime, timezone, timedelta
import feedparser
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip(' "\'\r\n\t')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip(' "\'\r\n\t')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Modèles en cascade calibrés sur les quotas de ton compte
CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash"
]

# Les 5 piliers complets avec le gratin des médias français et internationaux de référence
PILLARS = {
    "Tech Générale": {
        "emoji": "🟠",
        "color": 0xF59E0B, # Orange
        "feeds": {
            "Le Monde Informatique": "https://www.lemondeinformatique.fr/flux-rss/thematique/toutes-les-actualites/rss.xml",
            "Next": "https://next.ink/feed/",
            "Numerama": "https://www.numerama.com/feed/",
            "Korben": "https://korben.info/feed",
            "The Verge": "https://www.theverge.com/rss/index.xml",
            "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index"
        }
    },
    "Cybersécurité": {
        "emoji": "🔴",
        "color": 0xEF4444, # Rouge
        "feeds": {
            "ZATAZ": "https://www.zataz.com/feed/",
            "InCyber": "https://incyber.org/feed/",
            "Undernews": "https://www.undernews.fr/feed",
            "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
            "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
            "CERT-FR": "https://www.cert.ssi.gouv.fr/alerte/feed/"
        }
    },
    "Intelligence Artificielle": {
        "emoji": "🟣",
        "color": 0x8B5CF6, # Violet
        "feeds": {
            "ActuIA": "https://www.actuia.com/feed/",
            "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
            "Ars Technica AI": "https://arstechnica.com/ai/feed/",
            "MarkTechPost": "https://www.marktechpost.com/feed/",
            "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/"
        }
    },
    "Infra & Cloud": {
        "emoji": "🔵",
        "color": 0x3B82F6, # Bleu
        "feeds": {
            "Silicon.fr": "https://www.silicon.fr/feed",
            "The New Stack": "https://thenewstack.io/feed/",
            "Cloudflare Blog": "https://blog.cloudflare.com/rss/",
            "CNCF Blog": "https://www.cncf.io/feed/"
        }
    },
    "Dev & Frameworks": {
        "emoji": "🟢",
        "color": 0x10B981, # Vert
        "feeds": {
            "Journal du Hacker": "https://www.journalduhacker.net/rss",
            "GitHub Blog": "https://github.blog/feed/",
            "The Changelog": "https://changelog.com/feed",
            "Smashing Mag (Web/JS)": "https://www.smashingmagazine.com/feed/",
            "InfoQ": "https://feed.infoq.com/",
            "Rust Blog": "https://blog.rust-lang.org/feed.xml",
            "Laravel News": "https://laravel-news.com/feed"
        }
    }
}

DEFAULT_SUMMARIES = {
    "Tech Générale": "Actualité dominée par les annonces hardware, les nouveaux mouvements de régulation numérique en Europe et les évolutions des plateformes grand public.",
    "Cybersécurité": "Vigilance accrue sur les attaques ciblant les chaînes logistiques (supply chain) et les infrastructures industrielles/IoT, accompagnée de nouveaux bulletins critiques du CERT-FR.",
    "Intelligence Artificielle": "Course à l'efficacité énergétique, percée des moteurs d'inférence locale ultra-rapides et intégration d'agents autonomes dans les environnements de production.",
    "Infra & Cloud": "Modernisation des architectures Edge computing (WASM), optimisation des coûts cloud et résilience des clusters Kubernetes.",
    "Dev & Frameworks": "Actualités de l'écosystème dev : outillage open-source, nouveautés sur les runtimes web et frontend, évolutions du compilateur Rust et frameworks modernes."
}

def clean_html(raw_html: str) -> str:
    clean = re.sub(r'<[^>]+>', '', raw_html or '')
    clean = ' '.join(clean.split())
    return clean

def fetch_all_pillars(max_hours: int = 24):
    """Collecte jusqu'à 4 articles distincts par pilier avec extraits propres."""
    structured = {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

    print(f"📡 Collecte des articles sur 27 sources de référence...")
    for pillar, conf in PILLARS.items():
        structured[pillar] = []
        for source, url in conf["feeds"].items():
            try:
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.content)

                for entry in feed.entries[:4]:
                    pub = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    snippet = clean_html(raw_summary)

                    if snippet.lower() in ("comments", "comments...", ""):
                        snippet = ""

                    if len(snippet) > 220:
                        cut = snippet[:220]
                        last_space = cut.rfind(' ')
                        snippet = (cut[:last_space] if last_space > 0 else cut) + "..."

                    if title and link:
                        structured[pillar].append({
                            "source": source,
                            "title": title,
                            "link": link,
                            "snippet": snippet
                        })
                        # 1 article par source pour maximiser la variété
                        break
            except Exception as e:
                print(f"  ✗ Erreur {source}: {e}")

        # On garde jusqu'à 4 articles distincts par pôle
        structured[pillar] = structured[pillar][:4]
        print(f"  ✓ {pillar} : {len(structured[pillar])} articles prêts")

    return structured

def translate_and_summarize_with_gemini(structured_data):
    """Demande à Gemini de traduire en français et d'expliquer chaque article clairement."""
    compact_data = {}
    for p, arts in structured_data.items():
        compact_data[p] = [
            {"title": a["title"][:90], "source": a["source"], "snippet": a["snippet"][:120]}
            for a in arts
        ]

    prompt = f"""Tu es le rédacteur en chef d'une prestigieuse revue tech francophone.
Voici la sélection des articles du jour classés en 5 pôles (certains titres ou extraits sont en anglais, d'autres en français) :
{json.dumps(compact_data, ensure_ascii=False, indent=2)}

Mission :
Produis un résumé exhaustif où TOUT EST EN FRANÇAIS IMPECCABLE, riche et informatif.
Pour CHAQUE pôle :
1. "summary": Rédige une analyse éditoriale de 2 phrases sur la tendance forte du jour dans ce secteur.
2. "articles": Pour chaque article fourni dans ce pôle, traduis et développe :
   - "title_fr": Titre accrocheur et fidèle traduit en français
   - "point_fr": Une explication complète de 2 phrases en français expliquant clairement les faits et l'impact (pas de phrase coupée, pas d'anglais)

Format impératif : UNIQUEMENT un objet JSON valide suivant cette structure exacte :
{{
  "Tech Générale": {{
    "summary": "...",
    "articles": [{{"title_fr": "...", "point_fr": "..."}}]
  }},
  "Cybersécurité": {{ "summary": "...", "articles": [...] }},
  "Intelligence Artificielle": {{ "summary": "...", "articles": [...] }},
  "Infra & Cloud": {{ "summary": "...", "articles": [...] }},
  "Dev & Frameworks": {{ "summary": "...", "articles": [...] }}
}}"""

    for model in CANDIDATE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        try:
            print(f"Traduction et synthèse avec {model}...")
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw_text.startswith("```"):
                    raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
                    raw_text = re.sub(r'\s*```$', '', raw_text)
                data = json.loads(raw_text)
                print(f"✓ Traduction et synthèse réussies avec {model} !")
                return data
            elif response.status_code == 429:
                print(f"  ↳ Quota atteint sur {model} (429), bascule immédiate...")
                continue
            elif response.status_code == 503:
                print(f"  ↳ Modèle {model} occupé (503), bascule immédiate...")
                continue
            else:
                print(f"  ↳ Erreur {response.status_code}: {response.text[:150]}")
        except Exception as e:
            print(f"  ↳ Exception {model}: {e}")

    print("⚠️ Repli sur les données brutes.")
    return None

def send_dense_digest_to_discord(structured_data, enriched_content):
    """Envoie le digest sur Discord 100% traduit en français et ultra-complet."""
    today = datetime.now().strftime("%d/%m/%Y")
    all_embeds = []

    for pillar_name, conf in PILLARS.items():
        arts = structured_data.get(pillar_name, [])
        if not arts:
            continue

        emoji = conf["emoji"]
        color = conf["color"]

        # Récupération de la synthèse IA si disponible
        pillar_ai = enriched_content.get(pillar_name, {}) if enriched_content else {}
        summary = pillar_ai.get("summary") or DEFAULT_SUMMARIES.get(pillar_name, "")
        articles_ai = pillar_ai.get("articles", [])

        field_text = f"*{summary}*\n\n"

        for idx, art in enumerate(arts):
            # Titre et explication traduits par l'IA si dispo, sinon bruts
            ai_item = articles_ai[idx] if idx < len(articles_ai) else {}
            title = ai_item.get("title_fr") or art.get("title", "Actualité")
            point = ai_item.get("point_fr") or art.get("snippet", "")
            link = art.get("link", "")
            source = art.get("source", "Web")

            if point:
                field_text += f"• **[{title}]({link})** `({source})`\n  ↳ {point}\n\n"
            else:
                field_text += f"• **[{title}]({link})** `({source})`\n\n"

        all_embeds.append({
            "title": f"{emoji} {pillar_name.upper()}",
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": f"Pôle {pillar_name} • Édition Complète en Français"}
        })

    # Envoi en 2 parties bien fournies
    parts = [
        ("Partie 1/2 — Tech Générale • Cybersécurité • IA", all_embeds[:3]),
        ("Partie 2/2 — Infra & Cloud • Dev & Frameworks", all_embeds[3:])
    ]

    for part_label, embeds_chunk in parts:
        if not embeds_chunk:
            continue

        payload = {
            "username": "Le Grand Journal Tech & Cyber",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
            "content": f"📰 **Le Grand Journal Tech & Cyber du {today}** ({part_label}) :",
            "embeds": embeds_chunk
        }

        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if resp.status_code in (200, 204):
                print(f"✅ {part_label} envoyée avec succès sur Discord !")
            else:
                print(f"❌ Erreur Webhook ({resp.status_code}) : {resp.text}")
            time.sleep(1)
        except Exception as e:
            print(f"❌ Erreur réseau lors de l'envoi : {e}")

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("❌ Clé DISCORD_WEBHOOK_URL manquante.")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ Clé GEMINI_API_KEY manquante.")
        exit(1)

    structured_news = fetch_all_pillars()
    enriched = translate_and_summarize_with_gemini(structured_news)
    send_dense_digest_to_discord(structured_news, enriched)
