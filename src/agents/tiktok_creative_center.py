"""TikTok Creative Center scraping agent"""

from datetime import datetime
from typing import Optional
from playwright.async_api import Page
import logging

from .base_agent import BaseAgent, ScrapedProduct
from ..utils.stealth import BrowserStealth

logger = logging.getLogger(__name__)


class TikTokCreativeCenterAgent(BaseAgent):
    """
    Scrapes TikTok Creative Center for trending products.

    Data available:
    - Product name, image, category
    - View counts (aggregated across ads)
    - Like/engagement metrics
    - Top performing ads using product
    - Region-specific trends

    Rate limits: ~50 requests/hour recommended
    Authentication: None required, but rate limits apply
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
        period: str = "7",  # days: 7, 30, 120
        category: Optional[str] = None,
    ) -> list[ScrapedProduct]:
        """
        Fetch trending products from Creative Center.

        Strategy:
        1. Use Playwright to load page (heavy JS)
        2. Intercept API responses for cleaner data
        3. Paginate through results
        """
        products = []

        try:
            context, playwright, browser = await self.get_browser_context()

            try:
                # Create stealth-enhanced page
                page = await self.prepare_stealth_page(context)

                # Intercept API calls to capture clean JSON
                api_responses = []

                async def handle_response(response):
                    """Capture API responses"""
                    if self.PRODUCTS_ENDPOINT in response.url or "product/list" in response.url:
                        try:
                            data = await response.json()
                            api_responses.append(data)
                        except Exception as e:
                            logger.debug(f"Failed to parse response: {e}")

                page.on("response", handle_response)

                # Navigate with stealth and retry logic
                url = f"{self.BASE_URL}/inspiration/popular/product"
                logger.info(f"Navigating to TikTok Creative Center: {url}")

                success = await self.safe_navigate(page, url, wait_until="networkidle", timeout=60000)
                if not success:
                    logger.error("Failed to navigate to TikTok Creative Center (blocked or timeout)")
                    return []

                # Human-like delay for initial data to load
                await BrowserStealth.human_delay(2000, 4000)

                # Try to apply filters if elements exist
                try:
                    await self._apply_filters(page, region, period, category)
                except Exception as e:
                    logger.warning(f"Could not apply filters: {e}")

                # Scroll to load more products with human-like behavior
                scroll_attempts = 0
                max_scrolls = 10

                while len(products) < limit and scroll_attempts < max_scrolls:
                    # Human-like scrolling
                    await BrowserStealth.human_scroll(page, smooth=True)

                    # Random delay between scrolls (realistic)
                    await BrowserStealth.human_delay(1500, 3500)

                    # Occasional mouse movement (simulate reading/hovering)
                    if scroll_attempts % 3 == 0:
                        await BrowserStealth.random_mouse_movement(page, count=1)

                    # Parse intercepted responses
                    for response_data in api_responses:
                        new_products = self._parse_products(response_data)
                        products.extend(new_products)

                    api_responses.clear()
                    scroll_attempts += 1

                    # Check if we've hit the end
                    has_more = await self._has_more(page)
                    if not has_more:
                        logger.info("Reached end of product list")
                        break

                    logger.debug(f"Scroll {scroll_attempts}/{max_scrolls}: Found {len(products)} products so far")

                # If API interception didn't work, try scraping DOM
                if not products:
                    logger.warning("No API responses captured, trying DOM scraping")
                    products = await self._scrape_from_dom(page)

            finally:
                await context.close()
                await browser.close()
                await playwright.stop()

        except Exception as e:
            logger.error(f"Error fetching trending products: {e}")

        logger.info(f"Fetched {len(products)} products from TikTok Creative Center")
        return products[:limit]

    async def fetch_product_details(self, product_id: str) -> Optional[ScrapedProduct]:
        """Fetch detailed metrics for a specific product"""
        # For MVP, we get enough data from the trending list
        # This can be implemented later for deeper analysis
        logger.warning("fetch_product_details not yet implemented for TikTok CC")
        return None

    def _parse_products(self, api_data: dict) -> list[ScrapedProduct]:
        """Parse API response into normalized products"""
        products = []

        try:
            # Try different possible data structures
            items = []

            if isinstance(api_data, dict):
                # Try data.products
                if "data" in api_data and isinstance(api_data["data"], dict):
                    items = api_data["data"].get("products", [])
                    if not items:
                        items = api_data["data"].get("list", [])
                # Try direct products
                elif "products" in api_data:
                    items = api_data["products"]
                # Try direct list
                elif "list" in api_data:
                    items = api_data["list"]

            for item in items:
                try:
                    product = ScrapedProduct(
                        source=self.source_name,
                        source_id=str(item.get("product_id", item.get("id", ""))),
                        name=item.get("product_name", item.get("name", "Unknown")),
                        category=item.get("category_name", item.get("category")),
                        image_url=item.get("cover_url", item.get("image_url")),
                        product_url=item.get("product_url", item.get("url", "")),
                        views=item.get("vv", item.get("views", 0)),  # Video views
                        scraped_at=datetime.utcnow(),
                        raw_data=item,
                    )
                    products.append(product)
                except Exception as e:
                    logger.debug(f"Failed to parse product item: {e}")

        except Exception as e:
            logger.error(f"Error parsing API data: {e}")

        return products

    async def _scrape_from_dom(self, page: Page) -> list[ScrapedProduct]:
        """Fallback: scrape products from DOM elements"""
        products = []

        try:
            # Wait for product cards to load
            await page.wait_for_selector("[data-testid='product-card']", timeout=10000)

            # Extract product data from DOM
            product_data = await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll("[data-testid='product-card']");
                    return Array.from(cards).map(card => {
                        const nameEl = card.querySelector('.product-name');
                        const imageEl = card.querySelector('img');
                        const viewsEl = card.querySelector('.views-count');

                        return {
                            name: nameEl?.innerText || 'Unknown',
                            image_url: imageEl?.src || '',
                            views_text: viewsEl?.innerText || '0'
                        };
                    });
                }
            """)

            for idx, item in enumerate(product_data):
                try:
                    # Parse view count (e.g., "1.2M" -> 1200000)
                    views = self._parse_view_count(item.get("views_text", "0"))

                    product = ScrapedProduct(
                        source=self.source_name,
                        source_id=f"dom_{idx}_{datetime.utcnow().timestamp()}",
                        name=item.get("name", "Unknown"),
                        image_url=item.get("image_url"),
                        product_url="",
                        views=views,
                        scraped_at=datetime.utcnow(),
                        raw_data=item,
                    )
                    products.append(product)
                except Exception as e:
                    logger.debug(f"Failed to parse DOM product: {e}")

        except Exception as e:
            logger.warning(f"DOM scraping failed: {e}")

        return products

    def _parse_view_count(self, views_text: str) -> int:
        """Parse view count like '1.2M' or '500K' to integer"""
        try:
            views_text = views_text.strip().upper()
            multiplier = 1

            if "M" in views_text:
                multiplier = 1_000_000
                views_text = views_text.replace("M", "")
            elif "K" in views_text:
                multiplier = 1_000
                views_text = views_text.replace("K", "")

            value = float(views_text.replace(",", ""))
            return int(value * multiplier)
        except (ValueError, TypeError):
            return 0

    async def _apply_filters(
        self, page: Page, region: str, period: str, category: Optional[str]
    ):
        """Apply region/period/category filters via UI interaction"""
        # This would interact with the UI dropdowns
        # Implementation depends on current TikTok CC UI
        # For MVP, we can skip this and use default filters
        logger.debug(f"Applying filters: region={region}, period={period}, category={category}")
        pass

    async def _scroll_page(self, page: Page):
        """Scroll to trigger lazy loading"""
        await page.evaluate("window.scrollBy(0, window.innerHeight)")

    async def _has_more(self, page: Page) -> bool:
        """Check if more results are available"""
        try:
            # Check if we're at the bottom
            at_bottom = await page.evaluate("""
                () => {
                    return (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100;
                }
            """)
            return not at_bottom
        except Exception:
            return False
