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

# Priorité à 3.6 pour aujourd'hui (quota 3.8 plein à 21/20), puis 3.7 et 3.8
CANDIDATE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash"
]

# Les 5 piliers avec sources vérifiées et actives
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
            "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
            "Hacker News": "https://news.ycombinator.com/rss"
        }
    },
    "Infra & Cloud": {
        "emoji": "🔵",
        "color": 0x3B82F6, # Bleu
        "feeds": {
            "The New Stack": "https://thenewstack.io/feed/",
            "Silicon.fr": "https://www.silicon.fr/feed",
            "Cloudflare Blog": "https://blog.cloudflare.com/rss/",
            "CNCF Blog": "https://www.cncf.io/feed/"
        }
    },
    "Dev & Frameworks": {
        "emoji": "🟢",
        "color": 0x10B981, # Vert
        "feeds": {
            "GitHub Blog": "https://github.blog/feed/",
            "The Changelog": "https://changelog.com/feed",
            "Smashing Mag (Web/JS)": "https://www.smashingmagazine.com/feed/",
            "InfoQ (Architecture)": "https://feed.infoq.com/",
            "Rust Blog": "https://blog.rust-lang.org/feed.xml",
            "Laravel News (PHP)": "https://laravel-news.com/feed"
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
    return ' '.join(clean.split())

def fetch_all_pillars(max_hours: int = 24):
    """Collecte les articles par pilier avec garantie de contenu non-vide."""
    structured = {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

    print(f"📡 Collecte des articles des 5 piliers...")
    for pillar, conf in PILLARS.items():
        structured[pillar] = []
        for source, url in conf["feeds"].items():
            try:
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.content)
                recent_from_feed = []

                for entry in feed.entries[:4]:
                    pub = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    snippet = clean_html(getattr(entry, "summary", ""))[:130]

                    if snippet.lower() in ("comments", "comments..."):
                        snippet = ""

                    if title and link:
                        item = {
                            "source": source,
                            "title": title[:95],
                            "link": link,
                            "snippet": snippet
                        }
                        if not pub or pub > cutoff:
                            recent_from_feed.append(item)
                        elif len(recent_from_feed) == 0:
                            recent_from_feed.append(item)
                        # Max 1 article par source pour garantir une vraie diversité de sujets
                        if len(recent_from_feed) >= 1:
                            break

                structured[pillar].extend(recent_from_feed[:1])
            except Exception as e:
                print(f"  ✗ Erreur {source}: {e}")

        print(f"  ✓ {pillar} : {len(structured[pillar])} articles prêts")

    return structured

def call_gemini_for_summaries(structured_data):
    """Demande à Gemini de générer uniquement les synthèses éditoriales des 5 pôles (ultra rapide, <2s)."""
    # Pour que la requête soit instantanée et ne sature jamais (moins de 200 tokens)
    headlines = {
        pillar: [a["title"] for a in arts[:3]]
        for pillar, arts in structured_data.items()
    }

    prompt = f"""Tu es le rédacteur en chef d'une revue tech et cybersécurité de premier plan.
Voici les principaux titres de l'actualité du jour classés par pôle :
{json.dumps(headlines, ensure_ascii=False, indent=2)}

Mission :
Rédige pour CHAQUE pôle une phrase percutante et analytique (maximum 2 phrases) qui synthétise l'ambiance, la tendance forte et l'enjeu du jour.

Format de réponse requis : UNIQUEMENT un objet JSON associant chaque pôle à son texte d'analyse :
{{
  "Tech Générale": "...",
  "Cybersécurité": "...",
  "Intelligence Artificielle": "...",
  "Infra & Cloud": "...",
  "Dev & Frameworks": "..."
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
        for attempt in range(2):
            try:
                print(f"Génération de l'édito avec {model} (tentative {attempt+1})...")
                response = requests.post(url, json=payload, timeout=20)
                if response.status_code == 200:
                    raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if raw_text.startswith("```"):
                        raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
                        raw_text = re.sub(r'\s*```$', '', raw_text)
                    print(f"✓ Synthèses éditoriales rédigées avec succès par {model} !")
                    return json.loads(raw_text)
                elif response.status_code in (503, 429):
                    print(f"  ↳ Modèle {model} temporairement occupé ({response.status_code}), pause de 1s...")
                    time.sleep(1.5)
                else:
                    print(f"  ↳ Erreur {response.status_code}: {response.text[:150]}")
                    break
            except Exception as e:
                print(f"  ↳ Exception {model}: {e}")
                time.sleep(1)

    print("⚠️ Repli sur les synthèses de secours contextuelles.")
    return DEFAULT_SUMMARIES

def send_dense_digest_to_discord(structured_data, editorial_summaries):
    """Formate et envoie le digest sur Discord en 2 parties équilibrées."""
    today = datetime.now().strftime("%d/%m/%Y")
    all_embeds = []

    for pillar_name, conf in PILLARS.items():
        arts = structured_data.get(pillar_name, [])
        if not arts:
            continue

        emoji = conf["emoji"]
        color = conf["color"]
        summary = editorial_summaries.get(pillar_name, DEFAULT_SUMMARIES.get(pillar_name, ""))

        field_text = f"*{summary}*\n\n"
        for art in arts[:3]:
            title = art.get("title", "Actualité")
            link = art.get("link", "")
            source = art.get("source", "Web")
            point = art.get("snippet", "")
            if point:
                field_text += f"• **[{title}]({link})** `({source})`\n  ↳ {point}...\n\n"
            else:
                field_text += f"• **[{title}]({link})** `({source})`\n\n"

        all_embeds.append({
            "title": f"{emoji} {pillar_name.upper()}",
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": f"Pôle {pillar_name} • Veille Quotidienne"}
        })

    # Envoi en 2 messages consécutifs pour respecter la limite absolue des 6000 caractères
    parts = [
        ("Partie 1/2 — Tech Générale • Cyber • IA", all_embeds[:3]),
        ("Partie 2/2 — Infra & Cloud • Dev & Frameworks", all_embeds[3:])
    ]

    for part_label, embeds_chunk in parts:
        if not embeds_chunk:
            continue

        payload = {
            "username": "AI Tech Digest",
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
    summaries = call_gemini_for_summaries(structured_news)
    send_dense_digest_to_discord(structured_news, summaries)
