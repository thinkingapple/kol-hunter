import re
from app.scrapers.base import BaseScraper
from app.scrapers.utils import extract_emails


class TikTokScraper(BaseScraper):
    """TikTok scraper - basic meta tag extraction."""
    PLATFORM_NAME = "tiktok"
    RATE_LIMIT_SECONDS = 5.0

    async def search_kols(self, keywords: list = None) -> list:
        from app.scrapers.search_engine import SearchEngineScraper
        se = SearchEngineScraper()
        return await se.search_platform_kols("tiktok", keywords)

    async def scrape_profile(self, profile_url: str) -> dict:
        await self._rate_limit()

        username = ""
        match = re.search(r'tiktok\.com/@([\w.]+)', profile_url)
        if match:
            username = match.group(1)

        if not username:
            return {}

        try:
            import httpx
            from bs4 import BeautifulSoup
            from app.scrapers.utils import random_ua

            async with httpx.AsyncClient(
                headers={"User-Agent": random_ua()},
                follow_redirects=True,
                timeout=15,
            ) as client:
                resp = await client.get(f"https://www.tiktok.com/@{username}")
                if resp.status_code != 200:
                    return {}

                soup = BeautifulSoup(resp.text, "html.parser")

                name = username
                description = ""
                follower_count = 0

                og_title = soup.find("meta", property="og:title")
                if og_title:
                    title = og_title.get("content", "")
                    name_match = re.match(r'(.+?)\s*[\(@]', title)
                    if name_match:
                        name = name_match.group(1).strip()

                og_desc = soup.find("meta", property="og:description")
                if og_desc:
                    desc = og_desc.get("content", "")
                    description = desc
                    fan_match = re.search(r'([\d,.]+[KMkm]?)\s*Followers', desc, re.IGNORECASE)
                    if fan_match:
                        follower_count = self._parse_count(fan_match.group(1))

                emails = extract_emails(description)

                return {
                    "name": name,
                    "platform_username": username,
                    "profile_url": f"https://www.tiktok.com/@{username}",
                    "follower_count": follower_count,
                    "bio_text": description[:500],
                    "email": emails[0] if emails else None,
                    "raw_data": {"source": "tiktok_html"},
                }
        except Exception as e:
            print(f"TikTok scrape error for {profile_url}: {e}")
            return {}

    def _parse_count(self, text: str) -> int:
        text = text.strip().replace(",", "")
        multiplier = 1
        if text.lower().endswith("k"):
            multiplier = 1000
            text = text[:-1]
        elif text.lower().endswith("m"):
            multiplier = 1000000
            text = text[:-1]
        try:
            return int(float(text) * multiplier)
        except ValueError:
            return 0
