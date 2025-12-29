"""Amazon Movers & Shakers scraping agent."""

from typing import List

from loguru import logger

from ..storage.models import ScrapedProduct
from .base_agent import BaseAgent


class AmazonMoversAgent(BaseAgent):
    """Monitors Amazon Movers & Shakers for cross-platform validation.

    Purpose:
    - Validate TikTok trends are translating to real purchases
    - Identify products with multi-platform momentum
    - BSR (Best Sellers Rank) velocity as quality signal

    Data available:
    - BSR and BSR changes
    - Price
    - Review count and rating
    - Category ranking
    """

    MOVERS_URL = "https://www.amazon.com/gp/movers-and-shakers"

    @property
    def source_name(self) -> str:
        return "amazon_movers"

    async def fetch_trending(self, limit: int = 100) -> List[ScrapedProduct]:
        """Fetch products from Movers & Shakers across categories.

        Args:
            limit: Maximum number of products

        Returns:
            List of scraped products
        """
        logger.info(f"Fetching trending products from Amazon Movers & Shakers (limit={limit})")

        categories = self.config.get("agents", {}).get("amazon_movers", {}).get(
            "categories",
            ["beauty", "home-kitchen", "electronics", "toys-games"],
        )

        all_products = []

        for category in categories:
            try:
                products = await self._fetch_category(category)
                all_products.extend(products)
                await self._delay()
            except Exception as e:
                logger.error(f"Error fetching Amazon category {category}: {e}")
                continue

        logger.info(f"Fetched {len(all_products)} products from Amazon Movers & Shakers")
        return all_products[:limit]

    async def _fetch_category(self, category: str) -> List[ScrapedProduct]:
        """Fetch movers for a specific category.

        Args:
            category: Amazon category slug

        Returns:
            List of scraped products
        """
        products = []

        try:
            playwright, context = await self.get_browser_context()

            try:
                page = await context.new_page()
                url = f"{self.MOVERS_URL}/{category}"
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

                await self._delay()

                # Parse product cards
                # Note: Selectors would need to be updated for current Amazon structure
                products_data = await page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('[data-asin]');
                        return Array.from(items).map(item => ({
                            asin: item.dataset.asin,
                            name: item.querySelector('.p13n-sc-truncate')?.innerText,
                            price: item.querySelector('.p13n-sc-price')?.innerText,
                            rank_change: item.querySelector('.zg-percent-change')?.innerText,
                            image: item.querySelector('img')?.src,
                            rating: item.querySelector('.a-icon-star-small')?.innerText,
                            reviews: item.querySelector('.a-size-small')?.innerText
                        }));
                    }
                """)

                # Convert to ScrapedProduct
                for item in products_data:
                    if not item.get("asin"):
                        continue

                    product = self._create_scraped_product(
                        source_id=item.get("asin"),
                        name=item.get("name", "Unknown Product"),
                        product_url=f"https://amazon.com/dp/{item.get('asin')}",
                        category=category,
                        price_usd=self._parse_price(item.get("price")),
                        image_url=item.get("image"),
                        rating=self._parse_rating(item.get("rating")),
                        reviews=self._parse_reviews(item.get("reviews")),
                        raw_data=item,
                    )
                    products.append(product)

                await page.close()

            finally:
                await context.close()
                await playwright.stop()

        except Exception as e:
            logger.error(f"Error fetching Amazon category {category}: {e}")

        return products

    def _parse_price(self, price_str: Optional[str]) -> Optional[float]:
        """Parse Amazon price string."""
        if not price_str:
            return None

        try:
            import re

            numbers = re.findall(r"[\d.]+", price_str)
            if numbers:
                return float(numbers[0])
        except Exception:
            pass

        return None

    def _parse_rating(self, rating_str: Optional[str]) -> Optional[float]:
        """Parse Amazon rating string."""
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

    def _parse_reviews(self, reviews_str: Optional[str]) -> Optional[int]:
        """Parse Amazon reviews count."""
        if not reviews_str:
            return None

        try:
            import re

            numbers = re.findall(r"\d+", reviews_str.replace(",", ""))
            if numbers:
                return int(numbers[0])
        except Exception:
            pass

        return None


from typing import Optional
