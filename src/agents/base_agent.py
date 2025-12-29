"""Base agent class for all scraping agents"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
import httpx
from playwright.async_api import async_playwright
import logging
import random

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
        self.max_retries = config.get("max_retries", 3)
        self.proxy_pool = config.get("proxies", [])

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
        """Get Playwright browser context for JS-heavy pages"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080}, user_agent=self._get_user_agent()
        )
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
        """Rotate user agents"""
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        return random.choice(agents)
