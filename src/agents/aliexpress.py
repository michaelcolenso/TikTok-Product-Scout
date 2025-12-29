"""AliExpress scraping agent for supplier pricing."""

from typing import Dict, List, Optional

from loguru import logger

from ..storage.models import ScrapedProduct
from .base_agent import BaseAgent


class AliExpressAgent(BaseAgent):
    """Scrapes AliExpress for supplier pricing and product info.

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

    @property
    def source_name(self) -> str:
        return "aliexpress"

    async def fetch_trending(self, limit: int = 100) -> List[ScrapedProduct]:
        """Fetch bestsellers from various categories.

        Args:
            limit: Maximum number of products

        Returns:
            List of scraped products
        """
        logger.info(f"Fetching trending products from AliExpress (limit={limit})")

        products = []

        # For MVP, focus on search functionality for margin calculation
        # Production implementation would scrape bestseller pages

        logger.info(
            "AliExpress trending scrape not fully implemented - use search_product instead"
        )

        return products

    async def search_product(self, query: str, max_results: int = 10) -> List[ScrapedProduct]:
        """Search for a product to find supplier pricing.

        Args:
            query: Product search query
            max_results: Maximum results to return

        Returns:
            List of matching products
        """
        logger.info(f"Searching AliExpress for: {query}")

        products = []

        try:
            playwright, context = await self.get_browser_context()

            try:
                page = await context.new_page()

                # Navigate to search
                search_url = f"{self.BASE_URL}/w/wholesale-{query.replace(' ', '-')}.html"
                await page.goto(search_url, wait_until="networkidle", timeout=60000)

                await self._delay()

                # Parse product listings
                # Note: Actual selectors would need to be updated based on current site structure
                products_data = await page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('[data-product-id]');
                        return Array.from(items).slice(0, 10).map(item => ({
                            id: item.dataset.productId,
                            name: item.querySelector('.multi--titleText--nXeOvyr')?.innerText,
                            price: item.querySelector('.multi--price-sale--U-S0jtj')?.innerText,
                            image: item.querySelector('img')?.src,
                            url: item.querySelector('a')?.href,
                            orders: item.querySelector('.multi--trade--Ktbl2jB')?.innerText,
                            rating: item.querySelector('.multi--rating--36zrE9O')?.innerText
                        }));
                    }
                """)

                # Convert to ScrapedProduct
                for item in products_data:
                    if not item.get("id"):
                        continue

                    product = self._create_scraped_product(
                        source_id=str(item.get("id")),
                        name=item.get("name", query),
                        product_url=item.get("url", ""),
                        price_usd=self._parse_price(item.get("price")),
                        image_url=item.get("image"),
                        orders=self._parse_orders(item.get("orders")),
                        rating=self._parse_rating(item.get("rating")),
                        raw_data=item,
                    )
                    products.append(product)

                await page.close()

            finally:
                await context.close()
                await playwright.stop()

        except Exception as e:
            logger.error(f"Error searching AliExpress: {e}")

        logger.info(f"Found {len(products)} products on AliExpress for query: {query}")
        return products

    async def get_supplier_price(self, product_name: str) -> Optional[Dict]:
        """Find best supplier price for a product.

        Args:
            product_name: Product name to search

        Returns:
            Dictionary with pricing info
        """
        results = await self.search_product(product_name, max_results=10)

        if not results:
            return None

        prices = [p.price_usd for p in results if p.price_usd is not None and p.price_usd > 0]

        if not prices:
            return None

        return {
            "source": "aliexpress",
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "shipping_estimate": 2.50,  # Default estimate
            "delivery_days": 15,  # Default estimate
            "supplier_rating": results[0].rating if results[0].rating else 4.0,
            "supplier_orders": results[0].orders if results[0].orders else 0,
            "url": results[0].product_url if results else "",
        }

    def _parse_price(self, price_str: Optional[str]) -> Optional[float]:
        """Parse price string to float.

        Args:
            price_str: Price string (e.g., "$12.99", "US $12.99")

        Returns:
            Price as float or None
        """
        if not price_str:
            return None

        try:
            # Remove currency symbols and extract number
            import re

            numbers = re.findall(r"[\d.]+", price_str)
            if numbers:
                return float(numbers[0])
        except Exception:
            pass

        return None

    def _parse_orders(self, orders_str: Optional[str]) -> Optional[int]:
        """Parse orders string to int.

        Args:
            orders_str: Orders string (e.g., "1000+ sold")

        Returns:
            Order count or None
        """
        if not orders_str:
            return None

        try:
            import re

            numbers = re.findall(r"\d+", orders_str)
            if numbers:
                return int(numbers[0])
        except Exception:
            pass

        return None

    def _parse_rating(self, rating_str: Optional[str]) -> Optional[float]:
        """Parse rating string to float.

        Args:
            rating_str: Rating string (e.g., "4.5")

        Returns:
            Rating as float or None
        """
        if not rating_str:
            return None

        try:
            import re

            numbers = re.findall(r"[\d.]+", rating_str)
            if numbers:
                return float(numbers[0])
        except Exception:
            pass

        return None
