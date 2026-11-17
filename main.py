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

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip(' "\'\r\n\t')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip(' "\'\r\n\t')

# 19 Flux de référence couvrant les 5 grands piliers de la veille informatique
FEEDS = {
    # 🌐 Tech Générale & Écosystème (Hardware, Big Tech, Produits, Tendances)
    "The Verge": ("https://www.theverge.com/rss/index.xml", "Tech Générale", "🌐"),
    "TechCrunch": ("https://techcrunch.com/feed/", "Tech Générale", "🚀"),
    "Numerama": ("https://www.numerama.com/feed/", "Tech Générale", "📱"),
    "Next (Tech FR)": ("https://next.ink/feed/", "Tech Générale", "📰"),
    "Korben": ("https://korben.info/feed", "Tech Générale", "🐧"),

    # 🤖 Intelligence Artificielle & Modèles
    "Hacker News (IA/Tech)": ("https://news.ycombinator.com/rss", "IA & Recherche", "🤖"),

    # 🛡️ Cybersécurité & Incidents Opérationnels
    "ZATAZ (Fuites & Piratages)": ("https://www.zataz.com/feed/", "Cybersécurité", "🛡️"),
    "LeMagIT (Cyber Sécu)": ("https://www.lemagit.fr/rss/Securite.xml", "Cybersécurité", "🚨"),
    "InCyber (Menaces & OT/IoT)": ("https://incyber.org/feed/", "Cybersécurité", "🔒"),
    "The Hacker News": ("https://feeds.feedburner.com/TheHackersNews", "Cybersécurité", "⚠️"),
    "BleepingComputer": ("https://www.bleepingcomputer.com/feed/", "Cybersécurité", "🛡️"),
    "CERT-FR (Alertes Sécu)": ("https://www.cert.ssi.gouv.fr/alerte/feed/", "Cybersécurité", "⚡"),

    # ☁️ Infra & DevOps / Cloud
    "Cloudflare Blog": ("https://blog.cloudflare.com/rss/", "Infra & Cloud", "☁️"),
    "DevOps.com": ("https://devops.com/feed/", "Infra & Cloud", "⚙️"),

    # 💻 Dev, Frameworks & Nouvelles Technos
    "PHP Foundation": ("https://thephp.foundation/blog/feed.xml", "Dev & Technos", "🐘"),
    "Laravel News": ("https://feed.laravel-news.com/", "Dev & Technos", "⚡"),
    "InfoQ (Architecture)": ("https://feed.infoq.com/", "Dev & Technos", "💻"),
    "Changelog (Dev Tools)": ("https://changelog.com/feed", "Dev & Technos", "🛠️")
}

CATEGORY_COLORS = {
    "Tech Générale": 0xF59E0B,   # Orange / Ambre (Hardware, Big Tech, Écosystème)
    "IA & Recherche": 0x8B5CF6,  # Violet IA
    "Cybersécurité": 0xEF4444,   # Rouge sécurité
    "Infra & Cloud": 0x3B82F6,   # Bleu infra/cloud
    "Dev & Technos": 0x10B981    # Vert dev/code
}

def clean_html(raw_html: str) -> str:
    clean = re.sub(r'<[^>]+>', '', raw_html or '')
    return ' '.join(clean.split())

def fetch_recent_articles(max_hours: int = 24, limit_per_feed: int = 3):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

    print(f"📡 Analyse des flux (dernières {max_hours} heures)...")
    for source, (url, default_cat, emoji) in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if not pub or pub > cutoff:
                    snippet = clean_html(getattr(entry, "summary", ""))[:250]
                    articles.append({
                        "source": source,
                        "default_cat": default_cat,
                        "title": entry.title,
                        "link": entry.link,
                        "snippet": snippet
                    })
                    count += 1
                    if count >= limit_per_feed:
                        break
        except Exception as e:
            print(f"  ✗ Erreur sur {source}: {e}")

    return articles

def discover_available_gemini_model():
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
            for pref in ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-3-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
                if pref in supported:
                    return pref
            for m in supported:
                if "3.8" in m:
                    return m
            return supported[0] if supported else "gemini-3.8-flash"
    except Exception:
        pass
    return "gemini-3.8-flash"

def summarize_with_gemini(articles):
    if not articles:
        return []

    model_to_use = discover_available_gemini_model()
    print(f"🧠 Synthèse équilibrée avec {model_to_use}...")

    prompt = f"""Tu es un analyste senior en veille informatique et technologique.
Voici les articles collectés ces dernières 24h :
{json.dumps(articles, ensure_ascii=False, indent=2)}

Mission :
Sélectionne 7 à 8 actualités majeures et équilibre IMPÉRATIVEMENT les 5 piliers suivants :
1. "Tech Générale" : Au moins 1 à 2 sujets sur l'écosystème tech global, matériel, Big Tech, ou société numérique (The Verge, TechCrunch, Numerama, Korben, etc.).
2. "IA & Recherche" : Au moins 1 sujet majeur en Intelligence Artificielle (nouveaux modèles, releases, recherche).
3. "Cybersécurité" : Au moins 1 à 2 sujets sur les cyberattaques réelles, fuites de données ou failles critiques.
4. "Infra & Cloud" : Au moins 1 sujet sur le réseau, serveurs, conteneurs ou cloud.
5. "Dev & Technos" : Au moins 1 sujet sur le dev, les frameworks (PHP, JS, Rust, etc.) et outils open-source.

Pour chaque actualité, produis un objet JSON :
- "category": L'une de ces 5 catégories exactes : "Tech Générale", "IA & Recherche", "Cybersécurité", "Infra & Cloud", ou "Dev & Technos"
- "title": Titre accrocheur et précis en français
- "summary": 2 puces concises (commençant par "- ") résumant les faits clés
- "link": L'URL originale de l'article fournie dans la liste
- "source": Le nom de la source originale
- "emoji": Emoji adapté (ex: 🌐, 🤖, 🛡️, ☁️, 💻)

Format de réponse requis : UNIQUEMENT un tableau JSON valide."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_to_use}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=35)
        response.raise_for_status()
        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)
        return json.loads(raw_text)
    except Exception as e:
        print(f"⚠️ Erreur Gemini: {e}")
        return [{
            "category": art.get("default_cat", "Tech Générale"),
            "title": art["title"],
            "summary": art["snippet"] or "Détails dans l'article.",
            "link": art["link"],
            "source": art["source"],
            "emoji": "📰"
        } for art in articles[:7]]

def send_to_discord(curated_news):
    if not curated_news:
        return

    today = datetime.now().strftime("%d/%m/%Y")
    embeds = []

    for item in curated_news[:10]:
        cat = item.get("category", "Tech Générale")
        color = CATEGORY_COLORS.get(cat, 0xF59E0B)

        embeds.append({
            "title": f"{item.get('emoji', '📌')} [{cat}] {item.get('title')}",
            "url": item.get("link"),
            "description": item.get("summary", ""),
            "footer": {"text": f"Source : {item.get('source')} • {cat}"},
            "color": color
        })

    payload = {
        "username": "AI Tech Watcher",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "content": f"⚡ **Veille Tech Complète du {today}** — *Le digest quotidien en 5 piliers :*",
        "embeds": embeds
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            print("✅ Digest complet envoyé sur Discord !")
        else:
            print(f"❌ Erreur Webhook ({resp.status_code}) : {resp.text}")
    except Exception as e:
        print(f"❌ Erreur envoi : {e}")

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL or not GEMINI_API_KEY:
        print("❌ Clés d'environnement manquantes.")
        exit(1)

    news = fetch_recent_articles()
    curated = summarize_with_gemini(news)
    send_to_discord(curated)
