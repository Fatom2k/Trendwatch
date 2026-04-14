"""Report formatting and export utilities.

Supports two output formats:
* Markdown — human-readable trend report.
* JSON     — machine-readable export suitable for downstream pipelines.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from sources.base import Trend

logger = logging.getLogger(__name__)


class ReportWriter:
    """Write trend reports to disk in Markdown and JSON formats.

    Args:
        output_dir: Directory where reports are saved.  Created on demand.
    """

    def __init__(self, output_dir: str | Path = "output/reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def write(self, trends: List[Trend]) -> str:
        """Generate and save both Markdown and JSON reports.

        Args:
            trends: Scored and analysed trend objects.

        Returns:
            Path to the Markdown report file.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        md_path = self.output_dir / f"report_{timestamp}.md"
        json_path = self.output_dir / f"report_{timestamp}.json"

        md_path.write_text(self._render_markdown(trends), encoding="utf-8")
        json_path.write_text(self._render_json(trends), encoding="utf-8")

        logger.info("Reports written: %s  |  %s", md_path, json_path)
        return str(md_path)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_markdown(self, trends: List[Trend]) -> str:
        """Render a human-readable Markdown report."""
        lines: List[str] = [
            "# TrendWatch Report",
            f"\n_Generated at {datetime.now(timezone.utc).isoformat()}_\n",
            f"**{len(trends)} trends** detected and scored.\n",
            "---\n",
        ]

        for trend in sorted(trends, key=lambda t: t.score, reverse=True):
            lines.append(f"## [{trend.score}/100] {trend.topic}")
            lines.append(f"**Platform:** {trend.platform}")
            if trend.hashtags:
                lines.append("**Hashtags:** " + "  ".join(f"`{h}`" for h in trend.hashtags))
            lines.append(
                f"**Demand:** volume={trend.demand.get('volume', 'N/A')}  "
                f"growth={trend.demand.get('growth_rate', 'N/A')}"
            )
            lines.append(
                f"**Saturation:** creators={trend.saturation.get('creator_count', 'N/A')}  "
                f"avg_age_days={trend.saturation.get('avg_post_age_days', 'N/A')}"
            )
            lines.append(
                f"**Velocity:** daily_growth={trend.velocity.get('daily_growth', 'N/A')}  "
                f"peak_acceleration={trend.velocity.get('peak_acceleration', 'N/A')}"
            )
            if trend.summary:
                lines.append(f"\n> {trend.summary}")
            if trend.suggested_formats:
                lines.append("**Suggested formats:** " + ", ".join(trend.suggested_formats))
            lines.append("")

        return "\n".join(lines)

    def _render_json(self, trends: List[Trend]) -> str:
        """Render a JSON array of trend objects."""
        return json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(trends),
                "trends": [t.to_dict() for t in trends],
            },
            ensure_ascii=False,
            indent=2,
        )
