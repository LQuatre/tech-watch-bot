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

# Modèles en cascade calibrés pour une résilience absolue (priorité aux quotas hauts en cas de saturation)
CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash"
]

# 50 sources sélectionnées et testées (médias de référence français et internationaux)
PILLARS = {
    "Tech Générale": {
        "emoji": "🟠",
        "color": 0xF59E0B, # Orange
        "feeds": {
            "Le Monde Informatique": "https://www.lemondeinformatique.fr/flux-rss/thematique/toutes-les-actualites/rss.xml",
            "Génération-NT": "https://www.generation-nt.com/export/rss.xml",
            "Next": "https://next.ink/feed/",
            "Numerama": "https://www.numerama.com/feed/",
            "Korben": "https://korben.info/feed",
            "Frandroid": "https://www.frandroid.com/feed",
            "The Verge": "https://www.theverge.com/rss/index.xml",
            "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index"
        }
    },
    "Cybersécurité": {
        "emoji": "🔴",
        "color": 0xEF4444, # Rouge
        "feeds": {
            "Le Monde Informatique (Sec)": "https://www.lemondeinformatique.fr/flux-rss/thematique/securite/rss.xml",
            "ZATAZ": "https://www.zataz.com/feed/",
            "InCyber": "https://incyber.org/feed/",
            "Undernews": "https://www.undernews.fr/feed",
            "CERT-FR": "https://www.cert.ssi.gouv.fr/alerte/feed/",
            "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
            "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
            "Krebs on Security": "https://krebsonsecurity.com/feed/",
            "The Register (Sec)": "https://www.theregister.com/security/headlines.atom",
            "SANS ISC": "https://isc.sans.edu/rssfeed.xml"
        }
    },
    "Intelligence Artificielle": {
        "emoji": "🟣",
        "color": 0x8B5CF6, # Violet
        "feeds": {
            "Le Monde Informatique (IA)": "https://www.lemondeinformatique.fr/flux-rss/thematique/intelligence-artificielle/rss.xml",
            "ActuIA": "https://www.actuia.com/feed/",
            "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
            "Simon Willison (AI)": "https://simonwillison.net/atom/everything/",
            "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
            "Ars Technica AI": "https://arstechnica.com/ai/feed/",
            "MarkTechPost": "https://www.marktechpost.com/feed/",
            "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/"
        }
    },
    "Infra & Cloud": {
        "emoji": "🔵",
        "color": 0x3B82F6, # Bleu
        "feeds": {
            "Le Monde Informatique (Cloud)": "https://www.lemondeinformatique.fr/flux-rss/thematique/cloud-computing/rss.xml",
            "Silicon.fr": "https://www.silicon.fr/feed",
            "The New Stack": "https://thenewstack.io/feed/",
            "Cloudflare Blog": "https://blog.cloudflare.com/rss/",
            "CNCF Blog": "https://www.cncf.io/feed/",
            "AWS News": "https://aws.amazon.com/blogs/aws/feed/",
            "Netflix Tech": "https://netflixtechblog.com/feed"
        }
    },
    "Dev & Frameworks": {
        "emoji": "🟢",
        "color": 0x10B981, # Vert
        "feeds": {
            "Le Monde Informatique (Dev)": "https://www.lemondeinformatique.fr/flux-rss/thematique/developpement/rss.xml",
            "Journal du Hacker": "https://www.journalduhacker.net/rss",
            "LinuxFR": "https://linuxfr.org/journaux.atom",
            "Phoronix": "https://www.phoronix.com/phoronix-rss.php",
            "GitHub Blog": "https://github.blog/feed/",
            "The Changelog": "https://changelog.com/feed",
            "Smashing Mag (Web/JS)": "https://www.smashingmagazine.com/feed/",
            "InfoQ": "https://feed.infoq.com/",
            "Rust Blog": "https://blog.rust-lang.org/feed.xml",
            "Laravel News": "https://laravel-news.com/feed"
        }
    },
    "Esport & Leaks Roster": {
        "emoji": "🎮",
        "color": 0xEC4899, # Rose / Magenta Esport
        "feeds": {
            "Dexerto LoL": "https://www.dexerto.com/league-of-legends/feed/",
            "Dexerto Rocket League": "https://www.dexerto.com/rocket-league/feed/",
            "Dexerto Call of Duty": "https://www.dexerto.com/call-of-duty/feed/",
            "L'Équipe Esport": "https://dwh.lequipe.fr/api/edito/rss?path=/Esport/",
            "Dexerto Esport": "https://www.dexerto.com/esports/feed/",
            "Upcomer": "https://upcomer.com/feed",
            "Fragster (LEC/LoL)": "https://www.fragster.com/feed/"
        }
    }
}

DEFAULT_SUMMARIES = {
    "Tech Générale": "Actualité dominée par les régulations numériques européennes, les évolutions matérielles et les stratégies des géants de la tech.",
    "Cybersécurité": "Vigilance sur les vulnérabilités supply-chain, les attaques ransomware ciblant les entreprises et les alertes d'organismes gouvernementaux.",
    "Intelligence Artificielle": "Accélération des modèles multimodaux, essor de l'inférence locale et outillage des agents IA pour développeurs.",
    "Infra & Cloud": "Optimisation des architectures cloud-natives, passage à l'échelle sur Kubernetes et résilience des réseaux Edge.",
    "Dev & Frameworks": "Mises à jour des runtimes, renforcement de la sécurité des paquets open source et évolutions des langages modernes.",
    "Esport & Leaks Roster": "Mercato et rumeurs de transferts sur League of Legends (LEC/LFL), mouvements de rosters RLCS sur Rocket League et transferts de pros sur Call of Duty CDL."
}

def clean_html(raw_html: str) -> str:
    clean = re.sub(r'<[^>]+>', '', raw_html or '')
    clean = ' '.join(clean.split())
    return clean

def fetch_all_pillars(max_hours: int = 24):
    """Collecte jusqu'à 5 articles distincts par pilier parmi 50 sources."""
    structured = {}
    print(f"📡 Collecte des articles sur 50 sources de référence...")

    for pillar, conf in PILLARS.items():
        structured[pillar] = []
        for source, url in conf["feeds"].items():
            try:
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.content)

                for entry in feed.entries[:4]:
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    snippet = clean_html(raw_summary)

                    if snippet.lower() in ("comments", "comments...", ""):
                        snippet = ""

                    if len(snippet) > 220:
                        cut = snippet[:220]
                        last_space = cut.rfind(' ')
                        snippet = (cut[:last_space] if last_space > 0 else cut) + "..."

                    if title and link:
                        structured[pillar].append({
                            "source": source,
                            "title": title,
                            "link": link,
                            "snippet": snippet
                        })
                        # 1 article retenu par source pour diversifier au maximum
                        break
            except Exception as e:
                print(f"  ✗ Erreur {source}: {e}")

        # On retient 5 articles maximum par pilier
        structured[pillar] = structured[pillar][:5]
        print(f"  ✓ {pillar} : {len(structured[pillar])} articles prêts")

    return structured

def translate_and_enrich_with_gemini(structured_data):
    """Demande à Gemini d'enrichir le digest : Brief matinal, tags, traductions FR et pépite open-source."""
    compact_data = {}
    for p, arts in structured_data.items():
        compact_data[p] = [
            {"title": a["title"][:90], "source": a["source"], "snippet": a["snippet"][:120], "link": a["link"]}
            for a in arts
        ]

    prompt = f"""Tu es le rédacteur en chef d'une prestigieuse revue tech et cybersécurité francophone.
Voici la sélection des articles du jour classés par piliers :
{json.dumps(compact_data, ensure_ascii=False, indent=2)}

MISSION :
Génère une édition complète 100% EN FRANÇAIS IMPECCABLE, riche et professionnelle.

1. "executive_brief" :
   - "headline" : Une phrase d'impact direct résumant le grand fait technologique ou cyber marquant d'aujourd'hui.
   - "threat_level" : Le niveau de menace cyber du jour ("Normal 🟢", "Modéré 🟡", ou "Élevé 🔴") en fonction des failles ou attaques détectées.
   - "macro_trend" : Une phrase synthétisant la tendance forte de fond qui traverse l'écosystème aujourd'hui.

2. "spotlight_tool" :
   Identifie parmi les articles ou actualités fournies LA pépite technique / open-source / outil remarquable du jour :
   - "title" : Nom de l'outil ou projet
   - "link" : URL associée
   - "why" : 2 phrases complètes en français expliquant ce qu'il apporte aux développeurs/ingénieurs.

3. "pillars" :
   Pour CHAQUE pilier ("Tech Générale", "Cybersécurité", "Intelligence Artificielle", "Infra & Cloud", "Dev & Frameworks", "Esport & Leaks Roster") :
   - "summary" : 2 phrases d'analyse de fond en français sur la dynamique du secteur aujourd'hui (pour l'esport : mercato, leaks de rosters, transferts et actualité compétitive LoL/RL/CoD).
   - "articles" : Pour chaque article fourni dans ce pilier :
       * "title_fr" : Titre traduit et percutant en français.
       * "tag" : Un mot-clé court entre crochets (ex: "Hardware", "Vulnérabilité", "LLM", "Linux", "Réseau", "Dev", "LoL Mercato", "RLCS", "CoD CDL").
       * "point_fr" : 2 phrases complètes et claires en français détaillant les faits précis et l'impact direct (pas de texte tronqué).

FORMAT STRICTEMENT EXIGÉ : UNIQUEMENT un objet JSON valide :
{{
  "executive_brief": {{
    "headline": "...",
    "threat_level": "Modéré 🟡",
    "macro_trend": "..."
  }},
  "spotlight_tool": {{
    "title": "...",
    "link": "...",
    "why": "..."
  }},
  "pillars": {{
    "Tech Générale": {{ "summary": "...", "articles": [{{"title_fr": "...", "tag": "...", "point_fr": "..."}}] }},
    "Cybersécurité": {{ "summary": "...", "articles": [...] }},
    "Intelligence Artificielle": {{ "summary": "...", "articles": [...] }},
    "Infra & Cloud": {{ "summary": "...", "articles": [...] }},
    "Dev & Frameworks": {{ "summary": "...", "articles": [...] }},
    "Esport & Leaks Roster": {{ "summary": "...", "articles": [...] }}
  }}
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
            print(f"Traduction & enrichissement éditorial avec {model}...")
            response = requests.post(url, json=payload, timeout=45)
            if response.status_code == 200:
                raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw_text.startswith("```"):
                    raw_text = re.sub(r'^```(json)?\s*', '', raw_text)
                    raw_text = re.sub(r'\s*```$', '', raw_text)
                data = json.loads(raw_text)
                print(f"✓ Enrichissement réussi avec succès via {model} !")
                return data
            elif response.status_code == 429:
                print(f"  ↳ Quota atteint sur {model} (429), bascule immédiate...")
                continue
            elif response.status_code == 503:
                print(f"  ↳ Modèle {model} occupé (503), bascule immédiate...")
                continue
            else:
                print(f"  ↳ Erreur HTTP {response.status_code} sur {model}")
        except Exception as e:
            print(f"  ↳ Exception {model}: {e}")

    print("⚠️ Repli sur le format standard sans enrichissement IA.")
    return None

def send_dense_digest_to_discord(structured_data, enriched_content):
    """Envoie le digest enrichi sur Discord en 2 livraisons élégantes."""
    today = datetime.now().strftime("%d/%m/%Y")
    
    brief = enriched_content.get("executive_brief", {}) if enriched_content else {}
    spotlight = enriched_content.get("spotlight_tool", {}) if enriched_content else {}
    pillars_ai = enriched_content.get("pillars", {}) if enriched_content else {}

    # 1. Embed En-tête : Brief Matinal & Tendance du jour
    header_description = ""
    if brief:
        headline = brief.get("headline", "")
        threat = brief.get("threat_level", "Normal 🟢")
        macro = brief.get("macro_trend", "")
        header_description = (
            f"🎯 **Le fait marquant :** {headline}\n\n"
            f"🛡️ **Vigilance Cybersécurité :** {threat}\n\n"
            f"📈 **Tendance macro :** {macro}\n\n"
            f"⏱️ *Temps de lecture estimé : ~3 minutes*"
        )
    else:
        header_description = f"Bienvenue dans votre édition du {today}. Retrouvez l'essentiel de l'actualité tech, cyber, IA, cloud et dev décryptée en français."

    header_embed = {
        "title": f"🌅 BRIEF & TENDANCES TECH DU JOUR — {today}",
        "description": header_description,
        "color": 0x6366F1, # Indigo moderne
        "footer": {"text": "Édition Exécutive • Veille Matinale"}
    }

    # 2. Embeds des 5 Piliers
    pillar_embeds = []
    for pillar_name, conf in PILLARS.items():
        arts = structured_data.get(pillar_name, [])
        if not arts:
            continue

        emoji = conf["emoji"]
        color = conf["color"]

        pillar_data = pillars_ai.get(pillar_name, {})
        summary = pillar_data.get("summary") or DEFAULT_SUMMARIES.get(pillar_name, "")
        articles_ai = pillar_data.get("articles", [])

        field_text = f"*{summary}*\n\n"

        for idx, art in enumerate(arts):
            ai_item = articles_ai[idx] if idx < len(articles_ai) else {}
            title = ai_item.get("title_fr") or art.get("title", "Actualité")
            tag = f"`[{ai_item.get('tag', 'Tech')}]` " if ai_item.get("tag") else ""
            point = ai_item.get("point_fr") or art.get("snippet", "")
            link = art.get("link", "")
            source = art.get("source", "Web")

            if point:
                field_text += f"• {tag}**[{title}]({link})** `({source})`\n  ↳ {point}\n\n"
            else:
                field_text += f"• {tag}**[{title}]({link})** `({source})`\n\n"

        pillar_embeds.append({
            "title": f"{emoji} {pillar_name.upper()}",
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": f"Pôle {pillar_name} • Édition Complète en Français"}
        })

    # 3. Embed Pépite Open Source / Outil du jour
    spotlight_embed = None
    if spotlight and spotlight.get("title") and spotlight.get("why"):
        tool_title = spotlight.get("title")
        tool_link = spotlight.get("link", "")
        tool_why = spotlight.get("why")
        spotlight_embed = {
            "title": "⭐ LA PÉPITE OPEN SOURCE & TECHNIQUE DU JOUR",
            "description": f"• **[{tool_title}]({tool_link})**\n↳ {tool_why}",
            "color": 0xFBBF24, # Or / Ambre
            "footer": {"text": "Sélection Développeurs & Ingénieurs • Tech Watch"}
        }

    # Découpage équilibré en 4 livraisons pour ne JAMAIS dépasser la limite Discord (6000 caractères max par envoi)
    # Partie 1/4 : Brief Exécutif & Tech Générale (~2000 chars)
    # Partie 2/4 : Cybersécurité & Intelligence Artificielle (~2800 chars)
    # Partie 3/4 : Infra, Cloud, Dev & Pépite Open Source (~3000 chars)
    # Partie 4/4 : 🎮 Esport & Leaks Roster (LoL • Rocket League • Call of Duty) (~2200 chars)
    parts_def = [
        ("Partie 1/4 — Brief Exécutif & Tech Générale", [header_embed, pillar_embeds[0]] if pillar_embeds else [header_embed]),
        ("Partie 2/4 — Cybersécurité & Intelligence Artificielle", pillar_embeds[1:3] if len(pillar_embeds) >= 3 else pillar_embeds[1:]),
        ("Partie 3/4 — Infra, Cloud, Dev & Pépite Open Source", (pillar_embeds[3:5] + ([spotlight_embed] if spotlight_embed else [])) if len(pillar_embeds) >= 5 else ([spotlight_embed] if spotlight_embed else [])),
        ("Partie 4/4 — 🎮 Esport & Leaks Roster (LoL • Rocket League • CoD)", [pillar_embeds[5]] if len(pillar_embeds) >= 6 else (pillar_embeds[5:] if len(pillar_embeds) > 5 else []))
    ]

    for part_label, embeds_chunk in parts_def:
        if not embeds_chunk:
            continue

        # Sécurité anti-dépassement Discord : vérification du total de caractères
        total_chars = sum(len(e.get("title", "")) + len(e.get("description", "")) + len(e.get("footer", {}).get("text", "")) for e in embeds_chunk)
        if total_chars > 5500:
            # Sécurité supplémentaire : tronquer légèrement les descriptions si besoin
            for e in embeds_chunk:
                if len(e.get("description", "")) > 1800:
                    e["description"] = e["description"][:1800] + "..."

        payload = {
            "username": "Le Grand Journal Tech & Cyber",
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
            time.sleep(1.5)
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
    enriched = translate_and_enrich_with_gemini(structured_news)
    send_dense_digest_to_discord(structured_news, enriched)
