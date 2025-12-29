"""
Stealth utilities for evading anti-bot detection.

This module provides comprehensive evasion techniques to bypass
TikTok, AliExpress, and other platforms' anti-bot defenses including:
- Fingerprint randomization
- Human-like behavior simulation
- Resource blocking for performance
- Block/CAPTCHA detection
"""

import asyncio
import random
import math
import logging
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from playwright.async_api import Page, Browser, BrowserContext, Playwright, Route

logger = logging.getLogger(__name__)


class BrowserStealth:
    """
    Comprehensive stealth configuration for Playwright browsers.

    Features:
    - Hides automation indicators (navigator.webdriver, etc.)
    - Randomizes fingerprints (canvas, WebGL, fonts, etc.)
    - Mimics human behavior (mouse, scrolling, typing)
    - Detects and handles blocks/CAPTCHAs
    """

    # Common desktop user agents (updated for 2025)
    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    # Viewport configurations (common resolutions)
    VIEWPORTS = [
        {"width": 1920, "height": 1080},  # Full HD
        {"width": 1366, "height": 768},   # Laptop
        {"width": 1536, "height": 864},   # Laptop HD+
        {"width": 2560, "height": 1440},  # 2K
        {"width": 1440, "height": 900},   # MacBook Air
    ]

    # Timezones matching common regions
    TIMEZONES = [
        "America/New_York",
        "America/Chicago",
        "America/Los_Angeles",
        "America/Denver",
        "Europe/London",
        "Europe/Paris",
    ]

    # Resource types to block for performance and fingerprinting
    BLOCKED_RESOURCES = [
        "image",  # Block images (speed + fingerprint)
        "font",   # Block fonts (fingerprint)
        "media",  # Block videos (speed)
        "stylesheet",  # Optional: can break layout but helps speed
    ]

    @staticmethod
    def get_random_config() -> dict:
        """Generate randomized browser configuration"""
        return {
            "user_agent": random.choice(BrowserStealth.USER_AGENTS),
            "viewport": random.choice(BrowserStealth.VIEWPORTS),
            "timezone": random.choice(BrowserStealth.TIMEZONES),
            "locale": "en-US",
            "color_scheme": random.choice(["light", "dark"]),
        }

    @staticmethod
    async def apply_stealth(page: Page) -> None:
        """
        Apply stealth scripts to hide automation.

        This mimics playwright-stealth by patching known automation indicators.
        """
        try:
            # Import and apply playwright-stealth
            from playwright_stealth import stealth_async
            await stealth_async(page)
            logger.debug("Applied playwright-stealth to page")
        except ImportError:
            logger.warning("playwright-stealth not installed, using manual stealth")
            await BrowserStealth._apply_manual_stealth(page)

    @staticmethod
    async def _apply_manual_stealth(page: Page) -> None:
        """Fallback: Manually apply stealth patches if library unavailable"""
        await page.add_init_script("""
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Override plugins to simulate real browser
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Add chrome object (common in real browsers)
            window.chrome = {
                runtime: {}
            };

            // Randomize canvas fingerprint
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const shift = Math.random() * 0.0001;
                const ctx = this.getContext('2d');
                if (ctx) {
                    const imageData = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = imageData.data[i] + shift;
                    }
                    ctx.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };
        """)
        logger.debug("Applied manual stealth scripts")

    @staticmethod
    async def block_resources(page: Page, block_images: bool = True) -> None:
        """
        Block unnecessary resources to speed up and reduce fingerprinting.

        Args:
            block_images: If True, blocks images. Set False if product images needed.
        """
        async def handle_route(route: Route):
            resource_type = route.request.resource_type

            # Build block list
            block_list = ["font", "media"]
            if block_images:
                block_list.append("image")

            # Block ads and trackers
            url = route.request.url
            ad_domains = [
                "doubleclick.net",
                "googlesyndication.com",
                "googletagmanager.com",
                "analytics.tiktok.com",
                "facebook.com/tr",
                "hotjar.com",
            ]

            if resource_type in block_list or any(domain in url for domain in ad_domains):
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", handle_route)
        logger.debug(f"Resource blocking enabled (images={'blocked' if block_images else 'allowed'})")

    @staticmethod
    async def human_delay(min_ms: int = 500, max_ms: int = 3000) -> None:
        """
        Human-like random delay.

        Uses weighted distribution favoring middle values (more realistic).
        """
        # Use triangular distribution (peaks in middle)
        delay = random.triangular(min_ms, max_ms, (min_ms + max_ms) / 2)
        await asyncio.sleep(delay / 1000.0)

    @staticmethod
    async def human_type(page: Page, selector: str, text: str) -> None:
        """Type text with human-like delays between keystrokes"""
        await page.click(selector)
        for char in text:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))  # 50-150ms per char

    @staticmethod
    async def human_scroll(page: Page, distance: Optional[int] = None, smooth: bool = True) -> None:
        """
        Scroll page naturally with human-like behavior.

        Args:
            distance: Pixels to scroll (default: random viewport-based)
            smooth: If True, scrolls in small increments
        """
        if distance is None:
            # Random scroll between 30% to 100% of viewport
            viewport = page.viewport_size
            distance = random.randint(
                int(viewport["height"] * 0.3),
                int(viewport["height"] * 1.0)
            )

        if smooth:
            # Scroll in chunks with delays
            steps = random.randint(5, 15)
            step_size = distance / steps

            for _ in range(steps):
                await page.evaluate(f"window.scrollBy(0, {step_size})")
                await asyncio.sleep(random.uniform(0.05, 0.15))
        else:
            await page.evaluate(f"window.scrollBy(0, {distance})")

        await BrowserStealth.human_delay(300, 800)

    @staticmethod
    async def mouse_move_to(page: Page, x: int, y: int, steps: int = 10) -> None:
        """
        Move mouse to coordinates with realistic bezier curve.

        Args:
            x, y: Target coordinates
            steps: Number of intermediate points (more = smoother)
        """
        # Get current position (assume starting from random spot)
        current_x = random.randint(0, page.viewport_size["width"])
        current_y = random.randint(0, page.viewport_size["height"])

        # Generate bezier curve points
        for i in range(steps + 1):
            t = i / steps
            # Add some randomness to path
            noise_x = random.uniform(-5, 5)
            noise_y = random.uniform(-5, 5)

            # Linear interpolation with noise
            next_x = current_x + (x - current_x) * t + noise_x
            next_y = current_y + (y - current_y) * t + noise_y

            await page.mouse.move(next_x, next_y)
            await asyncio.sleep(random.uniform(0.01, 0.03))

    @staticmethod
    async def random_mouse_movement(page: Page, count: int = 3) -> None:
        """Perform random mouse movements to simulate human activity"""
        viewport = page.viewport_size

        for _ in range(count):
            x = random.randint(0, viewport["width"])
            y = random.randint(0, viewport["height"])
            await BrowserStealth.mouse_move_to(page, x, y, steps=random.randint(5, 10))
            await BrowserStealth.human_delay(200, 500)

    @staticmethod
    async def detect_block(page: Page) -> bool:
        """
        Detect if page is blocked or showing CAPTCHA.

        Returns True if blocked, False otherwise.
        """
        # Check page content for common block indicators
        content = await page.content()
        content_lower = content.lower()

        # Common block/CAPTCHA indicators
        block_indicators = [
            "captcha",
            "verify you are human",
            "access denied",
            "forbidden",
            "cloudflare",
            "security check",
            "unusual traffic",
            "robot",
            "please verify",
            "challenge",
            "checking your browser",
        ]

        for indicator in block_indicators:
            if indicator in content_lower:
                logger.warning(f"Block detected: Found '{indicator}' in page content")
                return True

        # Check for CAPTCHA elements
        captcha_selectors = [
            "iframe[src*='captcha']",
            "iframe[src*='recaptcha']",
            ".g-recaptcha",
            "#captcha",
            "[class*='captcha']",
        ]

        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    logger.warning(f"Block detected: Found CAPTCHA element '{selector}'")
                    return True
            except:
                pass

        # Check HTTP status
        try:
            response = page.url
            # If we were redirected to a different domain, might be blocked
            if "challenge" in response or "verify" in response:
                logger.warning("Block detected: Redirected to challenge page")
                return True
        except:
            pass

        return False

    @staticmethod
    async def take_failure_screenshot(page: Page, prefix: str = "blocked") -> Optional[str]:
        """
        Take screenshot on failure for debugging.

        Returns path to screenshot file.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"/tmp/{prefix}_{timestamp}.png"
            await page.screenshot(path=filename, full_page=True)
            logger.info(f"Failure screenshot saved: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None


class ProxyManager:
    """
    Manages proxy rotation with sticky sessions.

    Features:
    - Round-robin or weighted proxy selection
    - Sticky sessions (same IP for configurable duration)
    - Automatic proxy health tracking
    - Fallback to no proxy if all fail
    """

    def __init__(self, proxies: list[str], sticky_minutes: int = 15):
        """
        Args:
            proxies: List of proxy URLs (format: http://user:pass@ip:port)
            sticky_minutes: Minutes to stick with same proxy
        """
        self.proxies = proxies
        self.sticky_minutes = sticky_minutes
        self.current_proxy: Optional[str] = None
        self.current_proxy_until: Optional[datetime] = None
        self.failed_proxies: set[str] = set()
        self.current_index = 0

    def get_proxy(self) -> Optional[str]:
        """
        Get current proxy or rotate to next.

        Returns None if no proxies available or all failed.
        """
        if not self.proxies:
            return None

        # Check if we should stick with current proxy
        if self.current_proxy and self.current_proxy_until:
            if datetime.now() < self.current_proxy_until:
                return self.current_proxy

        # Rotate to next proxy
        available = [p for p in self.proxies if p not in self.failed_proxies]

        if not available:
            logger.warning("All proxies failed, resetting failed list")
            self.failed_proxies.clear()
            available = self.proxies

        # Round-robin selection
        self.current_proxy = available[self.current_index % len(available)]
        self.current_index += 1
        self.current_proxy_until = datetime.now() + timedelta(minutes=self.sticky_minutes)

        logger.info(f"Using proxy: {self._mask_proxy(self.current_proxy)} (sticky until {self.current_proxy_until.strftime('%H:%M')})")
        return self.current_proxy

    def mark_failed(self, proxy: str) -> None:
        """Mark a proxy as failed"""
        self.failed_proxies.add(proxy)
        logger.warning(f"Proxy marked as failed: {self._mask_proxy(proxy)}")

        # If current proxy failed, clear sticky session
        if proxy == self.current_proxy:
            self.current_proxy = None
            self.current_proxy_until = None

    def _mask_proxy(self, proxy: str) -> str:
        """Mask credentials in proxy URL for logging"""
        if "@" in proxy:
            parts = proxy.split("@")
            return f"***@{parts[1]}"
        return proxy


class RetryManager:
    """
    Manages exponential backoff retries with jitter.
    """

    @staticmethod
    async def retry_with_backoff(
        func: Callable,
        max_retries: int = 4,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ) -> Any:
        """
        Retry function with exponential backoff.

        Args:
            func: Async function to retry
            max_retries: Maximum number of retries
            base_delay: Initial delay in seconds (doubles each retry)
            max_delay: Maximum delay cap
            on_retry: Optional callback(attempt, exception) on each retry

        Returns:
            Result of func()

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await func()
            except Exception as e:
                last_exception = e

                if attempt >= max_retries:
                    logger.error(f"All {max_retries} retries exhausted")
                    raise

                # Calculate exponential backoff with jitter
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = random.uniform(0, delay * 0.1)  # Add 10% jitter
                total_delay = delay + jitter

                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {total_delay:.1f}s..."
                )

                if on_retry:
                    on_retry(attempt, e)

                await asyncio.sleep(total_delay)

        raise last_exception
