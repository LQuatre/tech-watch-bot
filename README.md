# 🚀 Bot de Veille Tech (Discord + Gemini IA)

Ce projet permet d'automatiser deux types de veille informatique sur ton serveur Discord via Webhook, avec analyse et synthèse par **Gemini Flash (IA gratuite)** :

1. ⚡ **Le Daily Digest (Quotidien)** : Les 5 meilleures actus des dernières 24h, chaque matin à 8h.
2. 📚 **Le Grand Récapitulatif Mensuel (Monthly)** : Une rétrospective catégorisée (*IA*, *Dev/Open-Source*, *Cybersécurité*, *Business/Hardware*) des 30 sujets les plus votés du mois, chaque 1er du mois.

---

## 📁 Structure du projet

- `main.py` : Script de la veille quotidienne.
- `monthly.py` : Script de la rétrospective mensuelle (Hacker News Top 30 jours + RSS + Synthèse catégorisée).
- `requirements.txt` : Dépendances (`feedparser`, `requests`, `python-dotenv`).
- `.github/workflows/daily_tech_watch.yml` : Workflow GitHub quotidien (tous les matins à 7h UTC).
- `.github/workflows/monthly_tech_watch.yml` : Workflow GitHub mensuel (chaque 1er du mois à 7h UTC).
- `.env.example` : Modèle de variables pour le local.

---

## ⚡ 1. Utilisation en local

1. Installe les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
2. Crée ton fichier `.env` avec tes clés :
   ```env
   DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
   GEMINI_API_KEY="AIzaSy..."
   ```
3. Lancer la veille quotidienne :
   ```bash
   python main.py
   ```
4. Lancer le récapitulatif mensuel :
   ```bash
   python monthly.py
   ```

---

## 🌐 2. Automatisation GitHub Actions

Les workflows tournent sans aucun serveur grâce à GitHub Actions :
- **Daily** : Tous les matins.
- **Monthly** : Le 1er de chaque mois.

Pour tester l'un ou l'autre manuellement :
Va sur ton dépôt dans **Actions**, choisis le workflow souhaité (*Daily AI Tech Watch* ou *Monthly AI Tech Retrospective*), et clique sur **Run workflow**.
