import re
from app.scrapers.base import BaseScraper
from app.scrapers.utils import extract_emails


class TwitterScraper(BaseScraper):
    """Twitter/X scraper using httpx for basic profile data."""
    PLATFORM_NAME = "twitter"
    RATE_LIMIT_SECONDS = 5.0

    async def search_kols(self, keywords: list = None) -> list:
        from app.scrapers.search_engine import SearchEngineScraper
        se = SearchEngineScraper()
        return await se.search_platform_kols("twitter", keywords)

    async def scrape_profile(self, profile_url: str) -> dict:
        """Scrape basic Twitter/X profile info from the HTML page."""
        await self._rate_limit()

        # Extract username from URL
        username = ""
        match = re.search(r'(?:twitter|x)\.com/(\w+)/?$', profile_url)
        if match:
            username = match.group(1)

        if not username or username.lower() in ("home", "search", "explore", "settings", "i"):
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
                # Try nitter instances or basic X page
                resp = await client.get(f"https://x.com/{username}")
                if resp.status_code != 200:
                    return {}

                soup = BeautifulSoup(resp.text, "html.parser")

                # Extract from meta tags
                name = username
                description = ""

                og_title = soup.find("meta", property="og:title")
                if og_title:
                    title_content = og_title.get("content", "")
                    # Format: "Name (@handle) / X"
                    name_match = re.match(r'(.+?)\s*\(@', title_content)
                    if name_match:
                        name = name_match.group(1).strip()

                og_desc = soup.find("meta", property="og:description")
                if og_desc:
                    description = og_desc.get("content", "")

                # Try to extract follower count from description or page
                follower_count = 0
                text = soup.get_text()
                fan_match = re.search(r'([\d,.]+[KMkm]?)\s*Followers', text, re.IGNORECASE)
                if fan_match:
                    follower_count = self._parse_count(fan_match.group(1))

                emails = extract_emails(description)

                return {
                    "name": name,
                    "platform_username": username,
                    "profile_url": f"https://x.com/{username}",
                    "follower_count": follower_count,
                    "bio_text": description[:500],
                    "email": emails[0] if emails else None,
                    "raw_data": {"source": "twitter_html"},
                }
        except Exception as e:
            print(f"Twitter scrape error for {profile_url}: {e}")
            return {}

    def _parse_count(self, text: str) -> int:
        """Parse follower count like '12.3K' or '1.5M' to integer."""
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
