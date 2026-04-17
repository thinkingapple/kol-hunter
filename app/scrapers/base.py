import asyncio
import time
from abc import ABC, abstractmethod

import config


class BaseScraper(ABC):
    PLATFORM_NAME: str = ""
    RATE_LIMIT_SECONDS: float = config.DEFAULT_RATE_LIMIT

    def __init__(self):
        self._last_request_time = 0.0

    async def _rate_limit(self):
        """Enforce minimum delay between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.RATE_LIMIT_SECONDS:
            await asyncio.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request_time = time.time()

    @abstractmethod
    async def search_kols(self, keywords: list) -> list:
        """Search for KOL profile URLs on this platform.
        Returns list of dicts with at least 'profile_url' key."""
        ...

    @abstractmethod
    async def scrape_profile(self, profile_url: str) -> dict:
        """Scrape a single KOL profile and return structured data.
        Returns dict with keys: name, platform_username, profile_url,
        follower_count, bio_text, etc."""
        ...
