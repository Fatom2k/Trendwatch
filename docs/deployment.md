# Deployment Guide

This guide covers deploying TrendWatch on a VPS with HTTPS, auto-deploy, and production hardening.

## Prerequisites

- VPS with Ubuntu 22.04+ (2 GB RAM minimum, 4 GB recommended)
- Domain name with DNS A record pointing to the VPS
- SSH access to the VPS
- Docker and Docker Compose installed

## 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in to apply group change
```

## 2. Clone the Repository

```bash
git clone https://github.com/fatom2k/trendwatch.git
cd trendwatch
```

## 3. Configure Environment

```bash
# Copy example and fill in your values
cp .env.example .env
nano .env
```

Required variables for production:

```env
DOMAIN=app.trendwatch2k10.com

# Auth0 (see docs/auth0_setup.md)
AUTH0_DOMAIN=trendwatch.eu.auth0.com
AUTH0_CLIENT_ID=...
AUTH0_CLIENT_SECRET=...
AUTH0_CALLBACK_URL=https://app.trendwatch2k10.com/auth/callback

# Access control
ADMIN_EMAILS=you@gmail.com
ALLOWED_EMAILS=

# Session security (generate with: openssl rand -hex 32)
SESSION_SECRET=your_long_random_secret_here

# API keys
ANTHROPIC_API_KEY=sk-ant-...
YOUTUBE_API_KEY=AIza...

# Deployment
DEPLOY_TAG=prod
```

## 4. Start Services

```bash
docker compose up -d
docker compose ps        # All services should be "running" or "healthy"
docker compose logs -f web
```

Caddy automatically provisions HTTPS via Let's Encrypt. The first startup may take 30–60 seconds for certificate issuance.

Visit `https://your-domain.com` — you should see the TrendWatch login page.

## 5. Auto-Deploy (Systemd Timer)

The auto-deploy system polls git every 5 minutes and rebuilds when changes are detected.

```bash
# Install systemd units
sudo cp scripts/trendwatch-autodeploy.service /etc/systemd/system/
sudo cp scripts/trendwatch-autodeploy.timer   /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now trendwatch-autodeploy.timer

# Verify
sudo systemctl status trendwatch-autodeploy.timer
journalctl -u trendwatch-autodeploy -f
```

Deploy behavior is controlled by `DEPLOY_TAG` in `.env`:
- `DEPLOY_TAG=prod` — follows branch `main`
- `DEPLOY_TAG=dev` — follows branch `dev`

### How it works

1. `auto-deploy.sh` runs every 5 minutes
2. It reads `DEPLOY_TAG` and maps it to the correct branch
3. If `git fetch` detects new commits → `git pull` + `docker compose up -d --build`
4. A lock file (`/tmp/trendwatch-deploy.lock`) prevents overlapping runs
5. Logs go to `logs/auto-deploy.log` and journald

## 6. Migrate Environment Variables

When new variables are added to `.env.example`, run the migration script to add them to your existing `.env` without overwriting current values:

```bash
# Preview changes
bash scripts/migrate_env.sh --dry-run

# Apply
bash scripts/migrate_env.sh
```

## 7. Updating to a New Version

### Manual update

```bash
git pull origin main
docker compose up -d --build
```

### Automatic (via auto-deploy)

Push to the branch tracked by `DEPLOY_TAG`. The timer picks it up within 5 minutes.

## 8. Backups

Elasticsearch data lives in the `elasticsearch-data` Docker volume. Back it up with:

```bash
docker run --rm \
  --volumes-from $(docker compose ps -q elasticsearch) \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/es-data-$(date +%Y%m%d).tar.gz /usr/share/elasticsearch/data
```

## Troubleshooting

### Web container fails to start
```bash
docker compose logs web
```
Common causes: missing `.env` variables, Auth0 misconfiguration, port conflict.

### Caddy shows "certificate pending"
- DNS A record not yet propagated (wait up to 1 hour)
- Let's Encrypt rate limits (max 5 certs/domain/week)

### Elasticsearch not healthy
```bash
docker compose logs elasticsearch
```
Increase Docker memory limit if container OOMs (ES needs ~1 GB).

### Auto-deploy not running
```bash
sudo systemctl status trendwatch-autodeploy.timer
sudo systemctl status trendwatch-autodeploy.service
journalctl -u trendwatch-autodeploy --since "1 hour ago"
```
