import re
from app.scrapers.base import BaseScraper
from app.scrapers.utils import extract_emails


class ThreadsScraper(BaseScraper):
    """Threads scraper - basic meta tag extraction."""
    PLATFORM_NAME = "threads"
    RATE_LIMIT_SECONDS = 5.0

    async def search_kols(self, keywords: list = None) -> list:
        from app.scrapers.search_engine import SearchEngineScraper
        se = SearchEngineScraper()
        return await se.search_platform_kols("threads", keywords)

    async def scrape_profile(self, profile_url: str) -> dict:
        await self._rate_limit()

        username = ""
        match = re.search(r'threads\.net/@([\w.]+)', profile_url)
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
                resp = await client.get(f"https://www.threads.net/@{username}")
                if resp.status_code != 200:
                    return {}

                soup = BeautifulSoup(resp.text, "html.parser")

                name = username
                description = ""

                og_title = soup.find("meta", property="og:title")
                if og_title:
                    title = og_title.get("content", "")
                    name_match = re.match(r'(.+?)\s*[\(@]', title)
                    if name_match:
                        name = name_match.group(1).strip()

                og_desc = soup.find("meta", property="og:description")
                if og_desc:
                    description = og_desc.get("content", "")

                emails = extract_emails(description)

                return {
                    "name": name,
                    "platform_username": username,
                    "profile_url": f"https://www.threads.net/@{username}",
                    "bio_text": description[:500],
                    "email": emails[0] if emails else None,
                    "raw_data": {"source": "threads_html"},
                }
        except Exception as e:
            print(f"Threads scrape error for {profile_url}: {e}")
            return {}
