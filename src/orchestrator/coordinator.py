"""Job coordinator for managing scraping, scoring, and alerting"""

import asyncio
from datetime import datetime, timedelta
import logging

from ..agents.tiktok_creative_center import TikTokCreativeCenterAgent
from ..agents.aliexpress import AliExpressAgent
from ..storage import Database
from ..scoring import CompositeScorer
from ..alerts import DiscordAlerter

logger = logging.getLogger(__name__)


class JobCoordinator:
    """
    Coordinates data collection, scoring, and alerting.
    """

    def __init__(self, config):
        self.config = config
        self.db = Database(config.database_url)
        self.scorer = CompositeScorer()

        # Initialize agents
        agent_config = {
            "rate_limit_delay": config.get("scraping.rate_limit_delay", 2.0),
            "max_retries": config.get("scraping.max_retries", 4),
            "use_stealth": config.get("scraping.stealth.enabled", True),
            "headless": config.get("scraping.stealth.headless", True),
            "block_images": config.get("scraping.stealth.block_images", True),
            "proxies": config.get("scraping.proxies.urls", []) if config.get("scraping.proxies.enabled", False) else [],
            "proxy_sticky_minutes": config.get("scraping.proxies.sticky_minutes", 15),
        }

        self.agents = {
            "tiktok_creative_center": TikTokCreativeCenterAgent(agent_config),
            "aliexpress": AliExpressAgent(agent_config),
        }

        # Initialize alerters
        webhook_url = config.discord_webhook_url
        self.discord = DiscordAlerter(webhook_url) if webhook_url else None

    async def run_agent(self, agent_name: str, limit: int = 100):
        """Run a specific scraping agent"""
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Unknown agent: {agent_name}")
            return

        logger.info(f"Starting {agent_name} scrape")
        start_time = datetime.utcnow()

        try:
            products = await agent.fetch_trending(limit=limit)

            # Store products
            for product in products:
                self.db.upsert_product(product)

            # Log job completion
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.db.record_scrape_job(
                agent_name=agent_name,
                status="completed",
                products_found=len(products),
                duration=duration,
            )

            logger.info(f"Completed {agent_name}: {len(products)} products in {duration:.1f}s")

        except Exception as e:
            logger.error(f"Error in {agent_name}: {str(e)}")
            self.db.record_scrape_job(agent_name=agent_name, status="failed")
            raise

    async def run_supplier_matching(self, limit: int = 50):
        """Match products with supplier prices from AliExpress"""
        logger.info("Starting supplier matching")

        # Get products needing supplier data
        products = self.db.get_products_needing_suppliers(limit=limit)

        aliexpress = self.agents["aliexpress"]

        matched = 0
        for product in products:
            try:
                supplier_data = await aliexpress.get_supplier_price(product.canonical_name)
                if supplier_data:
                    self.db.save_supplier_match(product.id, supplier_data)
                    matched += 1
                await asyncio.sleep(2)  # Rate limiting
            except Exception as e:
                logger.warning(f"Supplier match failed for {product.canonical_name}: {e}")

        logger.info(f"Matched {matched} products with suppliers")

    async def run_scoring(self):
        """Score all products with sufficient data"""
        logger.info("Starting scoring run")

        products = self.db.get_products_for_scoring()

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
        """Check for products that should trigger alerts"""
        logger.info("Checking for alert conditions")

        min_score = self.config.get("alerts.thresholds.min_composite_score", 70)
        cooldown_hours = self.config.get("alerts.thresholds.min_hours_between_alerts", 24)

        # Get high-scoring products that haven't been alerted recently
        candidates = self.db.get_alert_candidates(
            min_score=min_score, cooldown_hours=cooldown_hours
        )

        alerts_sent = 0
        for product in candidates:
            try:
                observations = self.db.get_observations(product.id)
                supplier_data = self.db.get_supplier_data(product.id)

                score = self.scorer.score_product(product, observations, supplier_data)

                # Only alert for actionable recommendations
                if score.recommendation in ["strong_buy", "buy"]:
                    await self._send_alert(product, score)
                    alerts_sent += 1
            except Exception as e:
                logger.error(f"Error processing alert for product {product.id}: {e}")

        logger.info(f"Sent {alerts_sent} alerts")

    async def _send_alert(self, product, score):
        """Send alert through configured channels"""
        if self.discord:
            try:
                await self.discord.send_alert(product, score)

                # Record that we sent an alert
                self.db.record_alert(product.id, score.to_dict())

                logger.info(f"Alert sent for {product.canonical_name}: {score.recommendation}")
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")

    async def cleanup_old_data(self, days: int = 30):
        """Remove old observations and inactive products"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = self.db.cleanup_old_observations(cutoff)
        logger.info(f"Cleaned up {deleted} old observations")
