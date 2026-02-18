"""AliExpress scraping agent for supplier pricing"""

from datetime import datetime
from typing import Optional
import logging

from .base_agent import BaseAgent, ScrapedProduct
from ..utils.stealth import BrowserStealth

logger = logging.getLogger(__name__)


class AliExpressAgent(BaseAgent):
    """
    Scrapes AliExpress for supplier pricing and product info.

    Primary purposes:
    1. Calculate profit margins (TikTok price vs supplier cost)
    2. Identify supplier reliability
    3. Cross-reference trending products

    Data available:
    - Product price (with shipping)
    - Supplier rating
    - Order volume
    - Shipping times
    - Product variants
    """

    BASE_URL = "https://www.aliexpress.com"
    SEARCH_URL = "https://www.aliexpress.com/wholesale"

    @property
    def source_name(self) -> str:
        return "aliexpress"

    async def fetch_trending(self, limit: int = 100) -> list[ScrapedProduct]:
        """Fetch bestsellers from various categories"""
        # For MVP, this is not the primary use case
        # We mainly use AliExpress for supplier matching
        logger.info("fetch_trending not primary use case for AliExpress")
        return []

    async def fetch_product_details(self, product_id: str) -> Optional[ScrapedProduct]:
        """Fetch detailed info for a specific product"""
        logger.warning("fetch_product_details not yet implemented for AliExpress")
        return None

    async def search_product(self, query: str, limit: int = 10) -> list[ScrapedProduct]:
        """
        Search for a product to find supplier pricing.
        Used to calculate margins for TikTok products.
        """
        products = []

        try:
            context, playwright, browser = await self.get_browser_context()

            try:
                # Create stealth-enhanced page
                page = await self.prepare_stealth_page(context)

                # Build search URL
                search_url = f"{self.SEARCH_URL}?SearchText={query.replace(' ', '+')}"
                logger.info(f"Searching AliExpress: {search_url}")

                # Navigate with stealth and retry
                success = await self.safe_navigate(page, search_url, wait_until="networkidle", timeout=60000)
                if not success:
                    logger.error("Failed to navigate to AliExpress (blocked or timeout)")
                    return []

                # Human-like delay
                await BrowserStealth.human_delay(2000, 4000)

                # Extract product data from search results
                product_data = await page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('.search-card-item');
                        return Array.from(items).slice(0, 10).map(item => {
                            const titleEl = item.querySelector('.multi--title--G7dOCj3');
                            const priceEl = item.querySelector('.multi--price-sale--U-S0jtj');
                            const ordersEl = item.querySelector('.multi--trade--Ktbl2jB');
                            const linkEl = item.querySelector('a');

                            return {
                                name: titleEl?.innerText || '',
                                price: priceEl?.innerText || '',
                                orders: ordersEl?.innerText || '',
                                url: linkEl?.href || ''
                            };
                        });
                    }
                """)

                for idx, item in enumerate(product_data):
                    try:
                        price = self._parse_price(item.get("price", "0"))
                        orders = self._parse_orders(item.get("orders", "0"))

                        if item.get("name"):
                            product = ScrapedProduct(
                                source=self.source_name,
                                source_id=f"search_{idx}",
                                name=item["name"],
                                price_usd=price,
                                product_url=item.get("url", ""),
                                orders=orders,
                                scraped_at=datetime.utcnow(),
                                raw_data=item,
                            )
                            products.append(product)
                    except Exception as e:
                        logger.debug(f"Failed to parse product: {e}")

            finally:
                await context.close()
                await browser.close()
                await playwright.stop()

        except Exception as e:
            logger.error(f"Error searching AliExpress: {e}")

        logger.info(f"Found {len(products)} products on AliExpress for query: {query}")
        return products[:limit]

    async def get_supplier_price(self, product_name: str) -> Optional[dict]:
        """
        Find best supplier price for a product.

        Returns:
            {
                "source": "aliexpress",
                "min_price": 5.99,
                "max_price": 12.99,
                "avg_price": 8.50,
                "shipping_estimate": 2.50,
                "delivery_days": 15,
                "supplier_url": "...",
                "supplier_rating": 4.5,
                "supplier_orders": 1000
            }
        """
        results = await self.search_product(product_name, limit=10)

        if not results:
            return None

        prices = [p.price_usd for p in results if p.price_usd and p.price_usd > 0]

        if not prices:
            return None

        # Use first result as "top supplier"
        top = results[0]

        return {
            "source": "aliexpress",
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "shipping_estimate": 2.50,  # Estimated, can be refined
            "delivery_days": 15,  # Estimated
            "supplier_url": top.product_url,
            "supplier_rating": top.rating or 0,
            "supplier_orders": top.orders or 0,
            "confidence": 0.7,  # Confidence in the match
        }

    def _parse_price(self, price_text: str) -> float:
        """Parse price like '$12.99' or '€10.50' to USD"""
        try:
            # Remove currency symbols and commas
            price_text = price_text.replace("$", "").replace("€", "").replace(",", "").strip()

            # Extract first number
            import re

            match = re.search(r"[\d.]+", price_text)
            if match:
                price = float(match.group())
                # Simple conversion if in EUR (rough approximation)
                if "€" in price_text:
                    price *= 1.1
                return price
        except Exception as e:
            logger.debug(f"Failed to parse price '{price_text}': {e}")

        return 0.0

    def _parse_orders(self, orders_text: str) -> int:
        """Parse order count like '1000+ sold' or '5K orders'"""
        try:
            orders_text = orders_text.upper().strip()
            multiplier = 1

            if "K" in orders_text:
                multiplier = 1_000
                orders_text = orders_text.replace("K", "")

            # Extract number
            import re

            match = re.search(r"[\d.]+", orders_text)
            if match:
                value = float(match.group())
                return int(value * multiplier)
        except (ValueError, TypeError):
            pass

        return 0
