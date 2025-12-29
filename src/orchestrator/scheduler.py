"""Job scheduler for automated scraping and scoring"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)


class JobScheduler:
    """
    Manages scheduled scraping and scoring jobs.

    Default schedule:
    - TikTok Creative Center: Every 4 hours
    - AliExpress (supplier matching): Every 12 hours
    - Scoring run: Every 2 hours
    - Alert check: Every 30 minutes
    """

    def __init__(self, coordinator, config):
        self.scheduler = AsyncIOScheduler()
        self.coordinator = coordinator
        self.config = config

    def configure_jobs(self):
        """Set up all scheduled jobs"""

        # TikTok Creative Center - primary source
        tiktok_hours = self.config.get("schedule.tiktok_creative_center_hours", 4)
        self.scheduler.add_job(
            self.coordinator.run_agent,
            IntervalTrigger(hours=tiktok_hours),
            args=["tiktok_creative_center"],
            id="tiktok_cc_scrape",
            name="TikTok Creative Center Scrape",
        )

        # AliExpress - supplier matching
        aliexpress_hours = self.config.get("schedule.aliexpress_hours", 12)
        self.scheduler.add_job(
            self.coordinator.run_supplier_matching,
            IntervalTrigger(hours=aliexpress_hours),
            id="supplier_match",
            name="Supplier Price Matching",
        )

        # Scoring engine
        scoring_hours = self.config.get("schedule.scoring_hours", 2)
        self.scheduler.add_job(
            self.coordinator.run_scoring,
            IntervalTrigger(hours=scoring_hours),
            id="scoring",
            name="Product Scoring",
        )

        # Alert check
        alert_minutes = self.config.get("schedule.alert_check_minutes", 30)
        self.scheduler.add_job(
            self.coordinator.check_alerts,
            IntervalTrigger(minutes=alert_minutes),
            id="alerts",
            name="Alert Check",
        )

        # Daily cleanup
        self.scheduler.add_job(
            self.coordinator.cleanup_old_data,
            CronTrigger(hour=3, minute=0),  # 3 AM
            id="cleanup",
            name="Data Cleanup",
        )

        logger.info("Scheduled jobs configured")

    def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
