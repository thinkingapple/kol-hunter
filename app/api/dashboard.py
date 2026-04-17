import json
from pathlib import Path

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import KOL, KOLProfile, Platform, ScanJob, OutreachEmail
from app import templates

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_market_data() -> dict:
    p = DATA_DIR / "platform_market_data.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"platforms": []}


@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total_kols = db.query(func.count(KOL.id)).scalar()
    tier_counts = dict(
        db.query(KOL.tier, func.count(KOL.id))
        .group_by(KOL.tier)
        .all()
    )
    kols_with_email = db.query(func.count(KOL.id)).filter(KOL.email.isnot(None), KOL.email != "").scalar()
    total_emails_sent = db.query(func.count(OutreachEmail.id)).filter(OutreachEmail.status == "sent").scalar()

    # 平台大盘统计：KOL数、总粉丝、平均互动率
    platform_stats_raw = (
        db.query(
            Platform.name,
            Platform.display_name,
            func.count(KOLProfile.id),
            func.coalesce(func.sum(KOLProfile.follower_count), 0),
            func.coalesce(func.avg(KOLProfile.engagement_rate), 0),
        )
        .outerjoin(KOLProfile, Platform.id == KOLProfile.platform_id)
        .filter(Platform.is_active == True)
        .group_by(Platform.id)
        .order_by(func.count(KOLProfile.id).desc())
        .all()
    )
    platform_stats = [
        {
            "name": r[0],
            "display_name": r[1],
            "kol_count": r[2],
            "total_followers": r[3] or 0,
            "avg_engagement": round(r[4] or 0, 2),
        }
        for r in platform_stats_raw
    ]

    platform_counts = (
        db.query(Platform.display_name, func.count(KOLProfile.id))
        .join(KOLProfile, Platform.id == KOLProfile.platform_id)
        .group_by(Platform.display_name)
        .all()
    )

    status_counts = dict(
        db.query(KOL.status, func.count(KOL.id))
        .group_by(KOL.status)
        .all()
    )

    recent_scans = (
        db.query(ScanJob)
        .order_by(ScanJob.created_at.desc())
        .limit(10)
        .all()
    )

    # 行业市场大盘数据
    market_data = _load_market_data()
    market_platforms = market_data.get("platforms", [])
    market_updated = market_data.get("updated_at", "")
    market_methodology = market_data.get("methodology", {})

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_kols": total_kols,
        "tier_counts": tier_counts,
        "kols_with_email": kols_with_email,
        "total_emails_sent": total_emails_sent,
        "platform_stats": platform_stats,
        "platform_counts": platform_counts,
        "status_counts": status_counts,
        "recent_scans": recent_scans,
        "market_platforms": market_platforms,
        "market_updated": market_updated,
        "market_methodology": market_methodology,
    })
