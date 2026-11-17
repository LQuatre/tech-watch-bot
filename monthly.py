import os
import json
import time
from datetime import datetime, timezone, timedelta
import feedparser
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

MONTHS_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]

FEEDS = {
    "Korben": "https://korben.info/feed",
    "Numerama": "https://www.numerama.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "TechCrunch": "https://techcrunch.com/feed/"
}

def fetch_top_stories_monthly():
    """Récupère les meilleures actualités des 30 derniers jours (Hacker News Algolia + Flux RSS)."""
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

    print("📰 2. Récupération des flux d'actualité tech...")
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
                    if count >= 8:
                        break
            print(f"  ✓ {source} : {count} articles récupérés.")
        except Exception as e:
            print(f"  ✗ Erreur {source} : {e}")

    return stories

def generate_monthly_digest(stories):
    """Demande à Gemini de créer une grande rétrospective mensuelle catégorisée."""
    if not stories:
        return None

    print("🧠 3. Analyse approfondie et rétrospective par Gemini Flash...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    current_month_name = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    prompt = f"""Tu es le rédacteur en chef d'une revue technologique de référence.
Nous réalisons le GRAND BILAN TECH MENSUEL ({current_month_name} {current_year}).

Voici la sélection des sujets les plus marquants des 30 derniers jours :
{json.dumps(stories, ensure_ascii=False, indent=2)}

Mission :
Rédige une rétrospective claire, passionnante et synthétique en français.
Structure impérativement la réponse en un objet JSON avec cette structure exacte :

{{
  "intro": "Un paragraphe d'introduction résumant la grande tendance ou le fait marquant qui a dominé ce mois.",
  "categories": [
    {{
      "name": "🤖 Intelligence Artificielle & Recherche",
      "color_hex": "8B5CF6",
      "highlights": [
        {{
          "title": "Nom de l'actu/modèle",
          "summary": "- Qu'est-ce qui s'est passé\\n- Pourquoi c'est une avancée majeure",
          "link": "URL d'origine"
        }}
      ]
    }},
    {{
      "name": "💻 Dev, Open Source & Infrastructures",
      "color_hex": "3B82F6",
      "highlights": [ ... ]
    }},
    {{
      "name": "🔒 Cybersécurité & Confidentialité",
      "color_hex": "EF4444",
      "highlights": [ ... ]
    }},
    {{
      "name": "🌐 Business Tech, Hardware & Écosystème",
      "color_hex": "10B981",
      "highlights": [ ... ]
    }}
  ]
}}

Consignes :
- 1 à 2 'highlights' maximum par catégorie (uniquement les événements réellement majeurs).
- Les liens doivent impérativement provenir de la liste fournie.
- Les résumés doivent être analytiques et percutants en 2 bullet points courts.
- Réponds UNIQUEMENT avec un JSON valide, sans balises de code Markdown."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=45)
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return json.loads(raw)
    except Exception as e:
        print(f"❌ Erreur lors de la génération mensuelle Gemini: {e}")
        return None

def send_monthly_to_discord(digest):
    """Formate et expédie le grand récapitulatif sur Discord en embeds thématiques."""
    if not digest:
        print("Aucun digest à envoyer.")
        return

    current_month = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    # Embed 1 : En-tête et vue globale
    embeds = [{
        "title": f"📚 LE GRAND RÉCAP TECH MENSUEL — {current_month.upper()} {current_year}",
        "description": f"**Ce qui a marqué l'industrie ce mois-ci :**\n{digest.get('intro', '')}",
        "color": 0xF59E0B, # Ambre doré
        "footer": {"text": "Édition Mensuelle • Tech Watcher"}
    }]

    # Embeds suivants : Chaque catégorie thématique
    color_map = {
        "8B5CF6": 0x8B5CF6,
        "3B82F6": 0x3B82F6,
        "EF4444": 0xEF4444,
        "10B981": 0x10B981
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
        "username": "AI Monthly Digest",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3281/3281323.png",
        "content": f"🎆 **Rétrospective Tech Mensuelle ({current_month} {current_year})** disponible !",
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
    if not DISCORD_WEBHOOK_URL or not GEMINI_API_KEY:
        print("❌ Clés d'environnement manquantes.")
        exit(1)

    stories = fetch_top_stories_monthly()
    print(f"-> {len(stories)} histoires collectées sur les 30 derniers jours.")

    digest = generate_monthly_digest(stories)
    send_monthly_to_discord(digest)
