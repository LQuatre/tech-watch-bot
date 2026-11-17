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

# Modèles en cascade : priorité absolue à 3.8, avec repli immédiat sur 3.7 / 3.6 / 3.1 en cas de pic de charge
CANDIDATE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash"
]

MONTHS_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]

FEEDS = {
    # 🛡️ Cybersécurité
    "ZATAZ": "https://www.zataz.com/feed/",
    "InCyber": "https://incyber.org/feed/",
    "Undernews": "https://www.undernews.fr/feed",
    "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "CERT-FR": "https://www.cert.ssi.gouv.fr/alerte/feed/",

    # ☁️ Infra & Cloud
    "The New Stack": "https://thenewstack.io/feed/",
    "Silicon.fr": "https://www.silicon.fr/feed",
    "Cloudflare Blog": "https://blog.cloudflare.com/rss/",

    # 💻 Dev & Technos
    "GitHub Blog": "https://github.blog/feed/",
    "The Changelog": "https://changelog.com/feed",
    "Smashing Mag (Web/JS)": "https://www.smashingmagazine.com/feed/",
    "Rust Blog": "https://blog.rust-lang.org/feed.xml",
    "InfoQ": "https://feed.infoq.com/",
    "Laravel News (PHP)": "https://laravel-news.com/feed",

    # 🌐 Tech générale
    "Next": "https://next.ink/feed/",
    "Korben": "https://korben.info/feed",
    "Numerama": "https://www.numerama.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml"
}

def fetch_top_stories_monthly():
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
                stories.append({
                    "source": "Hacker News (Top)",
                    "title": title[:90],
                    "link": url
                })
            print(f"  ✓ {len(hits)} histoires majeures récupérées de Hacker News.")
    except Exception as e:
        print(f"  ✗ Erreur Hacker News : {e}")

    print("📰 2. Récupération des flux spécialisés...")
    for source, url in FEEDS.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            feed = feedparser.parse(r.content)
            count = 0
            for entry in feed.entries[:4]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if title and link:
                    stories.append({
                        "source": source,
                        "title": title[:90],
                        "link": link
                    })
                    count += 1
            print(f"  ✓ {source} : {count} articles")
        except Exception as e:
            print(f"  ✗ Erreur {source} : {e}")

    return stories

def call_gemini_with_fallback(prompt: str):
    for model in CANDIDATE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        for attempt in range(2):
            try:
                print(f"Essai mensuel avec {model} (tentative {attempt+1})...")
                resp = requests.post(url, json=payload, timeout=45)
                if resp.status_code == 200:
                    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if raw.startswith("```"):
                        raw = re.sub(r'^```(json)?\s*', '', raw)
                        raw = re.sub(r'\s*```$', '', raw)
                    return json.loads(raw)
                elif resp.status_code in (503, 429):
                    print(f"  ↳ Modèle {model} surchargé ({resp.status_code}), pause...")
                    time.sleep(2)
                elif resp.status_code == 404:
                    print(f"  ↳ Modèle {model} 404, essai suivant...")
                    break
            except Exception as e:
                print(f"  ↳ Exception {e}")
                time.sleep(1)
    return None

def generate_monthly_digest(stories):
    if not stories:
        return None

    current_month_name = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    prompt = f"""Tu es le rédacteur en chef d'une revue tech et cybersécurité.
Nous réalisons le GRAND BILAN MENSUEL ({current_month_name} {current_year}).
Voici les sujets marquants :
{json.dumps(stories[:50], ensure_ascii=False, indent=2)}

Rédige une rétrospective synthétique en français.
Structure JSON exacte :
{{
  "intro": "2 phrases résumant la grande tendance du mois.",
  "categories": [
    {{
      "name": "🌐 Tech Générale & Écosystème",
      "color_hex": "F59E0B",
      "highlights": [{{"title": "...", "summary": "- Point 1\\n- Point 2", "link": "..."}}]
    }},
    {{
      "name": "🛡️ Cybersécurité & Failles Critiques",
      "color_hex": "EF4444",
      "highlights": [{{"title": "...", "summary": "- Point 1\\n- Point 2", "link": "..."}}]
    }},
    {{
      "name": "☁️ Infrastructure & Cloud",
      "color_hex": "3B82F6",
      "highlights": [{{"title": "...", "summary": "- Point 1\\n- Point 2", "link": "..."}}]
    }},
    {{
      "name": "💻 Dev & Frameworks",
      "color_hex": "10B981",
      "highlights": [{{"title": "...", "summary": "- Point 1\\n- Point 2", "link": "..."}}]
    }},
    {{
      "name": "🤖 Intelligence Artificielle",
      "color_hex": "8B5CF6",
      "highlights": [{{"title": "...", "summary": "- Point 1\\n- Point 2", "link": "..."}}]
    }}
  ]
}}"""

    return call_gemini_with_fallback(prompt)

def send_monthly_to_discord(digest):
    if not digest:
        return

    current_month = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    embeds = [{
        "title": f"📚 LE GRAND RÉCAP TECH & CYBER — {current_month.upper()} {current_year}",
        "description": f"**Ce qui a marqué l'industrie ce mois-ci :**\n{digest.get('intro', '')}",
        "color": 0xF59E0B,
        "footer": {"text": "Édition Mensuelle • Tech Watcher"}
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
        for h in cat.get("highlights", [])[:2]:
            field_text += f"• **[{h.get('title')}]({h.get('link')})**\n{h.get('summary')}\n\n"

        if field_text:
            hex_color = cat.get("color_hex", "3B82F6")
            color_int = color_map.get(hex_color, 0x3B82F6)
            embeds.append({
                "title": cat.get("name"),
                "description": field_text.strip()[:1000],
                "color": color_int
            })

    # Découpage en 2 messages si plus de 3 embeds pour ne pas dépasser 6000 chars
    chunks = [embeds[:3], embeds[3:]]
    for idx, chunk in enumerate(chunks, 1):
        if not chunk:
            continue
        payload = {
            "username": "AI Monthly Tech & Cyber",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3281/3281323.png",
            "content": f"🎆 **Rétrospective Mensuelle ({current_month} {current_year})** — Partie {idx}/2 :",
            "embeds": chunk
        }
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=20)
            if resp.status_code in (200, 204):
                print(f"✅ Rétrospective partie {idx} postée sur Discord !")
            else:
                print(f"❌ Erreur Webhook ({resp.status_code}) : {resp.text}")
            time.sleep(1)
        except Exception as e:
            print(f"❌ Erreur réseau: {e}")

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL or not GEMINI_API_KEY:
        print("❌ Clés d'environnement manquantes.")
        exit(1)

    stories = fetch_top_stories_monthly()
    digest = generate_monthly_digest(stories)
    send_monthly_to_discord(digest)
