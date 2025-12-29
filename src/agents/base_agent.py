"""Base agent class for web scraping."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from playwright.async_api import async_playwright, BrowserContext

from ..storage.models import ScrapedProduct
from ..utils.fingerprint import BrowserFingerprint
from ..utils.proxy import ProxyRotator


class BaseAgent(ABC):
    """Abstract base class for all scraping agents."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize agent.

        Args:
            config: Agent configuration dictionary
        """
        self.config = config
        self.rate_limit_delay = config.get("rate_limit_delay", 2.0)
        self.max_retries = config.get("max_retries", 3)
        self.timeout = config.get("timeout", 30)

        # Proxy setup
        proxy_list = config.get("proxies", [])
        self.proxy_rotator = ProxyRotator(proxy_list) if proxy_list else None

        # Anti-detection settings
        self.use_proxies = config.get("anti_detection", {}).get("use_proxies", False)
        self.rotate_user_agents = config.get("anti_detection", {}).get(
            "rotate_user_agents", True
        )
        self.random_delays = config.get("anti_detection", {}).get("random_delays", True)
        self.min_delay = config.get("anti_detection", {}).get("min_delay", 1.0)
        self.max_delay = config.get("anti_detection", {}).get("max_delay", 5.0)

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        pass

    @abstractmethod
    async def fetch_trending(self, limit: int = 100, **kwargs) -> List[ScrapedProduct]:
        """Fetch currently trending products.

        Args:
            limit: Maximum number of products to fetch
            **kwargs: Additional source-specific parameters

        Returns:
            List of scraped products
        """
        pass

    async def fetch_product_details(self, product_id: str) -> Optional[ScrapedProduct]:
        """Fetch detailed info for a specific product.

        Args:
            product_id: Product identifier in the source system

        Returns:
            Scraped product or None if not found
        """
        # Default implementation - subclasses can override
        return None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get configured HTTP client with proxy rotation.

        Returns:
            Configured HTTP client
        """
        proxy = None
        if self.use_proxies and self.proxy_rotator:
            proxy = self.proxy_rotator.get_next()

        return httpx.AsyncClient(
            proxy=proxy,
            timeout=self.timeout,
            headers=self._get_headers(),
            follow_redirects=True,
        )

    async def get_browser_context(
        self, mobile: bool = False
    ) -> tuple[Any, BrowserContext]:
        """Get Playwright browser context for JS-heavy pages.

        Args:
            mobile: If True, use mobile viewport and user agent

        Returns:
            Tuple of (playwright instance, browser context)
        """
        playwright = await async_playwright().start()

        # Get browser options
        browser_args = ["--disable-blink-features=AutomationControlled"]

        # Add proxy if configured
        proxy = None
        if self.use_proxies and self.proxy_rotator:
            proxy_url = self.proxy_rotator.get_next()
            if proxy_url:
                proxy = {"server": proxy_url}

        browser = await playwright.chromium.launch(
            headless=True, args=browser_args, proxy=proxy
        )

        # Get context options with fingerprinting
        context_options = BrowserFingerprint.get_browser_context_options(mobile)

        context = await browser.new_context(**context_options)

        # Inject stealth JavaScript
        await context.add_init_script(BrowserFingerprint.get_stealth_js())

        return playwright, context

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with optional user agent rotation.

        Returns:
            Dictionary of HTTP headers
        """
        if self.rotate_user_agents:
            return BrowserFingerprint.get_realistic_headers()

        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def _delay(self):
        """Add random delay between requests for human-like behavior."""
        if self.random_delays:
            delay = BrowserFingerprint.get_random_delay(self.min_delay, self.max_delay)
        else:
            delay = self.rate_limit_delay

        await asyncio.sleep(delay)

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Retry a function with exponential backoff.

        Args:
            func: Async function to retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            Exception: If all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = 2**attempt
                    await asyncio.sleep(delay)

        raise last_exception

    def _create_scraped_product(
        self,
        source_id: str,
        name: str,
        product_url: str,
        category: Optional[str] = None,
        price_usd: Optional[float] = None,
        image_url: Optional[str] = None,
        views: Optional[int] = None,
        sales: Optional[int] = None,
        orders: Optional[int] = None,
        reviews: Optional[int] = None,
        rating: Optional[float] = None,
        raw_data: Optional[Dict] = None,
    ) -> ScrapedProduct:
        """Helper to create ScrapedProduct instance.

        Args:
            source_id: Unique ID from source
            name: Product name
            product_url: URL to product
            category: Product category
            price_usd: Price in USD
            image_url: Product image URL
            views: View count
            sales: Sales count
            orders: Order count
            reviews: Review count
            rating: Product rating
            raw_data: Raw data dictionary

        Returns:
            ScrapedProduct instance
        """
        return ScrapedProduct(
            source=self.source_name,
            source_id=source_id,
            name=name,
            category=category,
            price_usd=price_usd,
            image_url=image_url,
            product_url=product_url,
            views=views,
            sales=sales,
            orders=orders,
            reviews=reviews,
            rating=rating,
            scraped_at=datetime.utcnow(),
            raw_data=raw_data,
        )
