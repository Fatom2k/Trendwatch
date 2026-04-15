#!/usr/bin/env bash
# scripts/auto-deploy.sh — Vérifie les mises à jour Git et redémarre les services si nécessaire.
#
# Piloté par DEPLOY_TAG dans .env :
#   DEPLOY_TAG=dev   → surveille la branche "dev"
#   DEPLOY_TAG=prod  → surveille la branche "main"
#
# Conçu pour être exécuté par un timer systemd toutes les N minutes.
# Un fichier verrou (/tmp/trendwatch-deploy.lock) empêche les exécutions simultanées.
#
# Usage manuel :
#   bash scripts/auto-deploy.sh
#   bash scripts/auto-deploy.sh --force   # force le redémarrage même sans changement

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
LOG_FILE="$PROJECT_DIR/logs/auto-deploy.log"
LOCK_FILE="/tmp/trendwatch-deploy.lock"
FORCE=false

for arg in "$@"; do
  [[ "$arg" == "--force" ]] && FORCE=true
done

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  local level="$1"; shift
  local msg="$*"
  local ts; ts=$(date '+%Y-%m-%dT%H:%M:%S')
  echo "[$ts] [$level] $msg" | tee -a "$LOG_FILE"
}

# ---------------------------------------------------------------------------
# Verrou — une seule instance à la fois
# ---------------------------------------------------------------------------

if [ -e "$LOCK_FILE" ]; then
  pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    log "WARN" "Déploiement déjà en cours (PID $pid). Abandon."
    exit 0
  else
    log "WARN" "Verrou obsolète supprimé."
    rm -f "$LOCK_FILE"
  fi
fi

echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ---------------------------------------------------------------------------
# Chargement du .env (lecture seule — on ne modifie pas l'environnement du shell)
# ---------------------------------------------------------------------------

if [[ ! -f "$ENV_FILE" ]]; then
  log "ERROR" "$ENV_FILE introuvable. Lance ce script depuis la racine du projet."
  exit 1
fi

get_env() {
  local key="$1"
  local default="${2:-}"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' || echo "$default"
}

DEPLOY_TAG=$(get_env "DEPLOY_TAG" "dev")

# Résolution branche ← tag
case "$DEPLOY_TAG" in
  prod)    BRANCH="main" ;;
  dev)     BRANCH="dev"  ;;
  *)       BRANCH="$DEPLOY_TAG" ;;   # valeur libre : nom de branche direct
esac

log "INFO" "Tag=$DEPLOY_TAG → branche=$BRANCH (répertoire=$PROJECT_DIR)"

# ---------------------------------------------------------------------------
# Vérification des mises à jour
# ---------------------------------------------------------------------------

cd "$PROJECT_DIR"

# S'assurer qu'on est sur la bonne branche
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
  log "INFO" "Basculement de '$CURRENT_BRANCH' vers '$BRANCH'."
  git checkout "$BRANCH" >> "$LOG_FILE" 2>&1
fi

# Fetch sans modifier le dépôt local
git fetch origin "$BRANCH" >> "$LOG_FILE" 2>&1

LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(git rev-parse "origin/$BRANCH")

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]] && [[ "$FORCE" == "false" ]]; then
  log "INFO" "Aucun changement détecté (HEAD=$LOCAL_SHA). Rien à faire."
  exit 0
fi

if [[ "$FORCE" == "true" ]]; then
  log "INFO" "Redémarrage forcé (--force)."
else
  log "INFO" "Changement détecté : local=$LOCAL_SHA → remote=$REMOTE_SHA"
fi

# ---------------------------------------------------------------------------
# Déploiement
# ---------------------------------------------------------------------------

log "INFO" "=== Début du déploiement ==="

# 1. Pull
log "INFO" "git pull origin $BRANCH"
git pull origin "$BRANCH" >> "$LOG_FILE" 2>&1

NEW_SHA=$(git rev-parse HEAD)
log "INFO" "HEAD mis à jour : $NEW_SHA"

# 2. Rebuild et redémarrage des services Docker Compose
log "INFO" "docker compose up -d --build"
docker compose up -d --build >> "$LOG_FILE" 2>&1

# 3. Attente courte puis vérification de santé
sleep 5
RUNNING=$(docker compose ps --services --filter "status=running" 2>/dev/null | wc -l | tr -d ' ')
log "INFO" "$RUNNING service(s) en cours d'exécution après déploiement."

log "INFO" "=== Déploiement terminé (SHA=$NEW_SHA) ==="
