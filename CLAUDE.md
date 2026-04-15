# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Important: Docker/Docker Compose Deployment

This project **runs entirely on Docker/Docker Compose**. Do NOT attempt local Python setup, venv, or local server launches. Always:
- Use `docker compose` commands to start/stop services
- Check `docker logs` for errors, not local console
- Rebuild images after code changes with `docker compose up -d --build`
- Never run pip/python commands in local shell (the virtualenv is inside containers)

## Quick Start Commands

**⚠️ This project runs on Docker/Docker Compose, not locally.**

```bash
# Full stack start/stop
docker compose up -d         # Start all services
docker compose down          # Stop all services
docker compose logs -f web   # Follow web server logs
docker compose logs -f agent # Follow agent logs
docker compose ps            # List running containers

# Rebuild after code changes
docker compose down
docker compose up -d --build

# Run tests in Docker
docker compose exec web pytest
docker compose exec web pytest -v
docker compose exec web pytest --cov=agent --cov=sources --cov=analysis
```

**Local development** (if needed):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest  # Run tests locally
```

## Architecture Overview

The project implements an intelligent trend-watching pipeline from data collection to content generation:

```
Sources (TikTok, Instagram, Twitter, Google Trends)
    ↓
TrendWatchAgent (orchestrator: collect → analyze → score → report)
    ├─ TrendClusterer (group by theme)
    ├─ TrendScorer (score on demand/saturation/velocity)
    ├─ TrendSummarizer (AI insights via Claude API)
    └─ ReportWriter (JSON + Markdown output)
    ↓
TrendStore (Elasticsearch persistence)
    ↓
Pipelines (content_digital.py, content_physical.py)
    ↓
Web Interface (FastAPI + Auth0 + HTML templates)
```

### Core Modules

- **`agent/core.py`** — `TrendWatchAgent`: Main orchestrator. Call `run()` to execute one full cycle.
- **`agent/scheduler.py`** — `TrendWatchScheduler`: APScheduler wrapper for hourly/daily/weekly cadence.
- **`sources/`** — Platform connectors. All inherit from `BaseSource` and implement `fetch()`, `normalize()`, `to_trend()`.
- **`analysis/`** — `TrendScorer` (composite 0–100 score), `TrendClusterer` (thematic grouping), `TrendSummarizer` (Claude API).
- **`storage/`** — `TrendStore` abstracts Elasticsearch; single-node Docker container for dev/test.
- **`config/settings.py`** — Centralised settings from `.env` with sensible defaults.
- **`web/app.py`** — FastAPI application factory. Routes in `web/routes/`.
- **`pipelines/`** — Consume scored trends and route to digital (posts/reels) or physical (POD/merch).

### Key Data Model

**`Trend`** (in `sources/base.py`) is the common currency:
- Platform, topic, hashtags, score (0–100)
- Demand (volume, growth_rate), saturation (creator_count, age), velocity (daily_growth, acceleration)
- `detected_at` (UTC), `suggested_formats`, `pipeline_target` ("digital" or "physical")
- Optional: `cluster_id`, `summary`, `raw` payload

Sources produce `Trend` objects → scorer enriches them → pipelines consume them.

## Important Technical Notes

### Jinja2 Version Pin

Requirements pins `jinja2==3.1.3` because version 3.1.4 has a cache-key bug with Starlette's globals (unhashable dict). Do not upgrade without testing the web interface thoroughly.

### Claude API Integration

- `TrendSummarizer` uses the Anthropic SDK to generate actionable trend insights.
- Set `ANTHROPIC_API_KEY` in `.env`.
- All Claude calls are in `analysis/summarizer.py`.

### Google Trends V2 (Discovery + Keyword Tracking)

**⚠️ IMPORTANT: GoogleTrendsV2 has two distinct modes** (configured via `GOOGLE_TRENDS_MODE` in `.env`):

1. **DISCOVERY mode** (default: `GOOGLE_TRENDS_MODE=discovery`)
   - Auto-discovers emerging trends by comparing 37 seed topics
   - Returns only trends with >30% growth (configurable in `sources/google_trends_v2.py`)
   - No keyword pre-configuration needed
   - Best for: Finding new trends organically

2. **TRACKING mode** (`GOOGLE_TRENDS_MODE=tracking`)
   - Monitors specific keywords from `GOOGLE_TRENDS_KEYWORDS` setting
   - Returns all tracked keywords with their current growth rates
   - Best for: Monitoring known trends and measuring momentum

**Switch modes in `.env`:**
```env
GOOGLE_TRENDS_MODE=discovery   # Auto-discover new trends (default)
# OR
GOOGLE_TRENDS_MODE=tracking    # Track specific keywords
```

**Note:** Old `GoogleTrendsSource` (sources/google_trends.py) relied on pytrends `trending_searches()` endpoint which Google deprecated. Use `GoogleTrendsV2Source` instead.

### Elasticsearch Setup

- Docker container in `docker-compose.yml` with security disabled (dev/test only).
- `elasticsearch_host` is `http://localhost:9200` locally, `http://elasticsearch:9200` in containers.
- Health check ensures the index exists before agent startup.

### Environment Variables & Secrets

**⚠️ NEVER commit `.env`** — it contains API keys and secrets. Use `.env.example` as template.

Required for full operation:
- `ANTHROPIC_API_KEY` — Claude API
- `TIKTOK_API_KEY`, `TWITTER_BEARER_TOKEN`, `INSTAGRAM_ACCESS_TOKEN` — Social APIs
- `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` — Web OAuth
- Optional: `ELASTICSEARCH_HOST`, `SCHEDULE_CADENCE`, `SCHEDULE_TIME`, `TIMEZONE`

**Auth0 Setup (Critical):**
1. Create account at https://auth0.com (free tier)
2. Create Application → Regular Web Application
3. Enable Google social connection
4. In Application Settings, configure **Allowed Callback URLs**:
   - Set in Auth0 Dashboard: `https://your-domain.com/auth/callback`
   - Set in `.env`: `AUTH0_CALLBACK_URL=https://your-domain.com/auth/callback`
   - **MUST match exactly** (protocol, domain, port, path) or OAuth will fail with "Callback URL mismatch"
5. After `.env` changes, restart container: `docker compose down web && docker compose up -d web`

See `.env.example` for all options and defaults.

### Web Interface (FastAPI)

- Runs on port 8000 (uvicorn).
- Auth0 OAuth2 integration in `web/routes/auth.py`.
- Role-based access control (`admin`, `viewer`) via email whitelist.
- Jinja2 templates in `web/templates/`. Base layout extends all pages.
- Static files in `web/static/` (CSS, JS).
- Session middleware uses signed cookies.

### Docker & Compose

- `Dockerfile`: Python 3.11, installs requirements, runs scheduler by default.
- `docker-compose.yml`: Four services (elasticsearch, trendwatch agent, web, caddy reverse proxy).
- Caddy auto-provisions HTTPS via Let's Encrypt. Domain from `$DOMAIN` env var.

### Data Sources & Content Types

Each source collector captures a specific **content category**. This allows filtering and analysis by type:

**Supported Content Types:**
- `web_searches` — General web search queries (Google Trends, Exploding Topics)
- `social_video` — Video trends from TikTok, Instagram Reels, YouTube Shorts
- `social_hashtags` — Hashtag popularity (TikTok, Instagram)
- `streaming` — Streaming platform trending content (Netflix via Trakt.tv, YouTube)
- `shopping` — E-commerce and product trending (Google Shopping Trends)
- `news` — News and current events trending (Google News Trends, Twitter)

**Configured Sources (`.env` → `ACTIVE_PLATFORMS`):**
- **google_trends** (web_searches) — Top 50 searches (mock mode for dev, RapidAPI for prod)
- **tiktok** (social_video) — Trending hashtags via TikTok Creative Center API
- **instagram** (social_hashtags) — Hashtag popularity via Graph API + SISTRIX
- **twitter** (news) — Trending topics and hashtags
- **exploding_topics** (web_searches) — Rapidly growing search queries
- **trakt** (streaming, planned) — Netflix/streaming trending shows via Trakt.tv API

**CSV Import:**
- Upload CSV files via **`http://localhost:8000/import/csv`**
- Supports Google Trends exports (Title, Value, Traffic, etc.)
- Auto-detects column names (flexible parsing)
- Saves to `donnees/uploads/` and stores directly in Elasticsearch

**Directory Structure - Data Management:**
```
donnees/
├── samples/          ← Example CSV files (for testing/reference)
│   └── example_trends_FR.csv
├── uploads/          ← User-uploaded CSV files (not committed)
└── exports/          ← Generated reports and exports (optional)
```

**Netflix / Streaming Strategy:**
- **Recommendation:** Use **Trakt.tv API** (free, reliable)
  - Endpoint: https://api.trakt.tv/shows/trending
  - Returns: Trending shows with watcher count, play count
  - No auth required; rate limited at 1000 req/hour
  - Covers Netflix, Hulu, Prime Video, and more
  - Implementation pattern: `sources/trakt.py` (to be created as example)

### Unified Document Structure (Elasticsearch)

**All imported documents in Elasticsearch follow a standardized structure with mandatory fields:**

```json
{
  "_data_category": "terms",        // Data category (terms, trending, news, etc.)
  "_data_source": "google_trends",  // Source platform
  "_geo": "FR",                      // Geographic location
  "_imported_at": "2026-04-15T...", // UTC timestamp of import
  
  "data": { /* raw CSV data */ },   // Original/raw data from import
  "title": "query string",           // Human-readable title/topic
  "trend": 150,                      // Numeric trend value (growth %, rank, etc.)
  
  // Optional metadata
  "_csv_source": "filename.csv",
  "_search_type": "web",
  "_time_range": "hours",
  "_csv_row_index": 1
}
```

**How `title` and `trend` are extracted by category:**
- **terms** — `title`: Query column, `trend`: Increase percent (as integer)
- **trending** — *(to be specified)*
- **news** — *(to be specified)*
- Other categories — *(to be specified)*

## Development Patterns

### Adding a New Source

Each source collector captures one **content type**. Supported types:

| Type | Description | Example Sources |
|------|-------------|-----------------|
| `web_searches` | General web search queries | Google Trends, Exploding Topics |
| `social_video` | Video content trends | TikTok, Instagram Reels, YouTube Shorts |
| `social_hashtags` | Hashtag popularity | TikTok, Instagram |
| `streaming` | Streaming platform content | Netflix (via Trakt.tv), YouTube |
| `shopping` | E-commerce & product trends | Google Shopping |
| `news` | News & current events | Google News, Twitter |

**Steps to add a new source:**

1. Create `sources/your_platform.py` inheriting from `BaseSource`.
2. Implement three methods:
   ```python
   def fetch(self) -> List[Dict[str, Any]]:
       """Retrieve raw data from API/scraper."""

   def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
       """Convert to common dict with 'topic', 'hashtags', demand/saturation/velocity."""

   def to_trend(self, normalized: Dict[str, Any]) -> Trend:
       """Convert to Trend object, specifying content_type."""
       return Trend(
           platform="your_platform",
           topic=normalized["topic"],
           hashtags=normalized["hashtags"],
           content_type="web_searches",  # ← KEY: specify type here
           demand=normalized["demand"],
           saturation=normalized["saturation"],
           velocity=normalized["velocity"],
           # ... other fields
       )
   ```
3. Register in `config/settings.py` (add API key settings).
4. Register in `agent/core.py._build_sources()` (add to active platform check).
5. Add tests in `tests/test_sources.py` using mocks.

### Modifying the Score

Edit `analysis/scorer.py`. The score combines demand, saturation, and velocity into a 0–100 scale. Retest with `pytest tests/test_scorer.py`.

### Testing

- Unit tests in `tests/` use mocks for external APIs.
- Integration tests patch `_build_sources()` to inject mock data.
- No real API calls in tests; use fixtures or `MagicMock`.

### Web Routes & Templates

Routes in `web/routes/` are registered in `web/app.py`. 

**Jinja2Templates.TemplateResponse signature (Starlette 0.29+):**
```python
# Correct: request must be FIRST argument, then name, then context (positional)
templates.TemplateResponse(request, "template.html", {"request": request})

# Wrong: these will fail
templates.TemplateResponse("template.html", {"request": request})
templates.TemplateResponse("template.html", context={"request": request})
```

**⚠️ IMPORTANT: All web pages must pass user context to templates:**

Every template response must include both `request` AND `user` in the context dict so that:
- The navbar renders correctly (displays user info, role badge, admin/import links)
- Auth guards can be enforced at the template level
- User session info is consistently available across all pages

```python
from web.auth import get_current_user

user = get_current_user(request)
return templates.TemplateResponse(
    request,
    "template.html",
    {
        "request": request,
        "user": user,  # ← Always include this
        # ... other context
    },
)
```

All pages extend `base.html`, which expects `user` in the context for proper navbar rendering.

## Common Git Patterns

Recent commits show:
- `fix:` for bug fixes (e.g., Jinja2 cache fixes, Starlette signature updates)
- `feat:` for new features (e.g., web interface, Elasticsearch storage)
- `chore:` for configuration and tooling

Commit messages are terse and action-oriented.
