import os
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import feedparser
import requests

from gemini_helper import generate_json_with_verified_gemini

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

MONTHS_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]

FEEDS = {
    # 🛡️ Cybersécurité
    "Le Monde Informatique (Sec)": "https://www.lemondeinformatique.fr/flux-rss/thematique/securite/rss.xml",
    "ZATAZ": "https://www.zataz.com/feed/",
    "InCyber": "https://incyber.org/feed/",
    "Undernews": "https://www.undernews.fr/feed",
    "CERT-FR": "https://www.cert.ssi.gouv.fr/alerte/feed/",
    "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "The Register (Sec)": "https://www.theregister.com/security/headlines.atom",
    "SANS ISC": "https://isc.sans.edu/rssfeed.xml",

    # 🤖 Intelligence Artificielle
    "Le Monde Informatique (IA)": "https://www.lemondeinformatique.fr/flux-rss/thematique/intelligence-artificielle/rss.xml",
    "ActuIA": "https://www.actuia.com/feed/",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Simon Willison (AI)": "https://simonwillison.net/atom/everything/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",
    "MarkTechPost": "https://www.marktechpost.com/feed/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",

    # ☁️ Infra & Cloud
    "Le Monde Informatique (Cloud)": "https://www.lemondeinformatique.fr/flux-rss/thematique/cloud-computing/rss.xml",
    "Silicon.fr": "https://www.silicon.fr/feed",
    "The New Stack": "https://thenewstack.io/feed/",
    "Cloudflare Blog": "https://blog.cloudflare.com/rss/",
    "CNCF Blog": "https://www.cncf.io/feed/",
    "AWS News": "https://aws.amazon.com/blogs/aws/feed/",
    "Netflix Tech": "https://netflixtechblog.com/feed",

    # 💻 Dev & Technos
    "Le Monde Informatique (Dev)": "https://www.lemondeinformatique.fr/flux-rss/thematique/developpement/rss.xml",
    "Journal du Hacker": "https://www.journalduhacker.net/rss",
    "LinuxFR": "https://linuxfr.org/journaux.atom",
    "Phoronix": "https://www.phoronix.com/phoronix-rss.php",
    "GitHub Blog": "https://github.blog/feed/",
    "The Changelog": "https://changelog.com/feed",
    "Smashing Mag (Web/JS)": "https://www.smashingmagazine.com/feed/",
    "InfoQ": "https://feed.infoq.com/",
    "Rust Blog": "https://blog.rust-lang.org/feed.xml",
    "Laravel News": "https://laravel-news.com/feed",

    # 🌐 Tech générale
    "Le Monde Informatique": "https://www.lemondeinformatique.fr/flux-rss/thematique/toutes-les-actualites/rss.xml",
    "Génération-NT": "https://www.generation-nt.com/export/rss.xml",
    "Next": "https://next.ink/feed/",
    "Korben": "https://korben.info/feed",
    "Numerama": "https://www.numerama.com/feed/",
    "Frandroid": "https://www.frandroid.com/feed",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",

    # 🎮 Esport & Mercato Roster
    "Dexerto LoL": "https://www.dexerto.com/league-of-legends/feed/",
    "Dexerto Rocket League": "https://www.dexerto.com/rocket-league/feed/",
    "Dexerto Call of Duty": "https://www.dexerto.com/call-of-duty/feed/",
    "L'Équipe Esport": "https://dwh.lequipe.fr/api/edito/rss?path=/Esport/",
    "Dexerto Esport": "https://www.dexerto.com/esports/feed/",
    "Upcomer": "https://upcomer.com/feed",
    "Fragster": "https://www.fragster.com/feed/"
}


def _fetch_single_feed(item):
    source, url = item
    out = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=7)
        if r.status_code == 200:
            feed = feedparser.parse(r.content)
            for entry in feed.entries[:3]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if title and link:
                    out.append({"source": source, "title": title[:90], "link": link})
    except Exception:
        pass
    return out


def fetch_top_stories_monthly():
    stories = []
    now = datetime.now(timezone.utc)
    cutoff_ts = int((now - timedelta(days=30)).timestamp())

    print("📊 1. Récupération des sujets les plus votés du mois sur Hacker News...")
    hn_url = f"https://hn.algolia.com/api/v1/search?tags=story&numericFilters=created_at_i>{cutoff_ts}&hitsPerPage=30"
    try:
        resp = requests.get(hn_url, timeout=15)
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            for h in hits:
                title = h.get("title")
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                if title:
                    stories.append({"source": "Hacker News (Top)", "title": title[:90], "link": url})
            print(f"  ✓ {len(hits)} histoires majeures récupérées de Hacker News.")
    except Exception as e:
        print(f"  ✗ Erreur Hacker News : {e}")

    print(f"📰 2. Téléchargement parallèle de {len(FEEDS)} flux spécialisés...")
    with ThreadPoolExecutor(max_workers=12) as pool:
        for items in pool.map(_fetch_single_feed, FEEDS.items()):
            stories.extend(items)
    print(f"  ✓ Total articles collectés : {len(stories)}")
    return stories


def generate_monthly_digest(stories):
    if not stories:
        return None

    current_month_name = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    prompt = f"""Tu es le rédacteur en chef d'une prestigieuse revue tech, cyber et esport francophone.
Nous réalisons le GRAND BILAN MENSUEL ({current_month_name} {current_year}).
Voici une sélection des sujets marquants des 30 derniers jours :
{json.dumps(stories[:55], ensure_ascii=False)}

Rédige une rétrospective mensuelle 100% EN FRANÇAIS IMPECCABLE au format JSON strict :
{{
  "intro": "3 phrases percutantes résumant les grandes tendances du mois.",
  "top_event": {{
    "title": "L'événement numéro 1 du mois",
    "summary": "2 phrases en français expliquant pourquoi cet événement a marqué l'industrie."
  }},
  "categories": [
    {{"name": "🟠 Tech Générale & Écosystème", "color_hex": "F59E0B", "highlights": [{{"title": "Titre FR", "summary": "- Point 1\\n- Point 2", "link": "..."}}]}},
    {{"name": "🔴 Cybersécurité & Vulnérabilités Majeures", "color_hex": "EF4444", "highlights": [{{"title": "Titre FR", "summary": "- Point 1\\n- Point 2", "link": "..."}}]}},
    {{"name": "🟣 Intelligence Artificielle & Modèles", "color_hex": "8B5CF6", "highlights": [{{"title": "Titre FR", "summary": "- Point 1\\n- Point 2", "link": "..."}}]}},
    {{"name": "🔵 Infrastructure & Cloud", "color_hex": "3B82F6", "highlights": [{{"title": "Titre FR", "summary": "- Point 1\\n- Point 2", "link": "..."}}]}},
    {{"name": "🟢 Dev, Langages & Open Source", "color_hex": "10B981", "highlights": [{{"title": "Titre FR", "summary": "- Point 1\\n- Point 2", "link": "..."}}]}},
    {{"name": "🎮 Esport, Mercato & Leaks Roster", "color_hex": "EC4899", "highlights": [{{"title": "Titre FR", "summary": "- Point 1\\n- Point 2", "link": "..."}}]}}
  ]
}}"""

    return generate_json_with_verified_gemini(GEMINI_API_KEY, prompt, label="Bilan Mensuel")


def send_monthly_to_discord(digest):
    if not digest:
        return

    current_month = MONTHS_FR[datetime.now().month]
    current_year = datetime.now().year

    top_event = digest.get("top_event", {})
    top_event_text = ""
    if top_event and top_event.get("title"):
        top_event_text = f"\n\n🏆 **L'Événement Majeur du Mois :** {top_event.get('title')}\n↳ {top_event.get('summary', '')}"

    intro_embed = {
        "title": f"📚 LE GRAND RÉCAP TECH & CYBER — {current_month.upper()} {current_year}",
        "description": f"**Ce qui a transformé l'industrie ce mois-ci :**\n{digest.get('intro', '')}{top_event_text}",
        "color": 0x6366F1,
        "footer": {"text": "Édition Mensuelle Exécutive • Bilan 30 Jours"}
    }

    embeds = [intro_embed]
    color_map = {
        "F59E0B": 0xF59E0B,
        "EF4444": 0xEF4444,
        "3B82F6": 0x3B82F6,
        "10B981": 0x10B981,
        "8B5CF6": 0x8B5CF6,
        "EC4899": 0xEC4899
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
                "description": field_text.strip()[:1500],
                "color": color_int,
                "footer": {"text": f"Bilan Mensuel • {cat.get('name')}"}
            })

    chunks = [
        ("Partie 1/2 — Bilan Macro, Tech, Cyber & IA", embeds[:4]),
        ("Partie 2/2 — Infra Cloud, Dev & Esport Mercato", embeds[4:])
    ]

    for part_label, chunk in chunks:
        if not chunk:
            continue

        total_chars = sum(len(e.get("title", "")) + len(e.get("description", "")) + len(e.get("footer", {}).get("text", "")) for e in chunk)
        if total_chars > 5500:
            for e in chunk:
                if len(e.get("description", "")) > 1800:
                    e["description"] = e["description"][:1800] + "..."

        payload = {
            "username": "Le Grand Journal Tech & Cyber",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3281/3281323.png",
            "content": f"🎆 **Le Grand Bilan Mensuel ({current_month} {current_year})** — {part_label} :",
            "embeds": chunk
        }
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=20)
            if resp.status_code in (200, 204):
                print(f"✅ Rétrospective {part_label} postée sur Discord !")
            else:
                print(f"❌ Erreur Webhook ({resp.status_code}) : {resp.text}")
            time.sleep(1.5)
        except Exception as e:
            print(f"❌ Erreur réseau: {e}")


if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL or not GEMINI_API_KEY:
        print("❌ Clés d'environnement manquantes.")
        exit(1)

    stories = fetch_top_stories_monthly()
    digest = generate_monthly_digest(stories)
    send_monthly_to_discord(digest)
