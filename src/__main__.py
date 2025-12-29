"""Main entry point for TikTok Product Scout."""

import argparse
import asyncio
import sys

from loguru import logger

from .orchestrator.coordinator import JobCoordinator
from .orchestrator.scheduler import JobScheduler
from .utils.config import get_config
from .utils.logger import setup_logging


async def run_scheduler():
    """Run the job scheduler."""
    config = get_config()
    setup_logging()

    logger.info("=" * 80)
    logger.info("TikTok Product Scout - Starting")
    logger.info("=" * 80)

    # Initialize coordinator and scheduler
    coordinator = JobCoordinator(config.model_dump())
    scheduler = JobScheduler(coordinator, config.model_dump())

    # Configure and start scheduler
    scheduler.configure_jobs()
    scheduler.start()

    logger.info("Scheduler started. Press Ctrl+C to stop.")

    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()


async def run_single_agent(agent_name: str):
    """Run a single agent manually.

    Args:
        agent_name: Name of the agent to run
    """
    config = get_config()
    setup_logging()

    logger.info(f"Running agent: {agent_name}")

    coordinator = JobCoordinator(config.model_dump())
    await coordinator.run_agent(agent_name)

    logger.info("Agent run completed")


async def run_scoring():
    """Run product scoring manually."""
    config = get_config()
    setup_logging()

    logger.info("Running product scoring")

    coordinator = JobCoordinator(config.model_dump())
    await coordinator.run_scoring()

    logger.info("Scoring completed")


async def check_alerts():
    """Check and send alerts manually."""
    config = get_config()
    setup_logging()

    logger.info("Checking for alerts")

    coordinator = JobCoordinator(config.model_dump())
    await coordinator.check_alerts()

    logger.info("Alert check completed")


def run_api():
    """Run the FastAPI server."""
    import uvicorn

    from .api.main import app
    from .utils.config import get_config

    config = get_config()
    setup_logging()

    logger.info("=" * 80)
    logger.info("TikTok Product Scout API - Starting")
    logger.info("=" * 80)

    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        log_level="info",
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="TikTok Product Scout")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scheduler command
    subparsers.add_parser("scheduler", help="Run the job scheduler")

    # API command
    subparsers.add_parser("api", help="Run the API server")

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Run a single agent")
    agent_parser.add_argument(
        "agent_name",
        choices=[
            "tiktok_creative_center",
            "tiktok_shop",
            "aliexpress",
            "amazon_movers",
            "google_trends",
        ],
        help="Agent to run",
    )

    # Scoring command
    subparsers.add_parser("score", help="Run product scoring")

    # Alerts command
    subparsers.add_parser("alerts", help="Check and send alerts")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "scheduler":
            asyncio.run(run_scheduler())
        elif args.command == "api":
            run_api()
        elif args.command == "agent":
            asyncio.run(run_single_agent(args.agent_name))
        elif args.command == "score":
            asyncio.run(run_scoring())
        elif args.command == "alerts":
            asyncio.run(check_alerts())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
