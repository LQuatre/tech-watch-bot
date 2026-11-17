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

# Les 5 piliers avec leurs flux respectifs
PILLARS = {
    "Tech Générale": {
        "emoji": "🟠",
        "color": 0xF59E0B, # Orange
        "feeds": {
            "The Verge": "https://www.theverge.com/rss/index.xml",
            "TechCrunch": "https://techcrunch.com/feed/",
            "Numerama": "https://www.numerama.com/feed/",
            "Next": "https://next.ink/feed/",
            "Korben": "https://korben.info/feed"
        }
    },
    "Cybersécurité": {
        "emoji": "🔴",
        "color": 0xEF4444, # Rouge
        "feeds": {
            "ZATAZ": "https://www.zataz.com/feed/",
            "LeMagIT Sécurité": "https://www.lemagit.fr/rss/Securite.xml",
            "InCyber": "https://incyber.org/feed/",
            "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
            "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
            "CERT-FR": "https://www.cert.ssi.gouv.fr/alerte/feed/"
        }
    },
    "Intelligence Artificielle": {
        "emoji": "🟣",
        "color": 0x8B5CF6, # Violet
        "feeds": {
            "Hacker News (IA)": "https://news.ycombinator.com/rss",
            "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/"
        }
    },
    "Infra & Cloud": {
        "emoji": "🔵",
        "color": 0x3B82F6, # Bleu
        "feeds": {
            "Cloudflare Blog": "https://blog.cloudflare.com/rss/",
            "DevOps.com": "https://devops.com/feed/"
        }
    },
    "Dev & Frameworks": {
        "emoji": "🟢",
        "color": 0x10B981, # Vert
        "feeds": {
            "PHP Foundation": "https://thephp.foundation/blog/feed.xml",
            "Laravel News": "https://feed.laravel-news.com/",
            "InfoQ": "https://feed.infoq.com/",
            "The Changelog": "https://changelog.com/feed"
        }
    }
}

def clean_html(raw_html: str) -> str:
    clean = re.sub(r'<[^>]+>', '', raw_html or '')
    return ' '.join(clean.split())

def fetch_all_pillars(max_hours: int = 24, limit_per_feed: int = 4):
    """Récupère les articles en les structurant par pilier dès la collecte."""
    structured_articles = {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

    print(f"📡 Collecte des articles des 5 piliers (dernières {max_hours}h)...")
    for pillar_name, conf in PILLARS.items():
        structured_articles[pillar_name] = []
        for source, url in conf["feeds"].items():
            try:
                feed = feedparser.parse(url)
                count = 0
                for entry in feed.entries:
                    pub = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    if not pub or pub > cutoff:
                        snippet = clean_html(getattr(entry, "summary", ""))[:220]
                        structured_articles[pillar_name].append({
                            "source": source,
                            "title": entry.title.strip(),
                            "link": entry.link.strip(),
                            "snippet": snippet
                        })
                        count += 1
                        if count >= limit_per_feed:
                            break
            except Exception as e:
                print(f"  ✗ Erreur sur {source}: {e}")
        print(f"  ✓ {pillar_name} : {len(structured_articles[pillar_name])} articles collectés")

    return structured_articles

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

def summarize_dense_digest(structured_data):
    """Fait synthétiser chaque groupe d'articles par Gemini."""
    model_to_use = discover_available_gemini_model()
    print(f"🧠 Synthèse dense et groupée avec {model_to_use}...")

    prompt = f"""Tu es un analyste senior et rédacteur en chef d'une revue informatique professionnelle.
Voici les articles du jour collectés sur 5 piliers :
{json.dumps(structured_data, ensure_ascii=False, indent=2)}

Mission :
Pour CHAQUE pilier fourni ("Tech Générale", "Cybersécurité", "Intelligence Artificielle", "Infra & Cloud", "Dev & Frameworks") :
1. Rédige un "summary" de 2 ou 3 phrases percutantes qui résume la tendance majeure et l'ambiance du jour dans ce domaine.
2. Sélectionne les 3 ou 4 articles les plus importants de la liste.
3. Pour chaque article sélectionné, fournis :
   - "title": Titre accrocheur et propre en français
   - "link": L'URL originale exacte
   - "source": Le nom du média d'origine
   - "point": 1 phrase courte résumant le fait essentiel ou l'impact

Structure impérative du JSON en sortie (UNIQUEMENT ce format, sans balises Markdown) :
{{
  "Tech Générale": {{
    "summary": "...",
    "articles": [
      {{"title": "...", "link": "...", "source": "...", "point": "..."}}
    ]
  }},
  "Cybersécurité": {{
    "summary": "...",
    "articles": [...]
  }},
  "Intelligence Artificielle": {{
    "summary": "...",
    "articles": [...]
  }},
  "Infra & Cloud": {{
    "summary": "...",
    "articles": [...]
  }},
  "Dev & Frameworks": {{
    "summary": "...",
    "articles": [...]
  }}
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_to_use}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=50)
        response.raise_for_status()
        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)
        return json.loads(raw_text)
    except Exception as e:
        print(f"⚠️ Erreur Gemini: {e}")
        # Secours : génération locale garantie équilibrée
        fallback = {}
        for pillar, arts in structured_data.items():
            fallback[pillar] = {
                "summary": f"Voici la sélection des actualités les plus récentes en {pillar}.",
                "articles": [
                    {
                        "title": a["title"],
                        "link": a["link"],
                        "source": a["source"],
                        "point": a["snippet"] or "Consultez l'article pour les détails."
                    } for a in arts[:3]
                ]
            }
        return fallback

def send_dense_digest_to_discord(groups):
    if not groups:
        return

    today = datetime.now().strftime("%d/%m/%Y")
    embeds = []

    for pillar_name, conf in PILLARS.items():
        data = groups.get(pillar_name)
        if not data:
            continue

        emoji = conf["emoji"]
        color = conf["color"]
        summary = data.get("summary", "")

        field_text = f"*{summary}*\n\n"
        for art in data.get("articles", [])[:4]:
            title = art.get("title", "Article")
            link = art.get("link", "")
            source = art.get("source", "Web")
            point = art.get("point", "")
            field_text += f"• **[{title}]({link})** `({source})`\n  ↳ {point}\n\n"

        embeds.append({
            "title": f"{emoji} {pillar_name.upper()}",
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": f"Pôle {pillar_name} • Veille Quotidienne"}
        })

    payload = {
        "username": "AI Tech Digest (Format Dense)",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png",
        "content": f"📰 **Le Grand Journal Tech & Cyber du {today}** — *Le tour d'horizon complet en 5 piliers :*",
        "embeds": embeds[:10]
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=20)
        if resp.status_code in (200, 204):
            print("✅ Grand journal dense envoyé sur Discord avec succès !")
        else:
            print(f"❌ Erreur Webhook Discord ({resp.status_code}) : {resp.text}")
    except Exception as e:
        print(f"❌ Erreur réseau : {e}")

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL or not GEMINI_API_KEY:
        print("❌ Clés d'environnement manquantes.")
        exit(1)

    structured_news = fetch_all_pillars()
    digest = summarize_dense_digest(structured_news)
    send_dense_digest_to_discord(digest)
