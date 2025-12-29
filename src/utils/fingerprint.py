"""Browser fingerprinting and anti-detection utilities."""

import random
from typing import Dict, Any


class BrowserFingerprint:
    """Generates realistic browser fingerprints to avoid detection."""

    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    MOBILE_USER_AGENTS = [
        # iPhone
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/119.0.6045.169 Mobile/15E148 Safari/604.1",
        # Android Chrome
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    ]

    VIEWPORTS = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 2560, "height": 1440},
    ]

    MOBILE_VIEWPORTS = [
        {"width": 390, "height": 844},  # iPhone 14
        {"width": 393, "height": 852},  # iPhone 14 Pro
        {"width": 412, "height": 915},  # Pixel 7
        {"width": 360, "height": 800},  # Samsung Galaxy
    ]

    @classmethod
    def get_random_user_agent(cls, mobile: bool = False) -> str:
        """Get random user agent string.

        Args:
            mobile: If True, return mobile user agent

        Returns:
            User agent string
        """
        agents = cls.MOBILE_USER_AGENTS if mobile else cls.USER_AGENTS
        return random.choice(agents)

    @classmethod
    def get_random_viewport(cls, mobile: bool = False) -> Dict[str, int]:
        """Get random viewport size.

        Args:
            mobile: If True, return mobile viewport

        Returns:
            Dictionary with width and height
        """
        viewports = cls.MOBILE_VIEWPORTS if mobile else cls.VIEWPORTS
        return random.choice(viewports)

    @classmethod
    def get_realistic_headers(cls, mobile: bool = False) -> Dict[str, str]:
        """Get realistic HTTP headers.

        Args:
            mobile: If True, use mobile headers

        Returns:
            Dictionary of HTTP headers
        """
        user_agent = cls.get_random_user_agent(mobile)

        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        return headers

    @classmethod
    def get_browser_context_options(cls, mobile: bool = False) -> Dict[str, Any]:
        """Get Playwright browser context options with fingerprinting.

        Args:
            mobile: If True, use mobile configuration

        Returns:
            Dictionary of browser context options
        """
        user_agent = cls.get_random_user_agent(mobile)
        viewport = cls.get_random_viewport(mobile)

        options = {
            "user_agent": user_agent,
            "viewport": viewport,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "light",
            "java_script_enabled": True,
            "bypass_csp": True,
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        if mobile:
            options["is_mobile"] = True
            options["has_touch"] = True

        return options

    @classmethod
    def get_random_delay(cls, min_delay: float = 1.0, max_delay: float = 5.0) -> float:
        """Get random delay for human-like behavior.

        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds

        Returns:
            Random delay in seconds
        """
        return random.uniform(min_delay, max_delay)

    @classmethod
    def get_stealth_js(cls) -> str:
        """Get JavaScript to inject for stealth mode.

        Returns:
            JavaScript code string
        """
        return """
        // Overwrite the navigator.webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // Overwrite the navigator.plugins property
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // Overwrite the navigator.languages property
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        // Add chrome object
        window.chrome = {
            runtime: {}
        };

        // Overwrite permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
