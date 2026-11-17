import os
import json
import re
from datetime import datetime, timezone, timedelta
import feedparser
import requests

# Chargement automatique du fichier .env en local s'il existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Sources RSS : sélection de médias tech de référence (Français et Internationaux)
FEEDS = {
    "Korben": "https://korben.info/feed",
    "Numerama": "https://www.numerama.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Hacker News": "https://news.ycombinator.com/rss",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "TechCrunch": "https://techcrunch.com/feed/"
}

def clean_html(raw_html: str) -> str:
    """Retire les balises HTML basiques des extraits RSS."""
    clean = re.sub(r'<[^>]+>', '', raw_html or '')
    return ' '.join(clean.split())

def fetch_recent_articles(max_hours: int = 24, limit_per_feed: int = 4):
    """Récupère les articles récents des dernières 24 heures."""
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

    print(f"📡 Analyse des flux RSS (dernières {max_hours} heures)...")

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
            print(f"  ✓ {source} : {count} article(s) trouvé(s)")
        except Exception as e:
            print(f"  ✗ Erreur sur {source}: {e}")

    return articles

def summarize_with_gemini(articles):
    """Sélectionne et résume les 5 actus phares via l'API Gemini."""
    if not articles:
        return []

    print("🧠 Analyse et synthèse par Gemini Flash...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""Tu es un analyste senior spécialisé en veille informatique et tech.
Voici une liste d'articles d'actualité collectés aujourd'hui :
{json.dumps(articles, ensure_ascii=False, indent=2)}

Mission :
1. Sélectionne les 5 actualités les plus percutantes et importantes (évite les doublons et les rumeurs mineures).
2. Pour chaque actualité, traduis/synthétise en français sous forme d'un objet JSON contenant :
   - "title": Un titre accrocheur et concis en français.
   - "summary": 2 ou 3 puces concises (commençant par "- ") résumant les faits clés et les implications.
   - "link": L'URL originale de l'article fournie dans la liste.
   - "source": Le nom de la source d'origine.
   - "emoji": Un emoji contextuel (ex: 🤖 pour IA, 🔒 pour sécu/cyber, 💻 pour dev/code, 📱 pour hardware/mobile).

IMPORTANT : Tu dois répondre UNIQUEMENT avec un tableau JSON valide au format :
[
  {{
    "title": "...",
    "summary": "- Point 1\\n- Point 2",
    "link": "...",
    "source": "...",
    "emoji": "🤖"
  }}
]
Ne mets aucun texte avant ou après le tableau JSON."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        data = json.loads(raw_text)
        return data
    except Exception as e:
        print(f"⚠️ Erreur lors de l'appel ou du parsing Gemini: {e}")
        # En cas d'échec de l'IA, on bascule sur les 5 premiers articles bruts
        return [{
            "title": art["title"],
            "summary": art["snippet"] or "Pas de description disponible.",
            "link": art["link"],
            "source": art["source"],
            "emoji": "📰"
        } for art in articles[:5]]

def send_to_discord(curated_news):
    """Envoie les actualités formatées sur le Webhook Discord."""
    if not curated_news:
        print("ℹ️ Aucune actualité à poster.")
        return

    today = datetime.now().strftime("%d/%m/%Y")
    embeds = []

    for item in curated_news[:10]:
        embeds.append({
            "title": f"{item.get('emoji', '📌')} {item.get('title', 'Actualité')}",
            "url": item.get("link"),
            "description": item.get("summary", ""),
            "footer": {"text": f"Source : {item.get('source', 'Web')}"},
            "color": 0x38BDF8  # Teinte bleu ciel / tech
        })

    payload = {
        "username": "AI Tech Watcher",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "content": f"🚀 **Veille Tech du {today}** — *Le top 5 des actus sélectionnées et synthétisées par IA :*",
        "embeds": embeds
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            print("✅ Actualités envoyées sur Discord avec succès !")
        else:
            print(f"❌ Erreur Webhook Discord ({resp.status_code}) : {resp.text}")
    except Exception as e:
        print(f"❌ Erreur réseau lors de l'envoi vers Discord : {e}")

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("❌ Erreur : DISCORD_WEBHOOK_URL n'est pas configuré.")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ Erreur : GEMINI_API_KEY n'est pas configuré.")
        exit(1)

    news = fetch_recent_articles()
    print(f"-> Total : {len(news)} articles collectés.")

    curated = summarize_with_gemini(news)
    print(f"-> Total : {len(curated)} actus sélectionnées.")

    send_to_discord(curated)
