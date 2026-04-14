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

### Elasticsearch Setup

- Docker container in `docker-compose.yml` with security disabled (dev/test only).
- `elasticsearch_host` is `http://localhost:9200` locally, `http://elasticsearch:9200` in containers.
- Health check ensures the index exists before agent startup.

### Environment Variables

Required for full operation:
- `ANTHROPIC_API_KEY` — Claude API
- `TIKTOK_API_KEY`, `TWITTER_BEARER_TOKEN`, `INSTAGRAM_ACCESS_TOKEN` — Social APIs
- `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` — Web OAuth
- Optional: `ELASTICSEARCH_HOST`, `SCHEDULE_CADENCE`, `SCHEDULE_TIME`, `TIMEZONE`

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

## Development Patterns

### Adding a New Source

1. Inherit from `BaseSource` in a new file, e.g. `sources/youtube.py`.
2. Implement `fetch()`, `normalize()`, `to_trend()`.
3. Register in `config/settings.py` and `agent/core.py._build_sources()`.
4. Add tests in `tests/test_sources.py`.

### Modifying the Score

Edit `analysis/scorer.py`. The score combines demand, saturation, and velocity into a 0–100 scale. Retest with `pytest tests/test_scorer.py`.

### Testing

- Unit tests in `tests/` use mocks for external APIs.
- Integration tests patch `_build_sources()` to inject mock data.
- No real API calls in tests; use fixtures or `MagicMock`.

### Web Routes

Routes in `web/routes/` are registered in `web/app.py`. Template responses require the `context=` parameter (Starlette 0.29+ compatibility).

## Common Git Patterns

Recent commits show:
- `fix:` for bug fixes (e.g., Jinja2 cache fixes, Starlette signature updates)
- `feat:` for new features (e.g., web interface, Elasticsearch storage)
- `chore:` for configuration and tooling

Commit messages are terse and action-oriented.
