#!/usr/bin/env bash
# scripts/migrate_env.sh — Fusionne .env.example dans .env sans écraser les valeurs existantes.
#
# Usage (depuis la racine du projet) :
#   bash scripts/migrate_env.sh
#   bash scripts/migrate_env.sh --dry-run   # prévisualise sans modifier .env
#
# Règles :
#   - Clé déjà présente dans .env  → conservée telle quelle
#   - Clé absente de .env           → ajoutée avec la valeur par défaut de .env.example
#   - Commentaires / sections        → ajoutés uniquement avant une clé nouvelle

set -euo pipefail

ENV_FILE=".env"
EXAMPLE_FILE=".env.example"
BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
DRY_RUN=false

for arg in "$@"; do
  [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
done

# --- Vérifications ---
if [[ ! -f "$EXAMPLE_FILE" ]]; then
  echo "❌ $EXAMPLE_FILE introuvable. Lance ce script depuis la racine du projet."
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "⚠️  $ENV_FILE absent — copie directe de $EXAMPLE_FILE."
  $DRY_RUN || cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo "✅ $ENV_FILE créé."
  exit 0
fi

# --- Sauvegarde avant modification ---
if ! $DRY_RUN; then
  cp "$ENV_FILE" "$BACKUP_FILE"
  echo "💾 Sauvegarde créée : $BACKUP_FILE"
fi

# --- Indexer les clés déjà présentes dans .env ---
declare -A existing_keys
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line//[[:space:]]/}" ]]  && continue
  key=$(echo "$line" | cut -d'=' -f1 | tr -d ' ')
  [[ -n "$key" ]] && existing_keys["$key"]=1
done < "$ENV_FILE"

# --- Fusion .env.example → .env ---
added=0
pending_comments=""

if $DRY_RUN; then
  echo ""
  echo "[DRY-RUN] Clés qui seraient ajoutées à $ENV_FILE :"
fi

while IFS= read -r line || [[ -n "$line" ]]; do

  # Ligne vide ou commentaire — mémoriser pour les insérer avant la prochaine clé ajoutée
  if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line//[[:space:]]/}" ]]; then
    pending_comments+="${line}"$'\n'
    continue
  fi

  key=$(echo "$line" | cut -d'=' -f1 | tr -d ' ')
  [[ -z "$key" ]] && { pending_comments=""; continue; }

  if [[ -v existing_keys["$key"] ]]; then
    # Clé déjà présente — ne rien faire
    pending_comments=""
  else
    # Nouvelle clé
    if $DRY_RUN; then
      echo "  + $line"
    else
      # Séparateur si le fichier ne se termine pas par une ligne vide
      [[ $(tail -c1 "$ENV_FILE" | wc -c) -gt 0 ]] && echo "" >> "$ENV_FILE"
      printf '%s' "$pending_comments" >> "$ENV_FILE"
      echo "$line" >> "$ENV_FILE"
    fi
    ((added++)) || true
    pending_comments=""
  fi

done < "$EXAMPLE_FILE"

# --- Résumé ---
echo ""
if $DRY_RUN; then
  echo "[DRY-RUN] $added clé(s) seraient ajoutées — aucune modification effectuée."
else
  if [[ $added -eq 0 ]]; then
    echo "✅ $ENV_FILE est déjà à jour. Aucune clé ajoutée."
    rm -f "$BACKUP_FILE"
  else
    echo "✅ $added clé(s) ajoutée(s) à $ENV_FILE."
    echo "   Sauvegarde disponible : $BACKUP_FILE"
  fi
fi
