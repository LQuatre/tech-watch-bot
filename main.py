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

# Sources RSS spécialisées par domaine
FEEDS = {
    # 🛡️ Cybersécurité
    "The Hacker News (Cyber)": "https://feeds.feedburner.com/TheHackersNews",
    "BleepingComputer (Cyber)": "https://www.bleepingcomputer.com/feed/",
    "CERT-FR (Alertes Sécu)": "https://www.cert.ssi.gouv.fr/alerte/feed/",

    # ☁️ Infra & DevOps / Cloud
    "Cloudflare Blog (Infra)": "https://blog.cloudflare.com/rss/",
    "DevOps.com (Infra)": "https://devops.com/feed/",

    # 💻 Dev, Frameworks & Nouvelles Technos
    "InfoQ (Dev & Arch)": "https://feed.infoq.com/",
    "Changelog (Dev)": "https://changelog.com/feed",
    "Hacker News": "https://news.ycombinator.com/rss",

    # 🌐 Généraliste Tech & Médias FR
    "Korben": "https://korben.info/feed",
    "Numerama": "https://www.numerama.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml"
}

CATEGORY_COLORS = {
    "Cybersécurité": 0xEF4444,   # Rouge sécurité
    "Infra & Cloud": 0x3B82F6,   # Bleu infra/cloud
    "Dev & Technos": 0x10B981,   # Vert dev/code
    "IA & Écosystème": 0x8B5CF6  # Violet IA
}

def clean_html(raw_html: str) -> str:
    """Retire les balises HTML des résumés."""
    clean = re.sub(r'<[^>]+>', '', raw_html or '')
    return ' '.join(clean.split())

def fetch_recent_articles(max_hours: int = 24, limit_per_feed: int = 3):
    """Récupère les articles récents des dernières 24 heures."""
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

    print(f"📡 Analyse des flux spécialisés (dernières {max_hours} heures)...")

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                if not published or published > cutoff:
                    snippet = clean_html(getattr(entry, "summary", ""))[:250]
                    articles.append({
                        "source": source,
                        "title": entry.title,
                        "link": entry.link,
                        "snippet": snippet
                    })
                    count += 1
                    if count >= limit_per_feed:
                        break
            print(f"  ✓ {source} : {count} article(s)")
        except Exception as e:
            print(f"  ✗ Erreur sur {source}: {e}")

    return articles

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
            for pref in ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-3-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
                if pref in supported:
                    return pref
            for m in supported:
                if "3.8-flash" in m or "3.8" in m:
                    return m
            return supported[0] if supported else "gemini-3.8-flash"
        else:
            print(f"  ⚠️ Erreur détection modèles ({resp.status_code}) : {resp.text}")
    except Exception as e:
        print(f"  ⚠️ Exception de détection : {e}")

    return "gemini-3.8-flash"

def summarize_with_gemini(articles):
    """Sélectionne et équilibre la veille quotidienne entre Cyber, Infra, Dev et IA."""
    if not articles:
        return []

    model_to_use = discover_available_gemini_model()
    print(f"🧠 Analyse et catégorisation avec {model_to_use}...")

    prompt = f"""Tu es un analyste senior en veille informatique.
Voici les articles tech collectés ces dernières 24h à partir de flux spécialisés :
{json.dumps(articles, ensure_ascii=False, indent=2)}

Mission :
Sélectionne les 5 ou 6 actualités les plus percutantes et équilibre impérativement les thématiques suivantes :
1. Au moins 1 sujet majeur en Cybersécurité (faille 0-day, alerte critique, incident cyber, malware).
2. Au moins 1 sujet majeur en Infra / DevOps / Cloud (conteneurs, réseau, cloud, Linux, architecture système).
3. Au moins 1 sujet majeur en Dev / Frameworks / Technos (mise à jour d'un langage/outil, nouvel outil dev).
4. Le reste sur l'IA ou les actualités tech globales.

Pour chaque actualité sélectionnée, produis un objet JSON :
- "category": L'une de ces 4 catégories exactes : "Cybersécurité", "Infra & Cloud", "Dev & Technos", ou "IA & Écosystème"
- "title": Titre accrocheur et précis en français
- "summary": 2 ou 3 puces concises (commençant par "- ") résumant les faits clés et les implications
- "link": L'URL originale de l'article fournie dans la liste
- "source": Le nom de la source originale
- "emoji": Emoji adapté (ex: 🔒, 🛡️, ☁️, ⚙️, 💻, 🤖)

IMPORTANT : Tu dois répondre UNIQUEMENT avec un tableau JSON valide au format :
[
  {{
    "category": "Cybersécurité",
    "title": "...",
    "summary": "- Point 1\\n- Point 2",
    "link": "...",
    "source": "...",
    "emoji": "🛡️"
  }}
]
Ne mets aucun texte avant ou après le tableau JSON."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_to_use}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code != 200:
            print(f"❌ Erreur Gemini ({response.status_code}) : {response.text}")
            raise ValueError(f"HTTP {response.status_code}")

        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)

        return json.loads(raw_text)
    except Exception as e:
        print(f"⚠️ Bascule vers les articles bruts suite à erreur: {e}")
        return [{
            "category": "Dev & Technos",
            "title": art["title"],
            "summary": art["snippet"] or "Pas de description disponible.",
            "link": art["link"],
            "source": art["source"],
            "emoji": "📰"
        } for art in articles[:5]]

def send_to_discord(curated_news):
    """Envoie les actualités sur Discord avec un code couleur par catégorie."""
    if not curated_news:
        print("ℹ️ Aucune actualité à poster.")
        return

    today = datetime.now().strftime("%d/%m/%Y")
    embeds = []

    for item in curated_news[:10]:
        cat = item.get("category", "Dev & Technos")
        color = CATEGORY_COLORS.get(cat, 0x38BDF8)

        embeds.append({
            "title": f"{item.get('emoji', '📌')} [{cat}] {item.get('title', 'Actualité')}",
            "url": item.get("link"),
            "description": item.get("summary", ""),
            "footer": {"text": f"Source : {item.get('source', 'Web')} • {cat}"},
            "color": color
        })

    payload = {
        "username": "Tech Watcher (Cyber • Infra • Dev • IA)",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "content": f"⚡ **Veille Tech & Sécu du {today}** — *Le digest quotidien Cyber, Infra, Dev & IA :*",
        "embeds": embeds
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            print("✅ Veille spécialisée envoyée sur Discord avec succès !")
        else:
            print(f"❌ Erreur Webhook Discord ({resp.status_code}) : {resp.text}")
    except Exception as e:
        print(f"❌ Erreur réseau lors de l'envoi : {e}")

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("❌ Erreur : DISCORD_WEBHOOK_URL requis.")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ Erreur : GEMINI_API_KEY requis.")
        exit(1)

    news = fetch_recent_articles()
    print(f"-> Total : {len(news)} articles collectés.")

    curated = summarize_with_gemini(news)
    print(f"-> Total : {len(curated)} actus sélectionnées.")

    send_to_discord(curated)
