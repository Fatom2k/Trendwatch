# TrendWatch — Roadmap

## Phase 1 — Veille manuelle assistée ✅ (en cours)

**Objectif :** Collecter des tendances depuis des sources gratuites et produire un rapport Markdown lisible.

- [x] Architecture du projet (sources, analysis, pipelines)
- [x] Classe abstraite `BaseSource`
- [x] Connecteur `google_trends.py` (pytrends, gratuit)
- [x] Scoring multicritère basique (demande / saturation / vélocité)
- [x] Export rapport Markdown
- [ ] Connecteur `exploding_topics.py` (tier gratuit)
- [ ] Rapport HTML statique avec graphiques

## Phase 2 — Automatisation des connecteurs et scheduling

**Objectif :** Automatiser la collecte sur toutes les sources et planifier les cycles de veille.

- [ ] Connecteur `tiktok.py` (TikTok Creative Center API)
- [ ] Connecteur `twitter.py` (X API v2 + trending topics)
- [ ] Connecteur `instagram.py` (Graph API + SISTRIX)
- [ ] Scheduling configurable via APScheduler (horaire / quotidien / hebdomadaire)
- [ ] Stockage persistant des tendances (SQLite ou JSON lines)
- [ ] Déduplication des tendances inter-sources

## Phase 3 — Scoring et clustering IA des tendances

**Objectif :** Améliorer la qualité du scoring et regrouper les tendances par thème.

- [ ] Scoring avancé avec pondération configurable par plateforme
- [ ] Clustering thématique (embeddings + k-means ou HDBSCAN)
- [ ] Résumé IA des tendances via API Claude (`claude-sonnet-4-20250514`)
- [ ] Détection des tendances cross-platform (même sujet sur plusieurs sources)
- [ ] Alertes sur les tendances à vélocité élevée

## Phase 4 — Intégration pipeline contenu dématérialisé

**Objectif :** Connecter TrendWatch à des outils de création de contenu automatique.

- [ ] Génération de briefs de contenu (format Markdown structuré)
- [ ] Génération de scripts de Reels / TikToks
- [ ] Génération de threads X
- [ ] Génération de légendes Instagram avec hashtags optimisés
- [ ] Intégration avec des outils no-code (Zapier, Make)
- [ ] Webhook de sortie configurable

## Phase 5 — Intégration pipeline contenu matérialisé (shops, POD)

**Objectif :** Transformer les tendances en opportunités de produits physiques.

- [ ] Suggestion de niche produit basée sur les tendances détectées
- [ ] Génération de briefs de design pour print-on-demand
- [ ] Intégration Printful API (création de produits)
- [ ] Intégration Printify API
- [ ] Intégration Shopify (publication automatique de produits)
- [ ] Tableau de bord de suivi des tendances → ventes

---

> Les phases sont itératives. Les retours terrain peuvent modifier les priorités.
