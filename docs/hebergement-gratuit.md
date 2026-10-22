# Hébergement gratuit de FinPilot

Cette configuration utilise Cloudflare Pages pour le frontend, Render Free pour l'API FastAPI et Neon Free pour PostgreSQL. Les données métier et les pièces jointes sont stockées dans Neon ; elles ne dépendent donc pas du disque éphémère de Render.

## 1. Préparer le dépôt

Le déploiement automatique nécessite que le projet soit dans un dépôt GitHub. Vérifiez que `.env`, les clés et `backend/finpilot.db` ne sont pas ajoutés au dépôt ; `.gitignore` les exclut déjà.

## 2. Créer la base Neon

1. Créez un projet PostgreSQL sur le plan Free.
2. Dans **Connect**, choisissez l'URL de connexion avec pooler et copiez la chaîne complète.
3. Conservez-la comme variable secrète `DATABASE_URL` sur Render. Le backend convertit automatiquement les préfixes `postgres://` et `postgresql://` vers le pilote psycopg.

Ne mettez jamais cette chaîne dans le frontend ou dans GitHub.

## 3. Déployer l'API sur Render

Créez un **Web Service** depuis le dépôt :

- Root Directory : `backend`
- Runtime : Docker
- Plan : Free
- Port : laisser Render fournir `PORT`

Ajoutez ces variables dans les paramètres du service :

| Variable | Valeur |
| --- | --- |
| `DATABASE_URL` | Chaîne Neon copiée précédemment |
| `FINPILOT_SECRET_KEY` | Clé aléatoire privée |
| `FINPILOT_CORS_ORIGINS` | URL Pages exacte, à renseigner après l'étape 4 |

Pour créer une clé secrète localement avec Python : `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Collez le résultat dans Render, jamais dans le code. Le démarrage du conteneur applique les migrations Alembic avant de lancer FastAPI.

Render fournit une URL telle que `https://finpilot-api.onrender.com`. L'API gratuite peut se mettre en veille après 15 minutes sans requête ; la première ouverture qui suit peut être lente.

## 4. Déployer le frontend sur Cloudflare Pages

Créez un projet Pages connecté au même dépôt :

- Root Directory : `frontend`
- Build command : `npm ci && npm run build`
- Build output directory : `dist`
- Variable de production `VITE_API_URL` : `https://<url-api-render>/api`

Pages fournit une adresse gratuite en `pages.dev`. Le fichier `public/_redirects` permet aux routes React de fonctionner après un rechargement direct.

Une fois l'adresse `pages.dev` connue, renseignez-la dans `FINPILOT_CORS_ORIGINS` sur Render, puis redéployez l'API. Indiquez uniquement les origines autorisées, séparées par des virgules si plusieurs domaines sont utilisés.

## 5. Vérifier et utiliser l'application

1. Ouvrez `https://<url-api-render>/api/health` ; l'API doit répondre avec `status: ok`.
2. Crée ton compte depuis l'écran de connexion sur Pages. Aucun compte partagé n'est créé au démarrage ; ton espace reçoit seulement les domaines et catégories de départ, sans client ni montant fictif.
3. Crée un client, une transaction et une pièce jointe. Redéploie l'API puis vérifie que les trois sont toujours accessibles.
4. Télécharge régulièrement la sauvegarde FinPilot sur ton ordinateur. Les offres gratuites ne donnent pas les mêmes garanties de sauvegarde qu'une offre de production payante.

Chaque compte possède son propre espace. Les cartes affichées sur l'écran de connexion sont des illustrations fictives marquées « démo » ; elles ne sont pas enregistrées dans la base.

## Limites des offres gratuites

Les offres gratuites suffisent pour un portfolio et un usage léger, sans garantie de disponibilité permanente. Render peut mettre l'API en veille. Neon limite le calcul, le stockage et le transfert mensuels ; son calcul se met en veille automatiquement quand il est inactif. Si un quota gratuit est atteint, le service peut être suspendu jusqu'à son renouvellement.
