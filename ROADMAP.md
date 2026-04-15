# TrendWatch — Roadmap

## Phase 1 — Socle technique ✅

- [x] Architecture modulaire (sources, analysis, pipelines, storage)
- [x] `BaseSource` (ABC) + `Trend` dataclass
- [x] Connecteurs : Google Trends, TikTok, Instagram, Twitter, Exploding Topics
- [x] Google Trends V2 — modes `discovery` et `tracking`
- [x] Scoring multicritère 0–100 (demande / saturation / vélocité)
- [x] Clustering thématique (TF-IDF + AgglomerativeClustering)
- [x] Résumés IA via Claude API (`TrendSummarizer`)
- [x] Export rapports JSON + Markdown
- [x] APScheduler (cycles horaire / quotidien / hebdo)

## Phase 2 — Stockage et interface web ✅

- [x] `TrendStore` — Elasticsearch single-node (Docker)
- [x] Interface web FastAPI + Jinja2 + TailwindCSS
- [x] Authentification Google via Auth0 (OAuth2)
- [x] Rôles `admin` / `viewer` par whitelist email
- [x] Dashboard avec visualisations Chart.js par source
- [x] Formulaire d'ajout manuel de tendances (admin)
- [x] HTTPS automatique via Caddy + Let's Encrypt
- [x] `docker-compose.yml` — 4 services (ES, agent, web, caddy)

## Phase 3 — Imports et visualisations modulaires ✅

- [x] `BaseImporter` (ABC) + `ImportContext` — pattern imports fichiers
- [x] `GoogleTrendsCsvImporter` — détection de colonnes fuzzy
- [x] `BaseVisualizer` (ABC) + `VizContext` — pattern visualisations
- [x] `GoogleTrendsVisualizer` — tableau filtrable (geo, catégorie, période)
- [x] Route `GET /data?source=…` — dispatch générique par visualizer
- [x] Registres `importers/__init__.py` et `visualizers/__init__.py`
- [x] Import CSV Google Trends (page /import) — admin only

## Phase 4 — YouTube et déploiement continu ✅

- [x] `BaseFetcher` (ABC) + `FetchContext` — pattern fetch API live
- [x] `YouTubeApiFetcher` — YouTube Data API v3 `chart=mostPopular`
  - Périmètres : France (`regionCode=FR`) et Mondial
  - Champs : id, titre, chaîne, vues, likes, commentaires, tags, thumbnails
  - Snapshots horodatés pour suivi temporel
  - Gestion quota (100 unités/appel, warning 80%, QuotaExhaustedError 100%)
- [x] `YouTubeViralVisualizer` — grille de cards avec sélecteur de snapshots
- [x] Route `POST /import/fetch` — déclenchement manuel (admin only)
- [x] Auto-deploy systemd (timer 5 min, tag `dev`/`prod`)
- [x] `scripts/migrate_env.sh` — migration .env sans perte

## Phase 5 — Consolidation et qualité 🔄 (en cours)

- [ ] Tests automatiques dans `auto-deploy.sh` (bloquer si pytest KO)
- [ ] Tests unitaires pour `importers/` et `visualizers/`
- [ ] Sources/youtube_viral.py — intégration dans le scheduler agent
- [ ] Connecteur Trakt.tv (streaming Netflix/Prime)
- [ ] Page d'exploration des tendances avec filtres avancés
- [ ] Comparaison de snapshots YouTube (delta vues entre deux fetches)
- [ ] Rapport HTML statique avec graphiques exportable

## Phase 6 — Pipelines de contenu 📋

- [ ] Génération de briefs de contenu (Markdown structuré)
- [ ] Génération de scripts Reels / TikToks via Claude API
- [ ] Génération de threads X avec hashtags optimisés
- [ ] Génération de légendes Instagram
- [ ] Webhook de sortie configurable
- [ ] Intégration no-code (Zapier / Make)

## Phase 7 — Contenu physique (POD / Shops) 📋

- [ ] Suggestion de niche produit basée sur les tendances
- [ ] Briefs de design pour print-on-demand
- [ ] Intégration Printful API
- [ ] Intégration Printify API
- [ ] Intégration Shopify (publication automatique)
- [ ] Dashboard tendances → ventes

---

## Versions

| Version | Contenu |
|---|---|
| `v0.1.0` | Interface web, Auth0, Elasticsearch, CSV import |
| `v0.2.0` | Modularisation imports/visualizers |
| `v0.2.1` | Auto-deploy systemd |
| `v0.3.0` | YouTube Viral Videos (BaseFetcher) |

> Les phases sont itératives. La validation terrain conditionne les priorités.
