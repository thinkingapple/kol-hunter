import json
from sqlalchemy.orm import Session

import config
from app.models import KOL, KOLProfile
from app.scoring.factors import (
    calc_reach_score,
    calc_engagement_score,
    calc_relevance_score,
    calc_region_score,
    calc_recency_score,
    calc_competitor_score,
    detect_region,
)
from app.scoring.competitor_detector import detect_competitor_mentions


def score_kol(kol: KOL, db: Session = None) -> dict:
    """Calculate composite score for a KOL.

    Returns dict with individual factor scores and total.
    """
    weights = config.SCORING_WEIGHTS

    # Aggregate data across profiles
    total_followers = kol.total_followers
    engagement_rates = []
    all_bio_text = ""
    last_post_dates = []

    for profile in kol.profiles:
        if profile.engagement_rate and profile.engagement_rate > 0:
            engagement_rates.append(profile.engagement_rate)
        if profile.bio_text:
            all_bio_text += " " + profile.bio_text
        if profile.last_post_date:
            last_post_dates.append(profile.last_post_date)

    avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
    latest_post = max(last_post_dates) if last_post_dates else None

    # Detect region if not set
    if kol.region == "unknown":
        detected = detect_region(all_bio_text, kol.language)
        if detected != "unknown":
            kol.region = detected

    # Detect competitor collaborations from bio text
    competitors = detect_competitor_mentions(all_bio_text)
    if competitors and not kol.competitor_history_list:
        kol.competitor_history = json.dumps(competitors, ensure_ascii=False)

    # Calculate individual factor scores
    reach = calc_reach_score(total_followers)
    engagement = calc_engagement_score(avg_engagement)
    relevance = calc_relevance_score(all_bio_text)
    region = calc_region_score(kol.region)
    recency = calc_recency_score(latest_post)
    competitor = calc_competitor_score(kol.competitor_history_list)

    # Weighted composite
    total = (
        reach * weights["reach"]
        + engagement * weights["engagement"]
        + relevance * weights["relevance"]
        + region * weights["region"]
        + recency * weights["recency"]
        + competitor * weights["competitor"]
    )

    # Assign tier
    if total >= 75:
        tier = "A"
    elif total >= 50:
        tier = "B"
    elif total >= 25:
        tier = "C"
    else:
        tier = "D"

    # Update KOL
    kol.total_score = round(total, 2)
    kol.tier = tier

    # Also update content relevance on each profile
    for profile in kol.profiles:
        bio = profile.bio_text or ""
        profile.content_relevance_score = calc_relevance_score(bio) / 100.0

    return {
        "reach": round(reach, 2),
        "engagement": round(engagement, 2),
        "relevance": round(relevance, 2),
        "region": round(region, 2),
        "recency": round(recency, 2),
        "competitor": round(competitor, 2),
        "total": round(total, 2),
        "tier": tier,
    }


def score_all_kols(db: Session):
    """Re-score all KOLs in the database."""
    kols = db.query(KOL).all()
    for kol in kols:
        score_kol(kol, db)
    db.commit()
    return len(kols)
