# FinPilot

FinPilot est un cockpit financier pour entrepreneur individuel : encaissements, dépenses, devis, factures, rentabilité, créances et trésorerie sont réunis dans un tableau de bord en FCFA.

## Fonctions

- Tableau de bord exécutif avec filtres de période, activité et client, indicateurs comparés, courbes mensuelles, répartition par activité, principaux clients et alertes.
- Registre de transactions avec catégories, moyens de paiement, statuts, pièces jointes et import/export CSV avec contrôle des doublons.
- Mini CRM clients avec chiffre d’affaires, créances ouvertes et segmentation A/B/C.
- Devis numérotés, conversion en facture, paiements partiels et génération de PDF.
- Analyses de rentabilité par activité, client et prestation, saisie du temps, prix conseillé et point mort.
- Alertes réglables sur factures en retard, concentration, dépenses récurrentes, baisse de marge, tension de trésorerie et pistes d’économies ou de croissance.
- Prévision de trésorerie à trois mois avec moyenne mobile, ajustement saisonnier simple lorsque l’historique le permet, scénarios, budgets et rapports PDF/Excel.
- Authentification par mot de passe haché, sauvegarde/restauration JSON incluant les pièces jointes et espace initial sans clients ni chiffres fictifs.
- Identité visuelle FinPilot en SVG, icônes responsives, connexion adaptative jour/nuit et signature de développement sur l’application et les documents PDF/CSV.

## Démarrage local

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

API : <http://localhost:8000/api>, documentation OpenAPI : <http://localhost:8000/docs>.

La base SQLite locale est créée dans `backend/finpilot.db`. Créez un compte depuis l'écran de connexion ; chaque nouvel espace reçoit les domaines et catégories de départ, sans client, transaction, budget ni objectif financier prérempli. Il n'existe pas de compte partagé ni de mot de passe de démonstration.

### Frontend

Dans un second terminal :

```powershell
cd frontend
npm install
npm run dev
```

Ouvrir <http://localhost:5173>. L’URL API peut être remplacée avec `VITE_API_URL` (valeur par défaut : `http://localhost:8000/api`).

La page de connexion charge le portrait depuis `frontend/public/assets/jeremie.webp` (80 Ko maximum). Si ce fichier n’est pas présent ou ne charge pas, elle affiche les initiales « JG » sur le fond dégradé. Pour activer le lien WhatsApp de la signature, définir `VITE_WHATSAPP_NUMBER` au format international, chiffres seulement ; `VITE_DEVELOPER_URL` peut aussi fournir une URL de portfolio.

La signature « Conçu et développé par Jérémie GASBEOGO » figure dans le pied de page, les exports PDF et CSV, et ce README.

### Docker Compose

```sh
docker compose up --build
```

### Hébergement gratuit

Le guide [docs/hebergement-gratuit.md](docs/hebergement-gratuit.md) décrit le déploiement de l'interface sur Cloudflare Pages, de l'API sur Render Free et de la base PostgreSQL sur Neon Free, avec les variables d'environnement nécessaires.

## Architecture

```text
backend/                 FastAPI, SQLAlchemy, Alembic, pandas
  app/main.py            Routes REST, authentification et documents
  app/models.py          Modèle relationnel
  app/schemas.py         Validation des entrées Pydantic
  app/analytics.py       KPI, prévisions et règles d’alerte
  app/seed.py            Catégories de départ sans clients ni chiffres fictifs
  tests/                 Tests pytest
frontend/                React, Vite, TypeScript, Tailwind
  src/pages/             Vues métier
  src/components/        Navigation, filtres, KPI, graphiques
docs/                    Architecture, KPI et dictionnaire
notebooks/               Analyse exploratoire locale, sans données embarquées
```

Les routes appliquent un filtre de propriété utilisateur. SQLite est le choix par défaut pour faciliter l'installation ; une URL PostgreSQL peut être configurée via `DATABASE_URL`. Alembic suit les changements du schéma. La clé JWT de développement doit être remplacée par `FINPILOT_SECRET_KEY` avant tout déploiement. Les pièces jointes sont conservées en base afin de résister aux redéploiements sur un serveur sans disque persistant.

## Définitions financières

FinPilot sépare les factures émises des mouvements d’argent. Le chiffre d’affaires encaissé et les charges payées sont calculés à partir des transactions réglées. Le CA facturé et les créances viennent des factures et de leurs paiements. Un paiement de facture crée une transaction d’encaissement liée, ce qui évite le double comptage. Les montants sont en FCFA entiers ; les taux et quantités sont des décimaux.

Les définitions détaillées et limites sont dans [docs/KPI.md](docs/KPI.md), les règles et hypothèses du moteur dans [docs/alert-engine.md](docs/alert-engine.md). Le schéma relationnel est dans [docs/architecture.md](docs/architecture.md), et le dictionnaire des champs dans [docs/data-dictionary.md](docs/data-dictionary.md).

## Tests

```powershell
cd backend
pytest
```

```powershell
cd frontend
npm test
```

Les tests backend couvrent les calculs de trésorerie, les scénarios de prévision, les règles d’alerte, le prix cible et le hachage des mots de passe.

## Choix techniques

- FastAPI et Pydantic v2 pour une API typée et une validation explicite.
- SQLAlchemy 2 avec UUID texte pour SQLite/PostgreSQL, clés étrangères activées et index sur utilisateur, période et filtres fréquents.
- pandas pour les regroupements périodiques et les séries de synthèse.
- React/TypeScript, React Router, TanStack Query et Recharts côté interface.
- ReportLab et openpyxl pour les documents PDF et Excel.

