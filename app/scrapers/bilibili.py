import re
from app.scrapers.base import BaseScraper
from app.scrapers.utils import extract_emails


class BilibiliScraper(BaseScraper):
    """Bilibili UP master scraper using httpx."""
    PLATFORM_NAME = "bilibili"
    RATE_LIMIT_SECONDS = 3.0

    async def search_kols(self, keywords: list = None) -> list:
        from app.scrapers.search_engine import SearchEngineScraper
        se = SearchEngineScraper()
        return await se.search_platform_kols("bilibili", keywords)

    async def scrape_profile(self, profile_url: str) -> dict:
        """Scrape a Bilibili user space page."""
        await self._rate_limit()

        # Extract mid (user ID) from URL
        mid_match = re.search(r'space\.bilibili\.com/(\d+)', profile_url)
        if not mid_match:
            # Try video URL - extract uploader later
            return await self._scrape_from_video(profile_url)

        mid = mid_match.group(1)

        try:
            import httpx
            from app.scrapers.utils import random_ua

            headers = {
                "User-Agent": random_ua(),
                "Referer": "https://www.bilibili.com",
            }

            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15) as client:
                # Fetch user info via API
                resp = await client.get(f"https://api.bilibili.com/x/space/wbi/acc/info?mid={mid}")
                if resp.status_code != 200:
                    return {}

                data = resp.json()
                if data.get("code") != 0:
                    # Try alternative endpoint
                    return await self._scrape_profile_html(profile_url)

                info = data.get("data", {})
                name = info.get("name", "")
                bio = info.get("sign", "")
                follower_count = 0

                # Fetch follower count
                await self._rate_limit()
                stat_resp = await client.get(f"https://api.bilibili.com/x/relation/stat?vmid={mid}")
                if stat_resp.status_code == 200:
                    stat_data = stat_resp.json()
                    if stat_data.get("code") == 0:
                        follower_count = stat_data.get("data", {}).get("follower", 0)

                emails = extract_emails(bio)

                return {
                    "name": name,
                    "platform_username": mid,
                    "profile_url": f"https://space.bilibili.com/{mid}",
                    "follower_count": follower_count,
                    "bio_text": bio[:500],
                    "email": emails[0] if emails else None,
                    "is_verified": bool(info.get("official", {}).get("type", -1) >= 0),
                    "raw_data": {"mid": mid, "level": info.get("level", 0)},
                }
        except Exception as e:
            print(f"Bilibili scrape error for {profile_url}: {e}")
            return {}

    async def _scrape_from_video(self, video_url: str) -> dict:
        """Extract uploader info from a video page."""
        try:
            import httpx
            from bs4 import BeautifulSoup
            from app.scrapers.utils import random_ua

            async with httpx.AsyncClient(
                headers={"User-Agent": random_ua()},
                follow_redirects=True,
                timeout=15,
            ) as client:
                resp = await client.get(video_url)
                soup = BeautifulSoup(resp.text, "html.parser")

                # Try to find uploader space link
                space_link = soup.find("a", href=re.compile(r'space\.bilibili\.com/\d+'))
                if space_link:
                    space_url = space_link.get("href", "")
                    if space_url.startswith("//"):
                        space_url = "https:" + space_url
                    return await self.scrape_profile(space_url)
        except Exception:
            pass
        return {}

    async def _scrape_profile_html(self, profile_url: str) -> dict:
        """Fallback: scrape profile from HTML."""
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
                soup = BeautifulSoup(resp.text, "html.parser")

                name = ""
                og_title = soup.find("meta", property="og:title")
                if og_title:
                    name = og_title.get("content", "").split("的")[0].strip()

                if not name and soup.title:
                    name = (soup.title.string or "").split("的")[0].strip()

                description = ""
                og_desc = soup.find("meta", property="og:description")
                if og_desc:
                    description = og_desc.get("content", "")

                if not name:
                    return {}

                return {
                    "name": name,
                    "platform_username": "",
                    "profile_url": profile_url,
                    "bio_text": description[:500],
                    "raw_data": {"source": "bilibili_html"},
                }
        except Exception:
            return {}
