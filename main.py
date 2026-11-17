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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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
            "PHP.net": "https://www.php.net/news.rss",
            "Laravel News": "https://laravel-news.com/feed",
            "InfoQ": "https://feed.infoq.com/",
            "The Changelog": "https://changelog.com/feed"
        }
    }
}

DEFAULT_SUMMARIES = {
    "Tech Générale": "Actualité dominée par les annonces hardware, les nouveaux mouvements de régulation numérique en Europe et les évolutions des plateformes grand public.",
    "Cybersécurité": "Vigilance accrue sur les attaques ciblant les chaînes logistiques (supply chain) et les infrastructures industrielles/IoT, accompagnée de nouveaux bulletins critiques du CERT-FR.",
    "Intelligence Artificielle": "Course à l'efficacité énergétique, percée des moteurs d'inférence locale ultra-rapides et intégration d'agents autonomes dans les environnements de production.",
    "Infra & Cloud": "Modernisation des architectures Edge computing (WASM), optimisation des coûts cloud et résilience des clusters Kubernetes.",
    "Dev & Frameworks": "Évolutions des runtimes modernes, adoption du Pipe operator sur PHP, accélération du tooling en Rust et nouvelles versions des frameworks web."
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
                # Utilisation d'un User-Agent réaliste pour contourner les protections 403
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.content)
                recent_from_feed = []

                for entry in feed.entries[:5]:
                    pub = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    snippet = clean_html(getattr(entry, "summary", ""))[:180]

                    # Ne pas garder les descriptions inutiles genre "Comments"
                    if snippet.lower() in ("comments", "comments..."):
                        snippet = ""

                    if title and link:
                        item = {
                            "source": source,
                            "title": title,
                            "link": link,
                            "snippet": snippet
                        }
                        if not pub or pub > cutoff:
                            recent_from_feed.append(item)
                        elif len(recent_from_feed) == 0 and len(structured[pillar]) < 2:
                            # Si le flux n'a rien posté aujourd'hui, on prend la dernière publication pour éviter un pilier vide
                            recent_from_feed.append(item)

                structured[pillar].extend(recent_from_feed[:3])
            except Exception as e:
                print(f"  ✗ Erreur {source}: {e}")

        # Sécurité : si un pilier a moins de 3 articles, on garde ce qu'on a
        print(f"  ✓ {pillar} : {len(structured[pillar])} articles prêts")

    return structured

def discover_available_gemini_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
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
    """Demande à Gemini de créer une synthèse par pilier et sélectionner les meilleurs articles."""
    model_to_use = discover_available_gemini_model()
    print(f"🧠 Synthèse par Gemini avec {model_to_use}...")

    # On prépare un échantillon concis pour éviter tout dépassement de token ou timeout
    compact_data = {}
    for p, arts in structured_data.items():
        compact_data[p] = [
            {"title": a["title"][:90], "source": a["source"], "link": a["link"], "snippet": a["snippet"][:120]}
            for a in arts[:4]
        ]

    prompt = f"""Tu es le rédacteur en chef d'une grande revue tech et cybersécurité.
Voici les articles du jour classés en 5 piliers :
{json.dumps(compact_data, ensure_ascii=False, indent=2)}

Mission :
Pour CHAQUE pilier ("Tech Générale", "Cybersécurité", "Intelligence Artificielle", "Infra & Cloud", "Dev & Frameworks") :
1. "summary": Rédige une phrase ou deux percutantes qui résume la tendance du jour dans ce domaine.
2. "articles": Sélectionne jusqu'à 3 ou 4 articles avec :
   - "title": Titre propre en français
   - "link": L'URL originale exacte
   - "source": Le nom de la source
   - "point": 1 phrase courte d'explication des faits

Réponds UNIQUEMENT avec un objet JSON valide au format :
{{
  "Tech Générale": {{"summary": "...", "articles": [{{"title": "...", "link": "...", "source": "...", "point": "..."}}]}},
  "Cybersécurité": {{"summary": "...", "articles": [...]}},
  "Intelligence Artificielle": {{"summary": "...", "articles": [...]}},
  "Infra & Cloud": {{"summary": "...", "articles": [...]}},
  "Dev & Frameworks": {{"summary": "...", "articles": [...]}}
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
        response = requests.post(url, json=payload, timeout=40)
        if response.status_code != 200:
            print(f"⚠️ Erreur Gemini ({response.status_code}) : {response.text}")
            raise ValueError(f"HTTP {response.status_code}")

        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)
        return json.loads(raw_text)
    except Exception as e:
        print(f"⚠️ Bascule vers le fallback intelligent: {e}")
        fallback = {}
        for pillar, arts in structured_data.items():
            fallback[pillar] = {
                "summary": DEFAULT_SUMMARIES.get(pillar, f"Actualités marquantes en {pillar}."),
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
            title = art.get("title", "Actualité")
            link = art.get("link", "")
            source = art.get("source", "Web")
            point = art.get("point", "")
            field_text += f"• **[{title}]({link})** `({source})`\n  ↳ {point}\n\n"

        embeds.append({
            "title": f"{emoji} {pillar_name.upper()}",
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": f"Pôle {pillar_name} • Veille Quotidienne Dense"}
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
    if not DISCORD_WEBHOOK_URL:
        print("❌ Clé DISCORD_WEBHOOK_URL manquante.")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ Clé GEMINI_API_KEY manquante.")
        exit(1)

    structured_news = fetch_all_pillars()
    digest = summarize_dense_digest(structured_news)
    send_dense_digest_to_discord(digest)
