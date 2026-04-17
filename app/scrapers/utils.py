import random
import re
import json
from datetime import datetime

from sqlalchemy.orm import Session
from app.models import KOL, KOLProfile, Platform

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def extract_emails(text: str) -> list:
    """Extract email addresses from text."""
    if not text:
        return []
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(pattern, text)))


def extract_youtube_channel_id(url: str) -> str:
    """Extract YouTube channel ID or handle from URL."""
    patterns = [
        r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
        r'youtube\.com/@([a-zA-Z0-9_.-]+)',
        r'youtube\.com/c/([a-zA-Z0-9_.-]+)',
        r'youtube\.com/user/([a-zA-Z0-9_.-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def save_kol_from_scrape(db: Session, profile_data: dict, platform: Platform) -> KOL:
    """Save or update a KOL from scraped profile data.

    profile_data should have keys:
    - name: str
    - platform_username: str
    - profile_url: str
    - follower_count: int (optional)
    - subscriber_count: int (optional)
    - bio_text: str (optional)
    - avg_views: int (optional)
    - avg_likes: float (optional)
    - avg_comments: float (optional)
    - engagement_rate: float (optional)
    - post_count: int (optional)
    - email: str (optional)
    - is_verified: bool (optional)
    - content_relevance_score: float (optional)
    - last_post_date: datetime (optional)
    - raw_data: dict (optional)
    """
    name = profile_data.get("name", "Unknown")
    profile_url = profile_data.get("profile_url", "")

    # Check if profile already exists
    existing_profile = (
        db.query(KOLProfile)
        .filter(KOLProfile.profile_url == profile_url, KOLProfile.platform_id == platform.id)
        .first()
    )

    if existing_profile:
        kol = existing_profile.kol
        # Update profile data
        for field in [
            "follower_count", "subscriber_count", "bio_text", "avg_views",
            "avg_likes", "avg_comments", "engagement_rate", "post_count",
            "is_verified", "content_relevance_score", "last_post_date",
        ]:
            val = profile_data.get(field)
            if val is not None:
                setattr(existing_profile, field, val)
        if profile_data.get("raw_data"):
            existing_profile.raw_data = json.dumps(profile_data["raw_data"], ensure_ascii=False, default=str)
        existing_profile.platform_username = profile_data.get("platform_username", existing_profile.platform_username)
        existing_profile.updated_at = datetime.utcnow()
    else:
        # Try to find existing KOL by name (fuzzy)
        kol = db.query(KOL).filter(KOL.name == name).first()
        if not kol:
            kol = KOL(
                name=name,
                region="unknown",
                language="mixed",
            )
            db.add(kol)
            db.flush()

        profile = KOLProfile(
            kol_id=kol.id,
            platform_id=platform.id,
            platform_username=profile_data.get("platform_username", ""),
            profile_url=profile_url,
            follower_count=profile_data.get("follower_count"),
            subscriber_count=profile_data.get("subscriber_count"),
            bio_text=profile_data.get("bio_text"),
            avg_views=profile_data.get("avg_views"),
            avg_likes=profile_data.get("avg_likes"),
            avg_comments=profile_data.get("avg_comments"),
            engagement_rate=profile_data.get("engagement_rate"),
            post_count=profile_data.get("post_count"),
            is_verified=profile_data.get("is_verified", False),
            content_relevance_score=profile_data.get("content_relevance_score", 0.0),
            last_post_date=profile_data.get("last_post_date"),
            raw_data=json.dumps(profile_data.get("raw_data", {}), ensure_ascii=False, default=str),
        )
        db.add(profile)

    # Update KOL email if found
    email = profile_data.get("email")
    if email and not kol.email:
        kol.email = email

    # Update bio summary
    bio = profile_data.get("bio_text")
    if bio and not kol.bio_summary:
        kol.bio_summary = bio[:200]

    kol.last_scanned_at = datetime.utcnow()
    kol.updated_at = datetime.utcnow()
    db.commit()
    return kol
