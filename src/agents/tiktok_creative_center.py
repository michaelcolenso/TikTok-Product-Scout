"""TikTok Creative Center scraping agent."""

import asyncio
from typing import List, Optional

from loguru import logger

from ..storage.models import ScrapedProduct
from .base_agent import BaseAgent


class TikTokCreativeCenterAgent(BaseAgent):
    """Scrapes TikTok Creative Center for trending products.

    Data available:
    - Product name, image, category
    - View counts (aggregated across ads)
    - Like/engagement metrics
    - Top performing ads using product
    - Region-specific trends

    Note: This is a simplified implementation. Full implementation would use
    Playwright to handle the JavaScript-heavy site and intercept API calls.
    """

    BASE_URL = "https://ads.tiktok.com/business/creativecenter"
    PRODUCTS_ENDPOINT = "/api/v1/popular/product/list"

    @property
    def source_name(self) -> str:
        return "tiktok_creative_center"

    async def fetch_trending(
        self,
        limit: int = 100,
        region: str = "US",
        period: str = "7",
        category: Optional[str] = None,
    ) -> List[ScrapedProduct]:
        """Fetch trending products from Creative Center.

        Args:
            limit: Maximum number of products to fetch
            region: Region code (US, GB, DE, etc.)
            period: Time period in days (7, 30, 120)
            category: Optional category filter

        Returns:
            List of scraped products
        """
        logger.info(
            f"Fetching trending products from TikTok Creative Center "
            f"(region={region}, period={period}, limit={limit})"
        )

        products = []

        try:
            # Get browser context
            playwright, context = await self.get_browser_context()

            try:
                page = await context.new_page()

                # Store API responses
                api_responses = []

                # Intercept API calls
                async def handle_response(response):
                    if self.PRODUCTS_ENDPOINT in response.url:
                        try:
                            data = await response.json()
                            api_responses.append(data)
                        except Exception:
                            pass

                page.on("response", handle_response)

                # Navigate to products page
                url = f"{self.BASE_URL}/inspiration/popular/product"
                await page.goto(url, wait_until="networkidle", timeout=60000)

                # Wait for data to load
                await asyncio.sleep(5)

                # Scroll to load more products
                for _ in range(5):  # Scroll 5 times
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await asyncio.sleep(2)

                # Parse intercepted responses
                for response_data in api_responses:
                    products.extend(self._parse_products(response_data))

                await page.close()

            finally:
                await context.close()
                await playwright.stop()

        except Exception as e:
            logger.error(f"Error fetching from TikTok Creative Center: {e}")
            # For MVP, return empty list on error
            # In production, you might want to implement fallbacks

        logger.info(f"Fetched {len(products)} products from TikTok Creative Center")
        return products[:limit]

    def _parse_products(self, api_data: dict) -> List[ScrapedProduct]:
        """Parse API response into normalized products.

        Args:
            api_data: Raw API response data

        Returns:
            List of scraped products
        """
        products = []

        # Navigate nested response structure
        product_list = api_data.get("data", {}).get("products", [])

        for item in product_list:
            try:
                product = self._create_scraped_product(
                    source_id=str(item.get("product_id", "")),
                    name=item.get("product_name", "Unknown Product"),
                    product_url=item.get("product_url", ""),
                    category=item.get("category_name"),
                    image_url=item.get("cover_url"),
                    views=item.get("vv", 0),  # Video views
                    raw_data=item,
                )
                products.append(product)
            except Exception as e:
                logger.warning(f"Error parsing product: {e}")
                continue

        return products

    async def fetch_product_details(self, product_id: str) -> Optional[ScrapedProduct]:
        """Fetch detailed metrics for a specific product.

        Args:
            product_id: TikTok product ID

        Returns:
            Scraped product with detailed metrics
        """
        # Implementation would query specific product endpoint
        # For MVP, return None
        logger.warning(
            f"Product details not implemented for TikTok CC (product_id={product_id})"
        )
        return None
