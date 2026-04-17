from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import KOL, KOLProfile, Platform, ScanJob, OutreachEmail
from app import templates

router = APIRouter()


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

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_kols": total_kols,
        "tier_counts": tier_counts,
        "kols_with_email": kols_with_email,
        "total_emails_sent": total_emails_sent,
        "platform_counts": platform_counts,
        "status_counts": status_counts,
        "recent_scans": recent_scans,
    })
