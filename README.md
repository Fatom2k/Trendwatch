# TrendWatch 🔭

> Agent de veille automatisée des tendances de contenu sur les plateformes sociales.

## Vision

TrendWatch est un agent intelligent qui surveille en continu les tendances émergentes sur Instagram, TikTok, X (Twitter), YouTube, Pinterest et d'autres plateformes. Il s'intègre dans un pipeline de création de contenu automatique — qu'il soit **dématérialisé** (posts, reels, threads) ou **matérialisé** (produits physiques via print-on-demand, shops, merchandising).

## Pipeline global

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐
│   VEILLE    │───▶│   ANALYSE    │───▶│   SCORING   │───▶│    OUTPUT    │───▶│     CONTENU       │
│             │    │              │    │             │    │              │    │                   │
│ TikTok      │    │ Clustering   │    │ Demande     │    │ Rapport MD   │    │ Digital : posts,  │
│ Instagram   │    │ thématique   │    │ Saturation  │    │ JSON export  │    │ reels, threads    │
│ X/Twitter   │    │ Résumé IA    │    │ Vélocité    │    │ Alertes      │    │                   │
│ Google      │    │ (Claude API) │    │ Score /100  │    │              │    │ Physique : POD,   │
│ Trends      │    │              │    │             │    │              │    │ shops, merch      │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └───────────────────┘
```

## Structure du projet

```
trendwatch/
├── agent/              # Orchestrateur principal
│   ├── core.py         # TrendWatchAgent
│   ├── scheduler.py    # Planification des cycles
│   └── output.py       # Formatage et export
├── sources/            # Connecteurs par plateforme
│   ├── base.py         # Classe abstraite BaseSource
│   ├── tiktok.py
│   ├── instagram.py
│   ├── twitter.py
│   ├── google_trends.py
│   └── exploding_topics.py
├── analysis/           # Traitement et scoring
│   ├── scorer.py       # Score multicritère /100
│   ├── clustering.py   # Regroupement thématique
│   └── summarizer.py   # Résumé IA (Claude API)
├── pipelines/          # Sorties vers création de contenu
│   ├── content_digital.py
│   └── content_physical.py
├── output/             # Rapports générés
│   └── schemas/        # Schémas JSON
├── config/             # Configuration globale
└── tests/
```

## Installation

```bash
# Cloner le repo
git clone https://github.com/fatom2k/trendwatch.git
cd trendwatch

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos clés API
```

## Lancement

```bash
# Lancer un cycle de veille unique
python -m agent.core

# Lancer en mode scheduler (continu)
python -m agent.scheduler

# Via Docker
docker-compose up -d
```

## Variables d'environnement requises

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Clé API Claude (Anthropic) |
| `TIKTOK_API_KEY` | Clé API TikTok Creative Center |
| `TWITTER_BEARER_TOKEN` | Bearer token X/Twitter API v2 |
| `INSTAGRAM_ACCESS_TOKEN` | Token d'accès Instagram Graph API |
| `SISTRIX_API_KEY` | Clé API SISTRIX (hashtags Instagram) |
| `EXPLODING_TOPICS_API_KEY` | Clé API Exploding Topics |

## Exemples de résultats

```json
{
  "id": "tt_cottagecore_2025_04",
  "platform": "tiktok",
  "topic": "cottagecore aesthetic",
  "hashtags": ["#cottagecore", "#darkacademia", "#fairycore"],
  "score": 82,
  "demand": { "volume": 4200000, "growth_rate": 0.34 },
  "saturation": { "creator_count": 12000, "avg_post_age_days": 18 },
  "velocity": { "daily_growth": 0.08, "peak_acceleration": 1.4 },
  "detected_at": "2025-04-14T08:00:00Z",
  "suggested_formats": ["reel", "carousel", "thread"],
  "pipeline_target": "digital"
}
```

## Licence

MIT
