"""Main entry point for TikTok Product Scout"""

import asyncio
import logging
import sys
from pathlib import Path

from .utils.config import config
from .orchestrator import JobCoordinator, JobScheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("logs/scout.log")],
)

logger = logging.getLogger(__name__)


async def run_single_scrape():
    """Run a single scrape for testing"""
    coordinator = JobCoordinator(config)

    logger.info("Running single scrape...")

    # Run TikTok Creative Center scraper
    await coordinator.run_agent("tiktok_creative_center", limit=50)

    # Run scoring
    await coordinator.run_scoring()

    # Check for alerts
    await coordinator.check_alerts()

    logger.info("Single scrape completed")


async def run_scheduler():
    """Run the scheduler for continuous operation"""
    coordinator = JobCoordinator(config)
    scheduler = JobScheduler(coordinator, config)

    scheduler.configure_jobs()
    scheduler.start()

    logger.info("Scheduler started - running continuously")

    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)  # Check every hour
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.stop()


def run_api():
    """Run the API server"""
    import uvicorn
    from .api.main import app

    host = config.get("api.host", "0.0.0.0")
    port = config.get("api.port", 8000)

    logger.info(f"Starting API server on {host}:{port}")

    uvicorn.run(app, host=host, port=port)


async def main():
    """Main entry point"""
    # Create necessary directories
    Path("data/db").mkdir(parents=True, exist_ok=True)
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "scrape":
            await run_single_scrape()
        elif command == "scheduler":
            await run_scheduler()
        elif command == "api":
            run_api()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python -m src.main [scrape|scheduler|api]")
            sys.exit(1)
    else:
        # Default: run scheduler
        await run_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
