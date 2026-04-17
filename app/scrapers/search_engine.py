import json
import re
from pathlib import Path

from duckduckgo_search import DDGS

from app.scrapers.base import BaseScraper

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def load_keywords() -> dict:
    kw_path = DATA_DIR / "search_keywords.json"
    if kw_path.exists():
        return json.loads(kw_path.read_text(encoding="utf-8"))
    return {"finance_general": [], "competitors": [], "platform_specific": {}}


class SearchEngineScraper(BaseScraper):
    PLATFORM_NAME = "search_engine"
    RATE_LIMIT_SECONDS = 2.0

    async def search_kols(self, keywords: list = None) -> list:
        """Not used directly - use search_platform_kols instead."""
        return []

    async def scrape_profile(self, profile_url: str) -> dict:
        """Not applicable for search engine."""
        return {}

    async def search_platform_kols(
        self, platform_name: str, keywords: list = None, max_results: int = 30
    ) -> list:
        """Search DuckDuckGo for KOL profiles on a specific platform.

        Returns list of profile URLs found.
        """
        kw_data = load_keywords()
        site_filter = kw_data.get("platform_specific", {}).get(platform_name, "")

        if not keywords:
            keywords = kw_data.get("finance_general", [])[:5]

        all_urls = []
        seen = set()

        for keyword in keywords:
            query = f"{keyword} {site_filter}".strip()
            await self._rate_limit()

            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
                    for r in results:
                        url = r.get("href", "")
                        if url and url not in seen:
                            # Filter to actual profile/channel URLs
                            if self._is_profile_url(url, platform_name):
                                seen.add(url)
                                all_urls.append(url)
            except Exception as e:
                print(f"Search error for '{query}': {e}")
                continue

        return all_urls

    def _is_profile_url(self, url: str, platform_name: str) -> bool:
        """Check if URL looks like a user profile (not a random page)."""
        patterns = {
            "youtube": [
                r'youtube\.com/@[\w.-]+',
                r'youtube\.com/channel/[\w-]+',
                r'youtube\.com/c/[\w.-]+',
                r'youtube\.com/user/[\w.-]+',
            ],
            "instagram": [
                r'instagram\.com/[\w.]+/?$',
            ],
            "twitter": [
                r'(twitter|x)\.com/[\w]+/?$',
            ],
            "xiaohongshu": [
                r'xiaohongshu\.com/user/profile/[\w]+',
            ],
            "bilibili": [
                r'space\.bilibili\.com/\d+',
                r'bilibili\.com/video/BV[\w]+',
            ],
            "facebook": [
                r'facebook\.com/[\w.]+/?$',
            ],
            "tiktok": [
                r'tiktok\.com/@[\w.]+',
            ],
            "threads": [
                r'threads\.net/@[\w.]+',
            ],
        }

        for pattern in patterns.get(platform_name, []):
            if re.search(pattern, url):
                return True
        return False

    async def search_competitor_mentions(self, kol_name: str) -> list:
        """Search for mentions of competitor brands alongside a KOL's name."""
        kw_data = load_keywords()
        competitor_keywords = kw_data.get("competitors", [])
        mentions = []

        for competitor in competitor_keywords[:4]:
            query = f'"{kol_name}" "{competitor}" 合作'
            await self._rate_limit()
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=5))
                    for r in results:
                        mentions.append({
                            "brand": competitor,
                            "evidence_url": r.get("href", ""),
                            "title": r.get("title", ""),
                        })
            except Exception:
                continue

        return mentions
