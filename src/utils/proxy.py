"""Proxy rotation and management utilities."""

import random
from datetime import datetime
from typing import Optional


class ProxyRotator:
    """Manages proxy rotation for web scraping."""

    def __init__(self, proxies: list[str]):
        """Initialize proxy rotator.

        Args:
            proxies: List of proxy URLs (e.g., http://user:pass@host:port)
        """
        self.proxies = proxies
        self.current_index = 0
        self.use_count = {proxy: 0 for proxy in proxies}
        self.failure_count = {proxy: 0 for proxy in proxies}

    def get_next(self, strategy: str = "round_robin") -> Optional[str]:
        """Get next proxy based on rotation strategy.

        Args:
            strategy: Rotation strategy (round_robin, random, least_used)

        Returns:
            Proxy URL or None if no proxies available
        """
        if not self.proxies:
            return None

        # Filter out failed proxies (>3 failures)
        available = [p for p in self.proxies if self.failure_count[p] < 3]

        if not available:
            # Reset failure counts if all proxies failed
            self.failure_count = {proxy: 0 for proxy in self.proxies}
            available = self.proxies

        if strategy == "round_robin":
            proxy = available[self.current_index % len(available)]
            self.current_index += 1
        elif strategy == "random":
            proxy = random.choice(available)
        elif strategy == "least_used":
            proxy = min(available, key=lambda p: self.use_count[p])
        else:
            proxy = available[0]

        self.use_count[proxy] += 1
        return proxy

    def rotate(self) -> Optional[str]:
        """Rotate to next proxy (round-robin)."""
        return self.get_next("round_robin")

    def get_random(self) -> Optional[str]:
        """Get random proxy."""
        return self.get_next("random")

    def mark_failure(self, proxy: str):
        """Mark a proxy as failed.

        Args:
            proxy: Proxy URL that failed
        """
        if proxy in self.failure_count:
            self.failure_count[proxy] += 1

    def mark_success(self, proxy: str):
        """Mark a proxy as successful (reset failure count).

        Args:
            proxy: Proxy URL that succeeded
        """
        if proxy in self.failure_count:
            self.failure_count[proxy] = 0

    def get_stats(self) -> dict:
        """Get proxy usage statistics."""
        return {
            "total_proxies": len(self.proxies),
            "available_proxies": len([p for p in self.proxies if self.failure_count[p] < 3]),
            "use_count": self.use_count.copy(),
            "failure_count": self.failure_count.copy(),
        }
