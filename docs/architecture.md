# Architecture Reference

## System Overview

```
External APIs / Files
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                   Data Ingestion                       │
│                                                       │
│  BaseSource (sources/)      BaseFetcher (importers/)  │
│  └─ background scheduler    └─ UI-triggered API call  │
│                                                       │
│  BaseImporter (importers/)                            │
│  └─ file upload (CSV)                                 │
└──────────────────────┬────────────────────────────────┘
                       │ index_document() / index_trend()
                       ▼
             ┌──────────────────┐
             │   TrendStore     │
             │  (Elasticsearch) │
             └────────┬─────────┘
                      │ search_documents()
                      ▼
┌───────────────────────────────────────────────────────┐
│                  Web Interface                         │
│                                                       │
│  GET /data?source=X  →  BaseVisualizer.fetch_data()  │
│                      →  Jinja2 template               │
│                                                       │
│  POST /import/csv    →  BaseImporter pipeline         │
│  POST /import/fetch  →  BaseFetcher pipeline          │
└───────────────────────────────────────────────────────┘
```

## Module Map

```
trendwatch/
├── agent/
│   ├── core.py           TrendWatchAgent — collect → score → cluster → summarize → store
│   └── scheduler.py      APScheduler — hourly/daily/weekly cycles
│
├── sources/              Background data connectors (BaseSource)
│   ├── base.py           BaseSource (ABC) + Trend (dataclass)
│   ├── google_trends_v2.py
│   ├── tiktok.py
│   ├── instagram.py
│   ├── twitter.py
│   └── exploding_topics.py
│
├── importers/            UI-triggered data ingestion
│   ├── base.py           BaseImporter + BaseFetcher + contexts + QuotaExhaustedError
│   ├── __init__.py       _FILE_REGISTRY + _FETCHER_REGISTRY + get_*/list_* helpers
│   ├── google_trends_csv.py  GoogleTrendsCsvImporter (BaseImporter)
│   └── youtube_viral.py  YouTubeApiFetcher (BaseFetcher)
│
├── visualizers/          Dashboard display modules
│   ├── base.py           BaseVisualizer (ABC) + VizContext
│   ├── __init__.py       _REGISTRY + get_visualizer() + list_visualizers()
│   ├── google_trends.py  GoogleTrendsVisualizer
│   └── youtube_viral.py  YouTubeViralVisualizer
│
├── analysis/
│   ├── scorer.py         TrendScorer — composite 0–100 score
│   ├── clustering.py     TrendClusterer — TF-IDF + AgglomerativeClustering
│   └── summarizer.py     TrendSummarizer — Claude API (Anthropic SDK)
│
├── storage/
│   └── elasticsearch.py  TrendStore — index_trend / index_document / search_documents
│
├── pipelines/
│   ├── content_digital.py   Posts, reels, threads
│   └── content_physical.py  POD, merch briefs
│
├── web/
│   ├── app.py            FastAPI factory + session middleware
│   ├── auth.py           Auth0 OAuth + login_required / admin_required guards
│   ├── templates_config.py  Jinja2Templates singleton
│   └── routes/
│       ├── auth.py       /auth/login, /auth/callback, /auth/logout
│       ├── trends.py     GET /  (dashboard)  +  GET /data  (visualizers)
│       ├── importer.py   GET /import  +  POST /import/csv  +  POST /import/fetch
│       ├── admin.py      GET/POST /admin  (admin panel)
│       └── settings.py   GET /settings
│
├── config/
│   └── settings.py       All settings from .env — Settings class (property accessors)
│
├── scripts/
│   ├── auto-deploy.sh    git poll + docker compose up --build
│   ├── migrate_env.sh    Non-destructive .env migration
│   ├── trendwatch-autodeploy.service
│   └── trendwatch-autodeploy.timer
│
├── caddy/
│   └── Caddyfile         Reverse proxy — HTTPS via Let's Encrypt
│
├── docs/
│   ├── architecture.md   (this file)
│   ├── adding_modules.md Developer guide — BaseImporter / BaseFetcher / BaseVisualizer
│   ├── deployment.md     VPS deployment + systemd auto-deploy
│   ├── auth0_setup.md    Auth0 + Google OAuth configuration
│   └── auth0_action.js   Auth0 post-login Action (role enrichment)
│
├── tests/
├── donnees/
│   ├── samples/          Example CSV files
│   └── uploads/          User uploads (gitignored)
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── CLAUDE.md
```

## Data Flow — CSV Import

```
User uploads CSV (POST /import/csv)
    │
    ▼
admin_required() guard
    │
    ▼
get_importer(source) → GoogleTrendsCsvImporter
    │
    ▼
importer.validate(file_path, context) → [] or [errors]
    │
    ▼
importer.parse_rows(file_path) → Iterator[Dict]
    │
    ▼
for each row:
    importer.build_document(row, idx, context) → ES document
    store.index_document(doc)
    │
    ▼
JSONResponse {"success": true, "count": N}
```

## Data Flow — API Fetch (YouTube)

```
User clicks "Fetch" (POST /import/fetch)
    │
    ▼
admin_required() guard
    │
    ▼
get_fetcher(source) → YouTubeApiFetcher
    │
    ▼
fetcher.validate_context(context) → [] or [errors]
    │
    ▼
fetcher.fetch(context)
    → YouTube Data API v3 videos.list(chart=mostPopular)
    → quota check (warn at 80%, raise QuotaExhaustedError at 100%)
    │
    ▼
for each video:
    fetcher.build_document(item, idx, context) → ES document
    store.index_document(doc)
    │
    ▼
JSONResponse {"success": true, "count": N, "quota_used": M}
```

## Data Flow — Dashboard Visualisation

```
User navigates to /data?source=youtube_viral&geo=FR
    │
    ▼
login_required() guard
    │
    ▼
get_visualizer(source) → YouTubeViralVisualizer
    │
    ▼
VizContext(source, data_category, geo, size, ...)
    │
    ▼
visualizer.fetch_data(store, context)
    → store.search_documents(_data_source=youtube_viral, _geo=FR)
    → deduplicate snapshot_dates
    │
    ▼
TemplateResponse("viz/youtube_viral.html", context)
```

## Authentication & Authorisation

```
Request
    │
    ├─ login_required() — redirects to /auth/login if no session
    │
    └─ admin_required() — returns 403 JSON or redirect if role != "admin"

Roles are resolved at login:
    user.email in ADMIN_EMAILS  → role = "admin"
    user.email in ALLOWED_EMAILS (or ALLOWED_EMAILS empty) → role = "viewer"
    otherwise → 403 Forbidden
```

Session stored in signed cookie (`itsdangerous`, key = `SESSION_SECRET`).

## Elasticsearch Index Structure

Index name: `trendwatch_trends` (configurable via `ELASTICSEARCH_INDEX`)

All documents share the unified envelope:

```json
{
  "_data_source":   "youtube_viral",
  "_data_category": "trending",
  "_geo":           "FR",
  "_imported_at":   "2026-04-15T10:00:00Z",
  "_snapshot_at":   "2026-04-15T10:00:00Z",
  "title":          "Video Title",
  "trend":          12345678,
  "data": {
    "video_id":      "abc123",
    "channel_title": "Channel Name",
    "view_count":    12345678,
    "like_count":    450000,
    "comment_count": 12000,
    "thumbnail_url": "https://...",
    "rank":          1
  }
}
```

`TrendStore.search_documents()` filters on `.keyword` sub-fields and sorts by `trend` descending.

## Docker Services

| Service | Image | Role | Port |
|---------|-------|------|------|
| `elasticsearch` | `elasticsearch:8.13.0` | Data store | 9200 (internal) |
| `trendwatch` | local Dockerfile | Agent scheduler | — |
| `web` | local Dockerfile | FastAPI + Uvicorn | 8000 (internal) |
| `caddy` | `caddy:2` | HTTPS reverse proxy | 80, 443 |

All services share a `trendwatch` Docker network. Only Caddy is exposed externally.
