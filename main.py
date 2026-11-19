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

# Modèles en cascade calibrés pour une résilience absolue
CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash"
]

# Les 5 piliers Tech & Cyber (43 sources)
TECH_PILLARS = {
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
    }
}

# Les 3 Grands Blocs Esport & Leaks Roster
ESPORT_GAMES = {
    "League of Legends": {
        "title": "🏆 LEAGUE OF LEGENDS • MERCATO & LEAKS",
        "emoji": "🏆",
        "color": 0x1D4ED8, # Bleu Royal LoL
        "footer": "Mercato LoL • LEC / LFL / Worlds",
        "feeds": {
            "Dexerto LoL": "https://www.dexerto.com/league-of-legends/feed/",
            "Fragster (LEC/LoL)": "https://www.fragster.com/feed/",
            "L'Équipe LoL": "https://dwh.lequipe.fr/api/edito/rss?path=/Esport/"
        },
        "default_summary": "Mercato et leaks de rosters en ébullition : accords verbaux, rachats de contrats (buyouts SkewMond, Yike, Rooster...) et recompositions majeures pour le LEC et la LFL."
    },
    "Rocket League": {
        "title": "🚀 ROCKET LEAGUE • ROSTERMANIA & RLCS",
        "emoji": "🚀",
        "color": 0x0284C7, # Cyan RLCS
        "footer": "Rostermania RLCS • Circuits Majeurs",
        "feeds": {
            "Dexerto Rocket League": "https://www.dexerto.com/rocket-league/feed/",
            "L'Équipe RL": "https://dwh.lequipe.fr/api/edito/rss?path=/Esport/"
        },
        "default_summary": "Rostermania et transferts sur Rocket League : réajustements de trios, mercato d'intersaison et qualifications pour les futurs tournois RLCS."
    },
    "Call of Duty": {
        "title": "💥 CALL OF DUTY • CDL & TRANSFERTS PROS",
        "emoji": "💥",
        "color": 0xEA580C, # Orange Militaire CDL
        "footer": "Scène CDL & Warzone • Roster Mania",
        "feeds": {
            "Dexerto Call of Duty": "https://www.dexerto.com/call-of-duty/feed/",
            "Upcomer CoD": "https://upcomer.com/feed"
        },
        "default_summary": "Rostermania CDL et scène compétitive Call of Duty : transferts de pros, composition des franchises américaines et évolutions du circuit compétitif."
    }
}

DEFAULT_SUMMARIES = {
    "Tech Générale": "Actualité dominée par les régulations numériques européennes, les évolutions matérielles et les stratégies des géants de la tech.",
    "Cybersécurité": "Vigilance sur les vulnérabilités supply-chain, les attaques ransomware ciblant les entreprises et les alertes d'organismes gouvernementaux.",
    "Intelligence Artificielle": "Accélération des modèles multimodaux, essor de l'inférence locale et outillage des agents IA pour développeurs.",
    "Infra & Cloud": "Optimisation des architectures cloud-natives, passage à l'échelle sur Kubernetes et résilience des réseaux Edge.",
    "Dev & Frameworks": "Mises à jour des runtimes, renforcement de la sécurité des paquets open source et évolutions des langages modernes."
}

ROSTER_KEYWORDS = [
    "transfer", "mercato", "roster", "leak", "rumor", "sign", "join", "leave", 
    "bench", "buyout", "contract", "skewmond", "yike", "caliste", "karmine", 
    "vitality", "fnatic", "g2", "rlcs", "cdl", "wooloo", "lineup"
]

def clean_html(raw_html: str) -> str:
    clean = re.sub(r'<[^>]+>', '', raw_html or '')
    clean = ' '.join(clean.split())
    return clean

def fetch_all_data(max_hours: int = 24):
    """Collecte les 5 piliers Tech (jusqu'à 5 articles) et les 3 Blocs Esport (jusqu'à 3 articles par jeu)."""
    tech_data = {}
    esport_data = {}

    print(f"📡 Collecte des 5 piliers Tech sur 43 sources...")
    for pillar, conf in TECH_PILLARS.items():
        tech_data[pillar] = []
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
                        tech_data[pillar].append({
                            "source": source,
                            "title": title,
                            "link": link,
                            "snippet": snippet
                        })
                        break
            except Exception as e:
                print(f"  ✗ Erreur {source}: {e}")
        tech_data[pillar] = tech_data[pillar][:5]
        print(f"  ✓ {pillar} : {len(tech_data[pillar])} articles prêts")

    print(f"🎮 Collecte des 3 Blocs Esport (LoL • Rocket League • Call of Duty)...")
    for game, conf in ESPORT_GAMES.items():
        esport_data[game] = []
        for source, url in conf["feeds"].items():
            source_count = 0
            try:
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.content)
                for entry in feed.entries[:12]:
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    snippet = clean_html(raw_summary)

                    if len(snippet) > 220:
                        cut = snippet[:220]
                        last_space = cut.rfind(' ')
                        snippet = (cut[:last_space] if last_space > 0 else cut) + "..."

                    if title and link:
                        text_to_check = f"{title} {snippet}".lower()
                        score = sum(10 for kw in ROSTER_KEYWORDS if kw in text_to_check)
                        esport_data[game].append({
                            "source": source,
                            "title": title,
                            "link": link,
                            "snippet": snippet,
                            "score": score
                        })
                        source_count += 1
                        if source_count >= 2:
                            break
            except Exception as e:
                print(f"  ✗ Erreur {source}: {e}")

        # Priorité aux transferts/leaks de rosters
        esport_data[game].sort(key=lambda x: x.get("score", 0), reverse=True)
        esport_data[game] = esport_data[game][:3]
        print(f"  ✓ {game} : {len(esport_data[game])} actus mercato/esport prêtes")

    return tech_data, esport_data

def translate_and_enrich_with_gemini(tech_data, esport_data):
    """Enrichissement IA complet : Brief, Tech, et les 3 gros blocs Esport dédiés."""
    compact_tech = {
        p: [{"title": a["title"][:90], "source": a["source"], "snippet": a["snippet"][:120], "link": a["link"]} for a in arts]
        for p, arts in tech_data.items()
    }
    compact_esport = {
        g: [{"title": a["title"][:90], "source": a["source"], "snippet": a["snippet"][:120], "link": a["link"]} for a in arts]
        for g, arts in esport_data.items()
    }

    prompt = f"""Tu es le rédacteur en chef d'une prestigieuse revue tech, cybersécurité et esport francophone.
Voici la sélection d'articles du jour :

TECH & CYBER :
{json.dumps(compact_tech, ensure_ascii=False, indent=2)}

ESPORT & MERCATO :
{json.dumps(compact_esport, ensure_ascii=False, indent=2)}

MISSION :
Génère une édition 100% EN FRANÇAIS IMPECCABLE, riche et captivante.

1. "executive_brief" :
   - "headline" : 1 phrase percutante sur le fait technologique ou cyber marquant du jour.
   - "threat_level" : Niveau de menace cyber ("Normal 🟢", "Modéré 🟡", "Élevé 🔴").
   - "macro_trend" : 1 phrase sur la tendance dominante.

2. "spotlight_tool" :
   - "title" : Nom de la pépite open-source / outil du jour repéré dans la tech.
   - "link" : URL
   - "why" : 2 phrases expliquant pourquoi c'est utile.

3. "tech_pillars" :
   Pour CHAQUE pilier Tech ("Tech Générale", "Cybersécurité", "Intelligence Artificielle", "Infra & Cloud", "Dev & Frameworks") :
   - "summary" : 2 phrases d'analyse éditoriale.
   - "articles" : Pour chaque article fourni :
       * "title_fr" : Titre traduit en français
       * "tag" : Tag court entre crochets (ex: "Hardware", "Vulnérabilité", "LLM", "Linux")
       * "point_fr" : 2 phrases complètes en français détaillant les faits précis et l'impact direct.

4. "esport_games" :
   Pour CHAQUE jeu ("League of Legends", "Rocket League", "Call of Duty") :
   - "summary" : 2 phrases d'analyse de fond focalisées sur le MERCATO, les TRANSFERTS et les LEAKS DE ROSTERS (ex: officialisations, buyouts, départs, rumeurs, tournois).
   - "articles" : Pour chaque actu du jeu :
       * "title_fr" : Titre traduit en français
       * "tag" : Tag explicite (ex: "LoL Mercato", "RLCS Transfert", "CoD CDL", "Roster Leak")
       * "point_fr" : 2 phrases complètes expliquant clairement les joueurs concernés, l'équipe et les enjeux.

FORMAT STRICTEMENT EXIGÉ : UNIQUEMENT un objet JSON valide :
{{
  "executive_brief": {{ "headline": "...", "threat_level": "Modéré 🟡", "macro_trend": "..." }},
  "spotlight_tool": {{ "title": "...", "link": "...", "why": "..." }},
  "tech_pillars": {{
    "Tech Générale": {{ "summary": "...", "articles": [{{"title_fr": "...", "tag": "...", "point_fr": "..."}}] }},
    "Cybersécurité": {{ "summary": "...", "articles": [...] }},
    "Intelligence Artificielle": {{ "summary": "...", "articles": [...] }},
    "Infra & Cloud": {{ "summary": "...", "articles": [...] }},
    "Dev & Frameworks": {{ "summary": "...", "articles": [...] }}
  }},
  "esport_games": {{
    "League of Legends": {{ "summary": "...", "articles": [{{"title_fr": "...", "tag": "...", "point_fr": "..."}}] }},
    "Rocket League": {{ "summary": "...", "articles": [...] }},
    "Call of Duty": {{ "summary": "...", "articles": [...] }}
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
            print(f"Traduction & structuration en gros blocs avec {model}...")
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

    print("⚠️ Repli sur les données standard.")
    return None

def send_dense_digest_to_discord(tech_data, esport_data, enriched_content):
    """Envoie le digest sur Discord découpé en 4 livraisons dont 3 gros blocs dédiés pour l'Esport."""
    today = datetime.now().strftime("%d/%m/%Y")
    
    brief = enriched_content.get("executive_brief", {}) if enriched_content else {}
    spotlight = enriched_content.get("spotlight_tool", {}) if enriched_content else {}
    tech_ai = enriched_content.get("tech_pillars", {}) if enriched_content else {}
    esport_ai = enriched_content.get("esport_games", {}) if enriched_content else {}

    # 1. Embed En-tête : Brief Matinal
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
        header_description = f"Bienvenue dans votre édition du {today}. Retrouvez l'essentiel de la tech, cyber, IA, cloud, dev et le mercato esport complet."

    header_embed = {
        "title": f"🌅 BRIEF & TENDANCES TECH DU JOUR — {today}",
        "description": header_description,
        "color": 0x6366F1,
        "footer": {"text": "Édition Exécutive • Veille Matinale"}
    }

    # 2. Embeds des 5 Piliers Tech
    tech_embeds = []
    for pillar_name, conf in TECH_PILLARS.items():
        arts = tech_data.get(pillar_name, [])
        if not arts:
            continue

        emoji = conf["emoji"]
        color = conf["color"]

        pillar_info = tech_ai.get(pillar_name, {})
        summary = pillar_info.get("summary") or DEFAULT_SUMMARIES.get(pillar_name, "")
        articles_ai = pillar_info.get("articles", [])

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

        tech_embeds.append({
            "title": f"{emoji} {pillar_name.upper()}",
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": f"Pôle {pillar_name} • Édition Complète en Français"}
        })

    # 3. Embed Pépite Open Source
    spotlight_embed = None
    if spotlight and spotlight.get("title") and spotlight.get("why"):
        tool_title = spotlight.get("title")
        tool_link = spotlight.get("link", "")
        tool_why = spotlight.get("why")
        spotlight_embed = {
            "title": "⭐ LA PÉPITE OPEN SOURCE & TECHNIQUE DU JOUR",
            "description": f"• **[{tool_title}]({tool_link})**\n↳ {tool_why}",
            "color": 0xFBBF24,
            "footer": {"text": "Sélection Développeurs & Ingénieurs • Tech Watch"}
        }

    # 4. Les 3 Gros Blocs Esport Dédiés (League of Legends, Rocket League, Call of Duty)
    esport_embeds = []
    for game_name, conf in ESPORT_GAMES.items():
        arts = esport_data.get(game_name, [])
        if not arts:
            continue

        color = conf["color"]
        title_block = conf["title"]
        footer_text = conf["footer"]

        game_info = esport_ai.get(game_name, {})
        summary = game_info.get("summary") or conf["default_summary"]
        articles_ai = game_info.get("articles", [])

        field_text = f"*{summary}*\n\n"
        for idx, art in enumerate(arts):
            ai_item = articles_ai[idx] if idx < len(articles_ai) else {}
            title = ai_item.get("title_fr") or art.get("title", "Actualité")
            tag = f"`[{ai_item.get('tag', game_name)}]` " if ai_item.get("tag") else ""
            point = ai_item.get("point_fr") or art.get("snippet", "")
            link = art.get("link", "")
            source = art.get("source", "Web")

            if point:
                field_text += f"• {tag}**[{title}]({link})** `({source})`\n  ↳ {point}\n\n"
            else:
                field_text += f"• {tag}**[{title}]({link})** `({source})`\n\n"

        esport_embeds.append({
            "title": title_block,
            "description": field_text.strip(),
            "color": color,
            "footer": {"text": footer_text}
        })

    # Découpage équilibré en 4 livraisons :
    # Partie 1/4 : Brief Exécutif & Tech Générale
    # Partie 2/4 : Cybersécurité & Intelligence Artificielle
    # Partie 3/4 : Infra, Cloud, Dev & Pépite Open Source
    # Partie 4/4 : Les 3 Gros Blocs Esport (LoL • Rocket League • Call of Duty)
    parts_def = [
        ("Partie 1/4 — Brief Exécutif & Tech Générale", [header_embed, tech_embeds[0]] if tech_embeds else [header_embed]),
        ("Partie 2/4 — Cybersécurité & Intelligence Artificielle", tech_embeds[1:3] if len(tech_embeds) >= 3 else tech_embeds[1:]),
        ("Partie 3/4 — Infra, Cloud, Dev & Pépite Open Source", (tech_embeds[3:] + ([spotlight_embed] if spotlight_embed else [])) if len(tech_embeds) >= 4 else ([spotlight_embed] if spotlight_embed else [])),
        ("Partie 4/4 — 🎮 Esport & Leaks Roster (LoL • Rocket League • Call of Duty)", esport_embeds)
    ]

    for part_label, embeds_chunk in parts_def:
        if not embeds_chunk:
            continue

        # Sécurité anti-dépassement Discord (6000 chars max)
        total_chars = sum(len(e.get("title", "")) + len(e.get("description", "")) + len(e.get("footer", {}).get("text", "")) for e in embeds_chunk)
        if total_chars > 5500:
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

    tech_news, esport_news = fetch_all_data()
    enriched = translate_and_enrich_with_gemini(tech_news, esport_news)
    send_dense_digest_to_discord(tech_news, esport_news, enriched)
