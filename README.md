# 🚀 Bot de Veille Tech Quotidienne (Discord + Gemini IA)

Ce projet permet de collecter automatiquement chaque jour les actualités tech de plusieurs sources de référence (Korben, Numerama, The Verge, Hacker News, TechCrunch...), de confier la sélection et la synthèse des 5 meilleures actus à **Gemini Flash (IA gratuite)**, puis de publier le résultat chaque matin sur ton serveur Discord via **Webhook**.

---

## 📁 Structure du projet

- `main.py` : Script Python principal (collecte RSS, prompt IA, publication Discord).
- `requirements.txt` : Dépendances (`feedparser`, `requests`, `python-dotenv`).
- `.github/workflows/daily_tech_watch.yml` : Automatisation gratuite par GitHub Actions (déclenchement quotidien à 8h).
- `.env.example` : Modèle pour configurer vos clés en local.

---

## ⚡ 1. Configuration rapide

### A. Récupérer tes 2 clés
1. **Webhook Discord** :
   - Clic droit sur le salon Discord de ton choix > *Modifier le salon* > *Intégrations* > *Webhooks* > *Nouveau Webhook*.
   - Copie l'URL du Webhook.
2. **Clé API Gemini (100% gratuite)** :
   - Rends-toi sur [Google AI Studio](https://aistudio.google.com/).
   - Clique sur *Get API key* > *Create API key* et copie-la.

### B. Tester en local (sur ton PC)
1. Crée un fichier `.env` à côté de `main.py` avec tes valeurs :
   ```env
   DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
   GEMINI_API_KEY="AIzaSy..."
   ```
2. Installe les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Lance le script :
   ```bash
   python main.py
   ```

---

## 🌐 2. Déploiement automatique avec GitHub (Gratuit H24)

Pour que la veille s'exécute automatiquement tous les jours sans laisser ton ordinateur allumé :

1. Crée un dépôt sur **GitHub** et pousse le contenu de ce dossier (`tech-watch-bot`).
2. Dans ton dépôt GitHub, va dans :
   **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.
3. Ajoute les deux secrets suivants :
   - `DISCORD_WEBHOOK_URL` : L'URL de ton webhook Discord.
   - `GEMINI_API_KEY` : Ta clé API Gemini.
4. C'est prêt ! Tu peux tester immédiatement en allant dans l'onglet **Actions** > **Daily AI Tech Watch** > **Run workflow**.
