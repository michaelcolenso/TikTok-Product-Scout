"""Base agent class for all scraping agents"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
import httpx
from playwright.async_api import async_playwright, Page, BrowserContext
import logging
import random

from ..utils.stealth import BrowserStealth, ProxyManager, RetryManager

logger = logging.getLogger(__name__)


class ScrapedProduct(BaseModel):
    """Normalized product data from any source"""

    source: str  # e.g., "tiktok_cc", "aliexpress"
    source_id: str  # Unique ID from source
    name: str
    category: Optional[str] = None
    price_usd: Optional[float] = None
    image_url: Optional[str] = None
    product_url: str

    # Source-specific metrics (nullable)
    views: Optional[int] = None
    sales: Optional[int] = None
    orders: Optional[int] = None
    reviews: Optional[int] = None
    rating: Optional[float] = None

    # Temporal data
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    first_seen_at: Optional[datetime] = None

    # Raw data for debugging
    raw_data: Optional[dict] = None


class BaseAgent(ABC):
    """Abstract base class for all scraping agents"""

    def __init__(self, config: dict):
        self.config = config
        self.rate_limit_delay = config.get("rate_limit_delay", 2.0)
        self.max_retries = config.get("max_retries", 4)
        self.proxy_pool = config.get("proxies", [])
        self.use_stealth = config.get("use_stealth", True)
        self.block_images = config.get("block_images", True)

        # Initialize proxy manager if proxies configured
        self.proxy_manager = None
        if self.proxy_pool:
            sticky_minutes = config.get("proxy_sticky_minutes", 15)
            self.proxy_manager = ProxyManager(self.proxy_pool, sticky_minutes)
            logger.info(f"Initialized proxy manager with {len(self.proxy_pool)} proxies (sticky: {sticky_minutes}min)")

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source"""
        pass

    @abstractmethod
    async def fetch_trending(self, limit: int = 100) -> list[ScrapedProduct]:
        """Fetch currently trending products"""
        pass

    @abstractmethod
    async def fetch_product_details(self, product_id: str) -> Optional[ScrapedProduct]:
        """Fetch detailed info for a specific product"""
        pass

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get configured HTTP client with proxy rotation"""
        proxy = self._rotate_proxy()
        return httpx.AsyncClient(
            proxy=proxy, timeout=30.0, headers=self._get_headers(), follow_redirects=True
        )

    async def get_browser_context(self):
        """
        Get stealth-enhanced Playwright browser context.

        Returns tuple: (context, playwright, browser)
        """
        # Get randomized config for this session
        stealth_config = BrowserStealth.get_random_config()

        playwright = await async_playwright().start()

        # Launch arguments for stealth
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--ignore-certificate-errors-spki-list",
        ]

        # Configure proxy if available
        proxy_config = None
        if self.proxy_manager:
            proxy_url = self.proxy_manager.get_proxy()
            if proxy_url:
                proxy_config = {"server": proxy_url}

        # Launch browser (headless for production, can set headless=False for debugging)
        browser = await playwright.chromium.launch(
            headless=self.config.get("headless", True),
            args=launch_args,
            proxy=proxy_config,
        )

        # Create context with randomized fingerprint
        context = await browser.new_context(
            viewport=stealth_config["viewport"],
            user_agent=stealth_config["user_agent"],
            timezone_id=stealth_config["timezone"],
            locale=stealth_config["locale"],
            color_scheme=stealth_config["color_scheme"],
            # Additional stealth options
            java_script_enabled=True,
            has_touch=False,
            is_mobile=False,
            # Permissions
            permissions=["geolocation"],
            geolocation={"latitude": 40.7128, "longitude": -74.0060},  # NYC
        )

        logger.info(f"Browser context created: {stealth_config['user_agent'][:50]}... | {stealth_config['viewport']}")

        return context, playwright, browser

    def _rotate_proxy(self) -> Optional[str]:
        """Rotate through proxy pool"""
        if not self.proxy_pool:
            return None
        # Round-robin or weighted selection
        return random.choice(self.proxy_pool)

    def _get_headers(self) -> dict:
        """Default headers to avoid detection"""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "User-Agent": self._get_user_agent(),
        }

    def _get_user_agent(self) -> str:
        """Rotate user agents (deprecated - use BrowserStealth.get_random_config)"""
        return random.choice(BrowserStealth.USER_AGENTS)

    async def prepare_stealth_page(self, context: BrowserContext) -> Page:
        """
        Create and configure a stealth-enhanced page.

        Returns configured Page ready for navigation.
        """
        page = await context.new_page()

        # Apply stealth patches
        if self.use_stealth:
            await BrowserStealth.apply_stealth(page)

        # Block resources to speed up and reduce fingerprint
        await BrowserStealth.block_resources(page, block_images=self.block_images)

        # Random mouse movement before navigating (simulate human)
        if random.random() < 0.3:  # 30% chance
            await BrowserStealth.random_mouse_movement(page, count=random.randint(1, 2))

        return page

    async def safe_navigate(
        self,
        page: Page,
        url: str,
        wait_until: str = "networkidle",
        timeout: int = 60000,
    ) -> bool:
        """
        Navigate with retry logic and block detection.

        Returns True if successful, False if blocked or failed.
        """
        async def navigate():
            await page.goto(url, wait_until=wait_until, timeout=timeout)

            # Check if we got blocked
            if await BrowserStealth.detect_block(page):
                # Take screenshot for debugging
                await BrowserStealth.take_failure_screenshot(page, prefix="blocked")

                # Mark proxy as failed if using proxies
                if self.proxy_manager and self.proxy_manager.current_proxy:
                    self.proxy_manager.mark_failed(self.proxy_manager.current_proxy)

                raise Exception("Page blocked or CAPTCHA detected")

            # Random delay after successful load (human behavior)
            await BrowserStealth.human_delay(1000, 3000)

        try:
            await RetryManager.retry_with_backoff(
                navigate,
                max_retries=self.max_retries,
                base_delay=2.0,
                on_retry=lambda attempt, ex: logger.warning(
                    f"Navigation retry {attempt + 1}/{self.max_retries}: {ex}"
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {url} after {self.max_retries} retries: {e}")
            return False
