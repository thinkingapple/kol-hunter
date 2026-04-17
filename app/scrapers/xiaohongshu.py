import re
from app.scrapers.base import BaseScraper
from app.scrapers.utils import extract_emails


class XiaohongshuScraper(BaseScraper):
    """Xiaohongshu / RedNote scraper using httpx + BeautifulSoup.

    Falls back to basic HTML scraping. For full JS rendering,
    Playwright can be added later.
    """
    PLATFORM_NAME = "xiaohongshu"
    RATE_LIMIT_SECONDS = 5.0

    async def search_kols(self, keywords: list = None) -> list:
        from app.scrapers.search_engine import SearchEngineScraper
        se = SearchEngineScraper()
        return await se.search_platform_kols("xiaohongshu", keywords)

    async def scrape_profile(self, profile_url: str) -> dict:
        """Scrape a Xiaohongshu user profile page."""
        await self._rate_limit()

        try:
            import httpx
            from bs4 import BeautifulSoup
            from app.scrapers.utils import random_ua

            async with httpx.AsyncClient(
                headers={"User-Agent": random_ua()},
                follow_redirects=True,
                timeout=15,
            ) as client:
                resp = await client.get(profile_url)
                if resp.status_code != 200:
                    return {}

                soup = BeautifulSoup(resp.text, "html.parser")

                # Try to extract from meta tags (works even without JS)
                name = ""
                description = ""
                follower_count = 0

                # og:title often has username
                og_title = soup.find("meta", property="og:title")
                if og_title:
                    name = og_title.get("content", "")

                # og:description
                og_desc = soup.find("meta", property="og:description")
                if og_desc:
                    description = og_desc.get("content", "")

                # Try extracting from page title
                if not name and soup.title:
                    name = soup.title.string or ""
                    name = name.split("-")[0].strip() if name else ""

                # Extract username from URL
                username = ""
                match = re.search(r'/user/profile/(\w+)', profile_url)
                if match:
                    username = match.group(1)

                # Extract follower count from page text
                text = soup.get_text()
                fan_match = re.search(r'(\d[\d,.]*)\s*(?:粉丝|粉絲|followers)', text, re.IGNORECASE)
                if fan_match:
                    follower_count = int(fan_match.group(1).replace(",", "").replace(".", ""))

                emails = extract_emails(description + " " + text[:2000])

                if not name:
                    return {}

                return {
                    "name": name,
                    "platform_username": username,
                    "profile_url": profile_url,
                    "follower_count": follower_count,
                    "bio_text": description[:500],
                    "email": emails[0] if emails else None,
                    "raw_data": {"source": "xiaohongshu_html"},
                }
        except Exception as e:
            print(f"Xiaohongshu scrape error for {profile_url}: {e}")
            return {}
