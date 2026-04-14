"""Physical content / product pipeline.

Transforms scored trends into product suggestions and design briefs for:
- Print-on-demand (Printful, Printify)
- E-commerce shops (Shopify)

Output artifacts are JSON files written to ``output/reports/physical/``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sources.base import Trend

logger = logging.getLogger(__name__)

# Product categories supported by most POD platforms
POD_PRODUCT_TYPES = [
    "t-shirt",
    "hoodie",
    "tote-bag",
    "poster",
    "phone-case",
    "mug",
    "sticker-pack",
    "cap",
]


class PhysicalContentPipeline:
    """Generates product briefs and design specs from trend data.

    Args:
        output_dir:   Directory where artifacts are written.
        pod_platform: Target POD platform slug (``"printful"`` | ``"printify"``).
        webhook_url:  Optional HTTP endpoint to POST each artifact.
    """

    def __init__(
        self,
        output_dir: str | Path = "output/reports/physical",
        pod_platform: str = "printful",
        webhook_url: Optional[str] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pod_platform = pod_platform
        self.webhook_url = webhook_url

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process(self, trends: List[Trend]) -> List[Dict]:
        """Generate product briefs for all trends targeting physical output.

        Args:
            trends: Analysed trends (only ``pipeline_target == 'physical'``
                    are processed; digital trends with score > 70 are
                    also considered as cross-over candidates).

        Returns:
            List of product brief dicts.
        """
        physical_trends = [
            t for t in trends
            if t.pipeline_target == "physical" or (t.score >= 70 and t.pipeline_target == "digital")
        ]
        artifacts = [self._build_artifact(t) for t in physical_trends]

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = self.output_dir / f"product_briefs_{timestamp}.json"
        out_path.write_text(json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Physical pipeline: %d briefs written to %s.", len(artifacts), out_path)

        if self.webhook_url:
            self._post_webhook(artifacts)

        return artifacts

    # ------------------------------------------------------------------
    # Artifact builders
    # ------------------------------------------------------------------

    def _build_artifact(self, trend: Trend) -> Dict:
        """Build a product brief dict for a single trend."""
        return {
            "trend_id": trend.id,
            "topic": trend.topic,
            "score": trend.score,
            "pod_platform": self.pod_platform,
            "product_suggestions": self._suggest_products(trend),
            "design_brief": self._build_design_brief(trend),
            "shop_listing": self._build_shop_listing(trend),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _suggest_products(self, trend: Trend) -> List[Dict]:
        """Suggest the most suitable POD product types for this trend."""
        # Simple heuristic: high-score trends get broader product lines
        count = 3 if trend.score < 60 else 5 if trend.score < 80 else len(POD_PRODUCT_TYPES)
        return [
            {"product_type": pt, "priority": idx + 1}
            for idx, pt in enumerate(POD_PRODUCT_TYPES[:count])
        ]

    def _build_design_brief(self, trend: Trend) -> Dict:
        """Generate a design brief for the print-on-demand artwork."""
        return {
            "concept": f"Minimalist graphic inspired by '{trend.topic}' aesthetic",
            "style_keywords": [trend.topic] + [h.lstrip("#") for h in trend.hashtags[:3]],
            "color_palette": "To be defined by designer based on trend aesthetic",
            "typography": "Bold, modern sans-serif with trend-related copy",
            "copy_options": [
                trend.topic.title(),
                f"#{trend.topic.replace(' ', '').lower()}",
                trend.summary[:50] + "..." if trend.summary and len(trend.summary) > 50 else trend.summary or "",
            ],
            "format_requirements": {
                "resolution": "300 DPI",
                "format": "PNG with transparent background",
                "min_size_px": "4500x5400",
            },
        }

    def _build_shop_listing(self, trend: Trend) -> Dict:
        """Build e-commerce listing metadata."""
        return {
            "title": f"{trend.topic.title()} — Trending Design",
            "description": (
                f"Inspired by the viral '{trend.topic}' trend.\n"
                f"{trend.summary or ''}\n"
                "Premium quality print-on-demand product."
            ),
            "tags": [h.lstrip("#") for h in trend.hashtags[:10]] + [trend.platform, "trending"],
            "seo_title": f"Buy {trend.topic.title()} T-Shirt | Trending {datetime.now().year}",
        }

    def _post_webhook(self, artifacts: List[Dict]) -> None:
        """POST artifacts to the configured webhook URL."""
        try:
            import httpx
            resp = httpx.post(self.webhook_url, json=artifacts, timeout=15.0)
            resp.raise_for_status()
            logger.info("Webhook delivered: %s", self.webhook_url)
        except Exception as exc:
            logger.error("Webhook delivery failed: %s", exc)
