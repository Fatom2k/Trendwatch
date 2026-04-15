# TrendWatch 🔭

> Agent de veille des tendances sociales — collecte automatisée, scoring IA, interface web et pipelines de contenu.

## Vue d'ensemble

TrendWatch surveille en continu les tendances émergentes sur les plateformes sociales et les moteurs de recherche. Il s'intègre dans un pipeline de création de contenu **dématérialisé** (posts, reels, threads) ou **matérialisé** (print-on-demand, merchandising).

```
Sources (TikTok, Google Trends, YouTube, Instagram, Twitter…)
    ↓
TrendWatchAgent  →  Scorer · Clusterer · Summarizer (Claude API)
    ↓
TrendStore (Elasticsearch)
    ↓
Importers (CSV, API)  ←→  Visualizers (dashboard web)
    ↓
Pipelines → Contenu digital / physique
```

---

## Démarrage rapide (Docker)

```bash
git clone https://github.com/fatom2k/trendwatch.git
cd trendwatch

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env (Auth0, clés API, domaine…)

# Démarrer tous les services
docker compose up -d

# Suivre les logs
docker compose logs -f web
```

L'interface web est disponible sur `https://DOMAIN` (HTTPS automatique via Caddy + Let's Encrypt).

> ⚠️ Ce projet tourne **exclusivement sur Docker Compose**. Ne pas lancer Python localement.

---

## Architecture

```
trendwatch/
├── agent/                  # Orchestrateur (scheduler + cycles de veille)
│   ├── core.py             # TrendWatchAgent.run()
│   └── scheduler.py        # APScheduler (horaire/quotidien/hebdo)
│
├── sources/                # Connecteurs API live (héritent BaseSource)
│   ├── base.py             # BaseSource (ABC) + Trend (dataclass)
│   ├── google_trends_v2.py # Google Trends — modes discovery / tracking
│   ├── tiktok.py
│   ├── instagram.py
│   ├── twitter.py
│   └── exploding_topics.py
│
├── importers/              # Imports déclenchés depuis l'UI
│   ├── base.py             # BaseImporter + BaseApiFetcher + contextes
│   ├── google_trends_csv.py# Import CSV Google Trends
│   └── youtube_viral.py    # Fetch YouTube Data API v3 (chart=mostPopular)
│
├── visualizers/            # Affichage par source dans le dashboard
│   ├── base.py             # BaseVisualizer + VizContext
│   ├── google_trends.py
│   └── youtube_viral.py
│
├── analysis/               # Traitement des tendances
│   ├── scorer.py           # Score multicritère 0–100
│   ├── clustering.py       # Regroupement thématique (TF-IDF + agglo)
│   └── summarizer.py       # Résumé IA via Claude API
│
├── storage/
│   └── elasticsearch.py    # TrendStore — index_trend / index_document / search
│
├── pipelines/
│   ├── content_digital.py  # Posts, reels, threads
│   └── content_physical.py # POD, merch
│
├── web/                    # Interface FastAPI
│   ├── app.py              # Factory + middleware session
│   ├── auth.py             # Auth0 OAuth + rôles admin/viewer
│   ├── routes/             # auth · trends · importer · admin · settings
│   └── templates/          # Jinja2 (base, dashboard, import, viz/…)
│
├── config/
│   └── settings.py         # Tous les paramètres depuis .env
│
├── scripts/
│   ├── migrate_env.sh      # Fusionne .env.example → .env sans écraser
│   ├── auto-deploy.sh      # Pull + rebuild si changement git détecté
│   ├── trendwatch-autodeploy.service
│   └── trendwatch-autodeploy.timer
│
├── caddy/
│   └── Caddyfile           # Reverse proxy + HTTPS Let's Encrypt
│
├── docs/                   # Documentation technique
└── tests/
```

---

## Services Docker

| Service | Rôle | Port interne |
|---|---|---|
| `elasticsearch` | Stockage des tendances | 9200 |
| `trendwatch` | Agent scheduler (cycles de veille) | — |
| `web` | Interface FastAPI + Uvicorn | 8000 |
| `caddy` | Reverse proxy HTTPS | 80/443 |

---

## Variables d'environnement principales

| Variable | Description |
|---|---|
| `DOMAIN` | Nom de domaine (ex. `app.trendwatch2k10.com`) |
| `AUTH0_DOMAIN` | Domaine Auth0 |
| `AUTH0_CLIENT_ID` | Client ID Auth0 |
| `AUTH0_CLIENT_SECRET` | Client Secret Auth0 |
| `AUTH0_CALLBACK_URL` | URL de callback OAuth |
| `ADMIN_EMAILS` | Emails admin (séparés par virgule) |
| `ALLOWED_EMAILS` | Emails viewer (vide = ouvert à tout compte Google) |
| `SESSION_SECRET` | Secret cookie (32+ caractères aléatoires) |
| `ANTHROPIC_API_KEY` | Claude API (résumés IA) |
| `YOUTUBE_API_KEY` | YouTube Data API v3 |
| `ELASTICSEARCH_HOST` | URL Elasticsearch (défaut: `http://elasticsearch:9200`) |
| `DEPLOY_TAG` | `dev` ou `prod` — pilote l'auto-deploy |

Voir `.env.example` pour la liste complète.

---

## Gestion des accès

- **admin** — accès complet (dashboard, import CSV, fetch API, admin panel)
- **viewer** — lecture seule (dashboard, visualisations)

Configurer via `ADMIN_EMAILS` et `ALLOWED_EMAILS` dans `.env`.  
Voir `docs/auth0_setup.md` pour la configuration Auth0.

---

## Sources de données

| Source | Type | Mode |
|---|---|---|
| Google Trends | `web_searches` | CSV upload ou API (discovery/tracking) |
| YouTube Viral | `social_video` | Fetch API v3 (chart=mostPopular) |
| TikTok | `social_video` | API Creative Center |
| Instagram | `social_hashtags` | Graph API + SISTRIX |
| Twitter/X | `news` | API v2 |
| Exploding Topics | `web_searches` | API REST |

---

## Ajouter un nouveau module

### Import CSV (fichier uploadé)
1. `importers/ma_source.py` → hérite `BaseImporter`
2. `visualizers/ma_source.py` → hérite `BaseVisualizer`
3. `web/templates/viz/ma_source.html`
4. Enregistrer dans `importers/__init__.py` et `visualizers/__init__.py`

### Fetch API (bouton dans l'UI)
1. `importers/ma_source.py` → hérite `BaseFetcher`
2. `visualizers/ma_source.py` → hérite `BaseVisualizer`
3. `web/templates/viz/ma_source.html`
4. Enregistrer dans `importers/__init__.py` (`_FETCHER_REGISTRY`) et `visualizers/__init__.py`

Voir `docs/adding_modules.md` pour le guide détaillé.

---

## Déploiement automatique

Le timer systemd vérifie les mises à jour git toutes les 5 minutes et redémarre les services si nécessaire.

```bash
# Installation (une seule fois sur le VPS)
sudo cp scripts/trendwatch-autodeploy.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trendwatch-autodeploy.timer

# Logs
journalctl -u trendwatch-autodeploy -f
```

`DEPLOY_TAG=dev` → suit la branche `dev`  
`DEPLOY_TAG=prod` → suit la branche `main`

---

## Migration .env

```bash
# Ajoute les nouvelles variables sans écraser les valeurs existantes
bash scripts/migrate_env.sh

# Prévisualisation sans modification
bash scripts/migrate_env.sh --dry-run
```

---

## Commandes utiles

```bash
docker compose ps                      # État des services
docker compose logs -f web             # Logs interface web
docker compose logs -f trendwatch      # Logs agent
docker compose exec web pytest         # Tests
docker compose up -d --build           # Rebuild après modif code
bash scripts/migrate_env.sh            # Mettre à jour .env
```

---

## Licence

MIT
