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

CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash"
]

# Les 5 piliers enrichis avec des sources actives et diversifiées
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
            "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
            "Ars Technica AI": "https://arstechnica.com/ai/feed/",
            "MarkTechPost": "https://www.marktechpost.com/feed/",
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
            "InfoQ": "https://feed.infoq.com/",
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
    clean = ' '.join(clean.split())
    # Nettoie les phrases incomplètes coupées abruptement
    return clean

def fetch_all_pillars(max_hours: int = 24):
    """Collecte 4 articles distincts par pilier avec du vrai texte substantiel."""
    structured = {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

    print(f"📡 Collecte approfondie des articles des 5 piliers...")
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

                    # Filtrer les snippets vides ou parasites
                    if snippet.lower() in ("comments", "comments...", ""):
                        snippet = ""

                    # Découpage propre à la fin d'une phrase complète (jusqu'à 240 caractères)
                    if len(snippet) > 240:
                        # Coupe proprement au dernier point ou espace
                        cut = snippet[:240]
                        last_period = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
                        if last_period > 100:
                            snippet = cut[:last_period+1]
                        else:
                            last_space = cut.rfind(' ')
                            snippet = (cut[:last_space] if last_space > 0 else cut) + "..."

                    if title and link:
                        item = {
                            "source": source,
                            "title": title,
                            "link": link,
                            "snippet": snippet
                        }
                        # On prend 1 article marquant par source pour garantir une vraie diversité
                        structured[pillar].append(item)
                        break
            except Exception as e:
                print(f"  ✗ Erreur {source}: {e}")

        # On garde jusqu'à 4 articles distincts par pôle
        structured[pillar] = structured[pillar][:4]
        print(f"  ✓ {pillar} : {len(structured[pillar])} articles complets prêts")

    return structured

def call_gemini_for_summaries(structured_data):
    """Demande à Gemini de rédiger les analyses de tendances éditoriales pour chaque pôle."""
    headlines = {
        pillar: [a["title"] for a in arts[:4]]
        for pillar, arts in structured_data.items()
    }

    prompt = f"""Tu es le rédacteur en chef d'une grande revue tech et cybersécurité de référence.
Voici les titres majeurs de l'actualité d'aujourd'hui, classés en 5 pôles :
{json.dumps(headlines, ensure_ascii=False, indent=2)}

Mission :
Rédige pour CHAQUE pôle une analyse de tendance en 2 phrases complètes, précises et journalistiques :
- Explique clairement ce qui se passe aujourd'hui dans ce domaine.
- Mets en avant l'impact ou l'enjeu sous-jacent pour les professionnels et passionnés.

Format de réponse requis : UNIQUEMENT un objet JSON valide :
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
        try:
            print(f"Génération de l'analyse avec {model}...")
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw_text.startswith("```"):
                    raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
                    raw_text = re.sub(r'\s*```$', '', raw_text)
                print(f"✓ Synthèses rédigées avec succès par {model} !")
                return json.loads(raw_text)
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

    print("⚠️ Repli sur les synthèses de secours contextuelles.")
    return DEFAULT_SUMMARIES

def send_dense_digest_to_discord(structured_data, editorial_summaries):
    """Formate et expédie le grand journal sur Discord avec des explications complètes."""
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
        for art in arts:
            title = art.get("title", "Actualité")
            link = art.get("link", "")
            source = art.get("source", "Web")
            point = art.get("snippet", "")
            if point:
                field_text += f"• **[{title}]({link})** `({source})`\n  ↳ {point}\n\n"
            else:
                field_text += f"• **[{title}]({link})** `({source})`\n\n"

        all_embeds.append({
            "title": f"{emoji} {pillar_name.upper()}",
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": f"Pôle {pillar_name} • Veille Quotidienne Approfondie"}
        })

    # Envoi en 2 parties bien fournies (environ 3000 caractères chacune, limite Discord = 6000)
    parts = [
        ("Partie 1/2 — Tech Générale • Cybersécurité • IA", all_embeds[:3]),
        ("Partie 2/2 — Infra & Cloud • Dev & Frameworks", all_embeds[3:])
    ]

    for part_label, embeds_chunk in parts:
        if not embeds_chunk:
            continue

        payload = {
            "username": "Le Grand Journal Tech",
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
