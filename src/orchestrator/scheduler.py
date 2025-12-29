"""Job scheduling for TikTok Product Scout."""

from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

if TYPE_CHECKING:
    from .coordinator import JobCoordinator


class JobScheduler:
    """Manages scheduled scraping and scoring jobs.

    Default schedule:
    - TikTok Creative Center: Every 4 hours
    - TikTok Shop: Every 6 hours
    - AliExpress (supplier matching): Every 12 hours
    - Amazon Movers: Every 8 hours
    - Scoring run: Every 2 hours
    - Alert check: Every 30 minutes
    """

    def __init__(self, coordinator: "JobCoordinator", config: dict):
        """Initialize job scheduler.

        Args:
            coordinator: Job coordinator instance
            config: Configuration dictionary
        """
        self.coordinator = coordinator
        self.config = config
        self.scheduler = AsyncIOScheduler()

    def configure_jobs(self):
        """Set up all scheduled jobs based on configuration."""
        schedule_config = self.config.get("schedule", {})

        # TikTok Creative Center - primary source
        tiktok_cc_hours = schedule_config.get("tiktok_creative_center_hours", 4)
        self.scheduler.add_job(
            self.coordinator.run_agent,
            IntervalTrigger(hours=tiktok_cc_hours),
            args=["tiktok_creative_center"],
            id="tiktok_cc_scrape",
            name="TikTok Creative Center Scrape",
            replace_existing=True,
        )
        logger.info(f"Scheduled TikTok CC scrape every {tiktok_cc_hours} hours")

        # TikTok Shop - sales data
        tiktok_shop_hours = schedule_config.get("tiktok_shop_hours", 6)
        self.scheduler.add_job(
            self.coordinator.run_agent,
            IntervalTrigger(hours=tiktok_shop_hours),
            args=["tiktok_shop"],
            id="tiktok_shop_scrape",
            name="TikTok Shop Scrape",
            replace_existing=True,
        )
        logger.info(f"Scheduled TikTok Shop scrape every {tiktok_shop_hours} hours")

        # AliExpress - supplier matching
        aliexpress_hours = schedule_config.get("aliexpress_hours", 12)
        self.scheduler.add_job(
            self.coordinator.run_supplier_matching,
            IntervalTrigger(hours=aliexpress_hours),
            id="supplier_match",
            name="Supplier Price Matching",
            replace_existing=True,
        )
        logger.info(f"Scheduled supplier matching every {aliexpress_hours} hours")

        # Amazon Movers - cross-validation
        amazon_hours = schedule_config.get("amazon_hours", 8)
        self.scheduler.add_job(
            self.coordinator.run_agent,
            IntervalTrigger(hours=amazon_hours),
            args=["amazon_movers"],
            id="amazon_scrape",
            name="Amazon Movers & Shakers",
            replace_existing=True,
        )
        logger.info(f"Scheduled Amazon scrape every {amazon_hours} hours")

        # Scoring engine
        scoring_hours = schedule_config.get("scoring_hours", 2)
        self.scheduler.add_job(
            self.coordinator.run_scoring,
            IntervalTrigger(hours=scoring_hours),
            id="scoring",
            name="Product Scoring",
            replace_existing=True,
        )
        logger.info(f"Scheduled product scoring every {scoring_hours} hours")

        # Alert check
        alert_minutes = schedule_config.get("alert_check_minutes", 30)
        self.scheduler.add_job(
            self.coordinator.check_alerts,
            IntervalTrigger(minutes=alert_minutes),
            id="alerts",
            name="Alert Check",
            replace_existing=True,
        )
        logger.info(f"Scheduled alert check every {alert_minutes} minutes")

        # Daily cleanup
        cleanup_days = schedule_config.get("cleanup_days", 30)
        self.scheduler.add_job(
            self.coordinator.cleanup_old_data,
            CronTrigger(hour=3, minute=0),  # 3 AM daily
            args=[cleanup_days],
            id="cleanup",
            name="Data Cleanup",
            replace_existing=True,
        )
        logger.info("Scheduled daily data cleanup at 3 AM")

    def start(self):
        """Start the scheduler."""
        logger.info("Starting job scheduler")
        self.scheduler.start()

    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping job scheduler")
        self.scheduler.shutdown()

    def get_jobs(self):
        """Get list of scheduled jobs."""
        return self.scheduler.get_jobs()
