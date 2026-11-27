import os
import sys
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import feedparser
import requests

from gemini_helper import discover_verified_models, generate_json_with_verified_gemini

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

# Les 5 piliers Tech & Cyber (43 sources)
TECH_PILLARS = {
    "Tech Générale": {
        "emoji": "🟠",
        "color": 0xF59E0B,
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
        "color": 0xEF4444,
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
        "color": 0x8B5CF6,
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
        "color": 0x3B82F6,
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
        "color": 0x10B981,
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
        "color": 0x1D4ED8,
        "footer": "Mercato LoL • LEC / LFL / Worlds",
        "feeds": {
            "Dexerto LoL": "https://www.dexerto.com/league-of-legends/feed/",
            "Fragster (LEC/LoL)": "https://www.fragster.com/feed/",
            "L'Équipe LoL": "https://dwh.lequipe.fr/api/edito/rss?path=/Esport/"
        },
        "default_summary": "Mercato et leaks de rosters en ébullition : accords verbaux, rachats de contrats (buyouts) et recompositions majeures pour le LEC et la LFL."
    },
    "Rocket League": {
        "title": "🚀 ROCKET LEAGUE • ROSTERMANIA & RLCS",
        "emoji": "🚀",
        "color": 0x0284C7,
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
        "color": 0xEA580C,
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
    clean = re.sub(r"<[^>]+>", "", raw_html or "")
    return " ".join(clean.split())


def _download_feed(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=7)
        if r.status_code == 200:
            return feedparser.parse(r.content)
    except Exception:
        pass
    return None


def fetch_all_data():
    """Télécharge en parallèle tous les flux RSS (environ 4s au lieu de 45s)."""
    t0 = time.time()
    all_urls = set()
    for conf in TECH_PILLARS.values():
        all_urls.update(conf["feeds"].values())
    for conf in ESPORT_GAMES.values():
        all_urls.update(conf["feeds"].values())

    print(f"📡 Téléchargement parallèle de {len(all_urls)} flux RSS...")
    url_list = list(all_urls)
    with ThreadPoolExecutor(max_workers=12) as pool:
        parsed_list = list(pool.map(_download_feed, url_list))
    feed_cache = dict(zip(url_list, parsed_list))
    print(f"  ✓ Flux récupérés en {time.time() - t0:.1f}s")

    tech_data = {}
    for pillar, conf in TECH_PILLARS.items():
        tech_data[pillar] = []
        for source, url in conf["feeds"].items():
            feed = feed_cache.get(url)
            if not feed:
                continue
            for entry in feed.entries[:4]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                snippet = clean_html(raw_summary)
                if snippet.lower() in ("comments", "comments...", ""):
                    snippet = ""
                if len(snippet) > 220:
                    cut = snippet[:220]
                    last_space = cut.rfind(" ")
                    snippet = (cut[:last_space] if last_space > 0 else cut) + "..."
                if title and link:
                    tech_data[pillar].append({
                        "source": source,
                        "title": title,
                        "link": link,
                        "snippet": snippet
                    })
                    break
        tech_data[pillar] = tech_data[pillar][:5]
        print(f"  ✓ {pillar} : {len(tech_data[pillar])} articles prêts")

    esport_data = {}
    for game, conf in ESPORT_GAMES.items():
        esport_data[game] = []
        for source, url in conf["feeds"].items():
            feed = feed_cache.get(url)
            if not feed:
                continue
            source_count = 0
            for entry in feed.entries[:12]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                snippet = clean_html(raw_summary)
                if len(snippet) > 220:
                    cut = snippet[:220]
                    last_space = cut.rfind(" ")
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
        esport_data[game].sort(key=lambda x: x.get("score", 0), reverse=True)
        esport_data[game] = esport_data[game][:3]
        print(f"  ✓ {game} : {len(esport_data[game])} actus mercato/esport prêtes")

    return tech_data, esport_data


def translate_and_enrich_with_gemini(tech_data, esport_data):
    """
    Découpe l'enrichissement en 2 appels JSON rapides et légers sur les modèles
    vérifiés dynamiquement (priorité Flash-Lite à 500 RPD -> 0 timeout, 0 troncature).
    """
    compact_tech = {
        p: [{"title": a["title"][:90], "source": a["source"], "snippet": a["snippet"][:120], "link": a["link"]} for a in arts]
        for p, arts in tech_data.items()
    }
    compact_esport = {
        g: [{"title": a["title"][:90], "source": a["source"], "snippet": a["snippet"][:120], "link": a["link"]} for a in arts]
        for g, arts in esport_data.items()
    }

    prompt_tech = f"""Tu es le rédacteur en chef d'une revue tech et cybersécurité francophone.
Voici les articles Tech & Cyber du jour :
{json.dumps(compact_tech, ensure_ascii=False)}

Génère UNIQUEMENT un objet JSON valide 100% EN FRANÇAIS IMPECCABLE :
1. "executive_brief": {{"headline": "1 phrase fait marquant", "threat_level": "Normal 🟢 | Modéré 🟡 | Élevé 🔴", "macro_trend": "1 phrase tendance"}}
2. "spotlight_tool": {{"title": "Nom outil/projet open-source repéré", "link": "URL", "why": "2 phrases d'explication"}}
3. "tech_pillars": Pour CHAQUE pilier ("Tech Générale", "Cybersécurité", "Intelligence Artificielle", "Infra & Cloud", "Dev & Frameworks") :
   - "summary": 2 phrases d'analyse éditoriale.
   - "articles": liste dans le même ordre avec {{"title_fr": "Titre traduit FR", "tag": "Mot-clé court", "point_fr": "2 phrases claires et complètes en français (faits + impact)"}}.
"""

    prompt_esport = f"""Tu es un journaliste esport francophone spécialiste du mercato (LoL, Rocket League, Call of Duty).
Voici les actus Esport du jour :
{json.dumps(compact_esport, ensure_ascii=False)}

Génère UNIQUEMENT un objet JSON valide 100% EN FRANÇAIS IMPECCABLE avec la clé "esport_games" contenant pour CHAQUE jeu ("League of Legends", "Rocket League", "Call of Duty") :
- "summary": 2 phrases d'analyse centrées sur le mercato, les transferts, leaks de rosters et enjeux compétitifs.
- "articles": liste dans le même ordre avec {{"title_fr": "Titre traduit FR", "tag": "Ex: LoL Mercato | RLCS | CoD CDL", "point_fr": "2 phrases complètes expliquant joueurs, équipes et impact"}}.
"""

    tech_res = generate_json_with_verified_gemini(GEMINI_API_KEY, prompt_tech, label="Volet Tech & Cyber") or {}
    esport_res = generate_json_with_verified_gemini(GEMINI_API_KEY, prompt_esport, label="Volet Esport & Mercato") or {}

    if not tech_res and not esport_res:
        return None

    return {
        "executive_brief": tech_res.get("executive_brief", {}),
        "spotlight_tool": tech_res.get("spotlight_tool", {}),
        "tech_pillars": tech_res.get("tech_pillars", {}),
        "esport_games": esport_res.get("esport_games", esport_res if "League of Legends" in esport_res else {}),
    }


def send_dense_digest_to_discord(tech_data, esport_data, enriched_content):
    """Envoie le digest sur Discord découpé en 4 livraisons dont 3 gros blocs dédiés pour l'Esport."""
    today = datetime.now().strftime("%d/%m/%Y")

    brief = enriched_content.get("executive_brief", {}) if enriched_content else {}
    spotlight = enriched_content.get("spotlight_tool", {}) if enriched_content else {}
    tech_ai = enriched_content.get("tech_pillars", {}) if enriched_content else {}
    esport_ai = enriched_content.get("esport_games", {}) if enriched_content else {}

    if brief and brief.get("headline"):
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

    spotlight_embed = None
    if spotlight and spotlight.get("title") and spotlight.get("why"):
        spotlight_embed = {
            "title": "⭐ LA PÉPITE OPEN SOURCE & TECHNIQUE DU JOUR",
            "description": f"• **[{spotlight.get('title')}]({spotlight.get('link', '')})**\n↳ {spotlight.get('why')}",
            "color": 0xFBBF24,
            "footer": {"text": "Sélection Développeurs & Ingénieurs • Tech Watch"}
        }

    esport_embeds = []
    for game_name, conf in ESPORT_GAMES.items():
        arts = esport_data.get(game_name, [])
        if not arts:
            continue

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
            "title": conf["title"],
            "description": field_text.strip(),
            "color": conf["color"],
            "footer": {"text": conf["footer"]}
        })

    parts_def = [
        ("Partie 1/4 — Brief Exécutif & Tech Générale", [header_embed, tech_embeds[0]] if tech_embeds else [header_embed]),
        ("Partie 2/4 — Cybersécurité & Intelligence Artificielle", tech_embeds[1:3] if len(tech_embeds) >= 3 else tech_embeds[1:]),
        ("Partie 3/4 — Infra, Cloud, Dev & Pépite Open Source", (tech_embeds[3:] + ([spotlight_embed] if spotlight_embed else [])) if len(tech_embeds) >= 4 else ([spotlight_embed] if spotlight_embed else [])),
        ("Partie 4/4 — 🎮 Esport & Leaks Roster (LoL • Rocket League • Call of Duty)", esport_embeds)
    ]

    for part_label, embeds_chunk in parts_def:
        if not embeds_chunk:
            continue

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


def run_gemini_smoke_test():
    """Vérifie en conditions réelles les modèles disponibles sur la clé API sans poster sur Discord."""
    if not GEMINI_API_KEY:
        print("❌ Clé GEMINI_API_KEY manquante.")
        sys.exit(1)
    models = discover_verified_models(GEMINI_API_KEY)
    print(f"\n🧪 Test réel d'appel JSON sur le modèle prioritaire : {models[0] if models else 'aucun'}")
    res = generate_json_with_verified_gemini(
        GEMINI_API_KEY,
        'Réponds uniquement avec ce JSON exact : {"ok": true, "message": "Modèle Gemini opérationnel en français"}',
        label="Smoke-Test Vérification Modèle"
    )
    if not res:
        print("❌ Le test réel Gemini a échoué.")
        sys.exit(1)
    print(f"🎉 RÉSULTAT VÉRIFIÉ : {json.dumps(res, ensure_ascii=False)}")


if __name__ == "__main__":
    if "--test-gemini" in sys.argv or os.environ.get("RUN_MODE") == "test_gemini_only":
        run_gemini_smoke_test()
        sys.exit(0)

    if not DISCORD_WEBHOOK_URL:
        print("❌ Clé DISCORD_WEBHOOK_URL manquante.")
        sys.exit(1)
    if not GEMINI_API_KEY:
        print("❌ Clé GEMINI_API_KEY manquante.")
        sys.exit(1)

    tech_news, esport_news = fetch_all_data()
    enriched = translate_and_enrich_with_gemini(tech_news, esport_news)
    send_dense_digest_to_discord(tech_news, esport_news, enriched)
