import re
from app.scrapers.base import BaseScraper
from app.scrapers.utils import extract_emails


class FacebookScraper(BaseScraper):
    """Facebook page scraper - basic meta tag extraction."""
    PLATFORM_NAME = "facebook"
    RATE_LIMIT_SECONDS = 5.0

    async def search_kols(self, keywords: list = None) -> list:
        from app.scrapers.search_engine import SearchEngineScraper
        se = SearchEngineScraper()
        return await se.search_platform_kols("facebook", keywords)

    async def scrape_profile(self, profile_url: str) -> dict:
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

                name = ""
                description = ""

                og_title = soup.find("meta", property="og:title")
                if og_title:
                    name = og_title.get("content", "")

                og_desc = soup.find("meta", property="og:description")
                if og_desc:
                    description = og_desc.get("content", "")

                if not name:
                    return {}

                # Extract username from URL
                username = ""
                match = re.search(r'facebook\.com/([\w.]+)/?', profile_url)
                if match:
                    username = match.group(1)

                emails = extract_emails(description)

                return {
                    "name": name,
                    "platform_username": username,
                    "profile_url": profile_url,
                    "bio_text": description[:500],
                    "email": emails[0] if emails else None,
                    "raw_data": {"source": "facebook_html"},
                }
        except Exception as e:
            print(f"Facebook scrape error for {profile_url}: {e}")
            return {}
