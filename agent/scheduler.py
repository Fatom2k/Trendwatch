"""Scheduling layer for TrendWatch.

Wraps APScheduler to run the watch cycle on a configurable cadence
(hourly, daily, weekly).  Reads its configuration from
:class:`~config.settings.Settings`.

Usage::

    python -m agent.scheduler
"""

from __future__ import annotations

import logging
import signal
import sys
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from agent.core import TrendWatchAgent
from config.settings import Settings

logger = logging.getLogger(__name__)


class TrendWatchScheduler:
    """Configurable scheduler that runs :class:`~agent.core.TrendWatchAgent`.

    Supported cadences (configured via ``Settings.schedule_cadence``):

    * ``"hourly"``   — every N hours (default: 1)
    * ``"daily"``    — every day at ``Settings.schedule_time`` (e.g. ``"08:00"``)
    * ``"weekly"``   — every Monday at ``Settings.schedule_time``

    Args:
        settings: Global configuration object.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._agent = TrendWatchAgent(settings=self.settings)
        self._scheduler = BlockingScheduler(timezone=self.settings.timezone)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Configure the trigger and start the blocking scheduler.

        Installs ``SIGINT`` / ``SIGTERM`` handlers so the process shuts down
        gracefully when interrupted.
        """
        self._add_job()
        self._install_signal_handlers()
        logger.info(
            "Scheduler started — cadence=%s, timezone=%s",
            self.settings.schedule_cadence,
            self.settings.timezone,
        )
        self._scheduler.start()

    def stop(self) -> None:
        """Gracefully stop the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_job(self) -> None:
        """Register the watch-cycle job using the configured trigger."""
        trigger = self._build_trigger()
        self._scheduler.add_job(
            func=self._run_cycle,
            trigger=trigger,
            id="trendwatch_cycle",
            name="TrendWatch — watch cycle",
            replace_existing=True,
            misfire_grace_time=300,
        )

    def _build_trigger(self):
        """Return the APScheduler trigger matching the configured cadence."""
        cadence = self.settings.schedule_cadence
        time_str = self.settings.schedule_time  # "HH:MM"
        hour, minute = (int(p) for p in time_str.split(":"))

        if cadence == "hourly":
            return IntervalTrigger(hours=self.settings.schedule_interval_hours)
        if cadence == "daily":
            return CronTrigger(hour=hour, minute=minute)
        if cadence == "weekly":
            return CronTrigger(day_of_week="mon", hour=hour, minute=minute)

        raise ValueError(f"Unknown schedule cadence: {cadence!r}. Choose hourly / daily / weekly.")

    def _run_cycle(self) -> None:
        """Entry point called by APScheduler on each tick."""
        try:
            report_path = self._agent.run()
            if report_path:
                logger.info("Cycle complete — report at %s", report_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unhandled error in watch cycle: %s", exc, exc_info=True)

    def _install_signal_handlers(self) -> None:
        """Register OS-level signal handlers for graceful shutdown."""

        def _handler(signum, _frame):
            logger.info("Signal %s received — shutting down.", signum)
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    TrendWatchScheduler().start()
