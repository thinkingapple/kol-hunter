import asyncio
import json
import re
import subprocess
from datetime import datetime

from app.scrapers.base import BaseScraper
from app.scrapers.utils import extract_emails


class YouTubeScraper(BaseScraper):
    PLATFORM_NAME = "youtube"
    RATE_LIMIT_SECONDS = 3.0

    async def search_kols(self, keywords: list = None) -> list:
        """Use search engine for discovery - this method delegates."""
        from app.scrapers.search_engine import SearchEngineScraper
        se = SearchEngineScraper()
        return await se.search_platform_kols("youtube", keywords)

    async def scrape_profile(self, profile_url: str) -> dict:
        """Scrape a YouTube channel/video URL using yt-dlp.

        Returns structured profile data dict.
        """
        await self._rate_limit()

        # Normalize URL to channel URL
        channel_url = self._normalize_to_channel(profile_url)
        if not channel_url:
            return {}

        try:
            # Get channel info via yt-dlp
            channel_data = await self._run_ytdlp(channel_url)
            if not channel_data:
                return {}

            # Get recent videos for engagement metrics
            videos_data = await self._get_recent_videos(channel_url, count=10)

            return self._build_profile(channel_data, videos_data, channel_url)
        except Exception as e:
            print(f"YouTube scrape error for {profile_url}: {e}")
            return {}

    def _normalize_to_channel(self, url: str) -> str:
        """Convert any YouTube URL to a channel/videos URL."""
        # Already a channel URL
        if re.search(r'youtube\.com/(@[\w.-]+|channel/[\w-]+|c/[\w.-]+|user/[\w.-]+)', url):
            # Ensure we target the videos tab for listing
            base = re.sub(r'/(videos|about|playlists|featured).*$', '', url)
            return base
        # Video URL - we'll extract channel from video metadata
        if re.search(r'youtube\.com/watch\?v=|youtu\.be/', url):
            return url  # Will handle in _run_ytdlp
        return url

    async def _run_ytdlp(self, url: str) -> dict:
        """Run yt-dlp to extract metadata."""
        await self._rate_limit()
        cmd = [
            "python3", "-m", "yt_dlp",
            "--dump-json",
            "--playlist-items", "1",
            "--no-download",
            "--no-warnings",
            "--quiet",
            url,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if stdout:
                return json.loads(stdout.decode("utf-8", errors="ignore"))
        except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
            print(f"yt-dlp error: {e}")
        return {}

    async def _get_recent_videos(self, channel_url: str, count: int = 10) -> list:
        """Get metadata for recent videos on a channel."""
        videos_url = channel_url.rstrip("/") + "/videos"
        cmd = [
            "python3", "-m", "yt_dlp",
            "--dump-json",
            "--playlist-items", f"1:{count}",
            "--no-download",
            "--no-warnings",
            "--quiet",
            "--flat-playlist",
            videos_url,
        ]
        videos = []
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if stdout:
                for line in stdout.decode("utf-8", errors="ignore").strip().split("\n"):
                    if line.strip():
                        try:
                            videos.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"yt-dlp videos error: {e}")
        return videos

    def _build_profile(self, channel_data: dict, videos: list, channel_url: str) -> dict:
        """Build a structured profile dict from yt-dlp data."""
        channel_name = channel_data.get("channel", "") or channel_data.get("uploader", "Unknown")
        channel_id = channel_data.get("channel_id", "")
        uploader_id = channel_data.get("uploader_id", "") or channel_data.get("channel_url", "")

        subscriber_count = channel_data.get("channel_follower_count") or 0
        description = channel_data.get("description", "") or ""

        # Derive profile URL
        if channel_id:
            profile_url = f"https://www.youtube.com/channel/{channel_id}"
        elif uploader_id and uploader_id.startswith("@"):
            profile_url = f"https://www.youtube.com/{uploader_id}"
        else:
            profile_url = channel_url

        # Compute engagement metrics from videos
        avg_views = 0
        avg_likes = 0.0
        avg_comments = 0.0
        post_count = len(videos)

        if videos:
            view_counts = [v.get("view_count", 0) or 0 for v in videos]
            like_counts = [v.get("like_count", 0) or 0 for v in videos]
            comment_counts = [v.get("comment_count", 0) or 0 for v in videos]

            avg_views = int(sum(view_counts) / len(view_counts)) if view_counts else 0
            avg_likes = sum(like_counts) / len(like_counts) if like_counts else 0.0
            avg_comments = sum(comment_counts) / len(comment_counts) if comment_counts else 0.0

        # Engagement rate: (avg_likes + avg_comments) / subscriber_count * 100
        engagement_rate = 0.0
        if subscriber_count > 0:
            engagement_rate = (avg_likes + avg_comments) / subscriber_count * 100

        # Extract email from description
        emails = extract_emails(description)
        email = emails[0] if emails else None

        # Username / handle
        platform_username = channel_data.get("uploader_id", "")
        if platform_username and platform_username.startswith("@"):
            platform_username = platform_username[1:]

        # Last video upload date
        last_post_date = None
        if videos:
            upload_date = videos[0].get("upload_date")
            if upload_date:
                try:
                    last_post_date = datetime.strptime(upload_date, "%Y%m%d")
                except ValueError:
                    pass

        return {
            "name": channel_name,
            "platform_username": platform_username,
            "profile_url": profile_url,
            "follower_count": subscriber_count,
            "subscriber_count": subscriber_count,
            "bio_text": description[:500] if description else "",
            "avg_views": avg_views,
            "avg_likes": avg_likes,
            "avg_comments": avg_comments,
            "engagement_rate": round(engagement_rate, 4),
            "post_count": post_count,
            "email": email,
            "is_verified": channel_data.get("channel_is_verified", False),
            "last_post_date": last_post_date,
            "raw_data": {
                "channel_id": channel_id,
                "subscriber_count": subscriber_count,
                "video_count": post_count,
            },
        }
