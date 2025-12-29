"""Job coordination for TikTok Product Scout."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

from loguru import logger

from ..agents.aliexpress import AliExpressAgent
from ..agents.amazon_movers import AmazonMoversAgent
from ..agents.google_trends import GoogleTrendsAgent
from ..agents.tiktok_creative_center import TikTokCreativeCenterAgent
from ..agents.tiktok_shop import TikTokShopAgent
from ..alerts.discord import DiscordAlerter
from ..alerts.email import EmailAlerter
from ..scoring.composite import CompositeScorer
from ..storage.database import Database
from ..utils.config import get_config, get_settings


class JobCoordinator:
    """Coordinates data collection, scoring, and alerting."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize job coordinator.

        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            config = get_config().model_dump()

        self.config = config
        self.settings = get_settings()

        # Initialize database
        db_url = config.get("database", {}).get("url", "sqlite:///data/db/products.db")
        self.db = Database(db_url)

        # Initialize scoring engine
        self.scorer = CompositeScorer(config)

        # Initialize agents
        self._init_agents()

        # Initialize alerters
        self._init_alerters()

    def _init_agents(self):
        """Initialize scraping agents."""
        agent_config = {
            **self.config.get("scraping", {}),
            **self.config.get("anti_detection", {}),
        }

        # Add API keys
        agent_config["kalodata_api_key"] = self.settings.kalodata_api_key
        agent_config["fastmoss_api_key"] = self.settings.fastmoss_api_key

        self.agents = {
            "tiktok_creative_center": TikTokCreativeCenterAgent(agent_config),
            "tiktok_shop": TikTokShopAgent(agent_config),
            "aliexpress": AliExpressAgent(agent_config),
            "amazon_movers": AmazonMoversAgent(agent_config),
            "google_trends": GoogleTrendsAgent(agent_config),
        }

        logger.info(f"Initialized {len(self.agents)} agents")

    def _init_alerters(self):
        """Initialize alert channels."""
        self.discord = None
        self.email_alerter = None

        # Discord
        discord_config = self.config.get("alerts", {}).get("discord", {})
        if discord_config.get("enabled") and self.settings.discord_webhook_url:
            self.discord = DiscordAlerter(self.settings.discord_webhook_url)
            logger.info("Initialized Discord alerter")

        # Email
        email_config = self.config.get("alerts", {}).get("email", {})
        if email_config.get("enabled") and self.settings.smtp_user:
            recipients = [
                r.strip()
                for r in self.settings.email_recipients.split(",")
                if r.strip()
            ]
            if recipients:
                self.email_alerter = EmailAlerter(
                    smtp_host=self.settings.smtp_host,
                    smtp_port=self.settings.smtp_port,
                    smtp_user=self.settings.smtp_user,
                    smtp_password=self.settings.smtp_password,
                    recipients=recipients,
                )
                logger.info(f"Initialized email alerter with {len(recipients)} recipients")

    async def run_agent(self, agent_name: str):
        """Run a specific scraping agent.

        Args:
            agent_name: Name of the agent to run
        """
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Unknown agent: {agent_name}")
            return

        logger.info(f"Starting {agent_name} scrape")
        start_time = datetime.utcnow()

        try:
            products = await agent.fetch_trending(limit=100)

            # Store products
            for product in products:
                try:
                    self.db.upsert_product(product)
                except Exception as e:
                    logger.error(f"Error storing product: {e}")

            # Log job completion
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed {agent_name}: {len(products)} products in {duration:.1f}s"
            )

        except Exception as e:
            logger.error(f"Error in {agent_name}: {str(e)}", exc_info=True)

    async def run_supplier_matching(self):
        """Match products with supplier prices from AliExpress."""
        logger.info("Starting supplier matching")

        # Get products needing supplier data
        products = self.db.get_products_needing_suppliers(limit=50)

        if not products:
            logger.info("No products need supplier matching")
            return

        aliexpress = self.agents["aliexpress"]

        for product in products:
            try:
                supplier_data = await aliexpress.get_supplier_price(product.canonical_name)
                if supplier_data:
                    self.db.save_supplier_match(product.id, supplier_data)
                    logger.info(f"Matched supplier for: {product.canonical_name}")

                # Rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                logger.warning(
                    f"Supplier match failed for {product.canonical_name}: {e}"
                )

        logger.info(f"Completed supplier matching for {len(products)} products")

    async def run_scoring(self):
        """Score all products with sufficient data."""
        logger.info("Starting scoring run")

        products = self.db.get_products_for_scoring(min_observations=2)

        if not products:
            logger.info("No products to score")
            return

        for product in products:
            try:
                observations = self.db.get_observations(product.id)
                supplier_data = self.db.get_supplier_data(product.id)

                score = self.scorer.score_product(product, observations, supplier_data)

                # Update product with new scores
                self.db.update_product_scores(
                    product.id,
                    composite_score=score.composite_score,
                    velocity_score=score.velocity_score,
                    margin_score=score.margin_score,
                    saturation_score=score.saturation_score,
                )

            except Exception as e:
                logger.error(f"Error scoring product {product.id}: {e}")

        logger.info(f"Scored {len(products)} products")

    async def check_alerts(self):
        """Check for products that should trigger alerts."""
        logger.info("Checking for alert conditions")

        thresholds = self.config.get("alerts", {}).get("thresholds", {})
        min_score = thresholds.get("min_composite_score", 70)
        cooldown_hours = thresholds.get("min_hours_between_alerts", 24)

        # Get high-scoring products that haven't been alerted recently
        candidates = self.db.get_alert_candidates(
            min_score=min_score, cooldown_hours=cooldown_hours
        )

        if not candidates:
            logger.info("No products meet alert criteria")
            return

        logger.info(f"Found {len(candidates)} alert candidates")

        for product in candidates:
            try:
                observations = self.db.get_observations(product.id)
                supplier_data = self.db.get_supplier_data(product.id)

                score = self.scorer.score_product(product, observations, supplier_data)

                # Only alert for actionable recommendations
                if score.recommendation in ["strong_buy", "buy"]:
                    await self._send_alert(product, score)

            except Exception as e:
                logger.error(f"Error processing alert for product {product.id}: {e}")

    async def _send_alert(self, product, score):
        """Send alert through configured channels.

        Args:
            product: Product instance
            score: Opportunity score
        """
        sent = False

        # Send to Discord
        if self.discord:
            try:
                result = await self.discord.send_alert(product, score)
                sent = sent or result
            except Exception as e:
                logger.error(f"Discord alert failed: {e}")

        # Send to Email
        if self.email_alerter:
            try:
                result = await self.email_alerter.send_alert(product, score)
                sent = sent or result
            except Exception as e:
                logger.error(f"Email alert failed: {e}")

        if sent:
            # Record that we sent an alert
            score_data = {
                "composite_score": score.composite_score,
                "recommendation": score.recommendation,
                "signals": score.signals,
            }
            self.db.record_alert(product.id, score_data)

            logger.info(
                f"Alert sent for {product.canonical_name}: {score.recommendation}"
            )

    async def cleanup_old_data(self, days: int = 30):
        """Remove old observations and inactive products.

        Args:
            days: Number of days to keep
        """
        logger.info(f"Cleaning up data older than {days} days")

        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = self.db.cleanup_old_observations(cutoff)

        logger.info(f"Cleaned up {deleted} old observations")

    async def run_manual_scrape(self, agent_name: str):
        """Manually trigger a scrape for testing.

        Args:
            agent_name: Name of the agent to run
        """
        await self.run_agent(agent_name)
