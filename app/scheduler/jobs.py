"""Scheduled job definitions for periodic KOL scanning and maintenance."""
from datetime import datetime


async def full_discovery_scan():
    """Scan all active platforms for new KOLs."""
    from app.database import SessionLocal
    from app.models import ScanJob
    from app.api.scraping import run_scan_job

    db = SessionLocal()
    try:
        job = ScanJob(job_type="full_discovery", status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    await run_scan_job(job_id)


async def platform_scan(platform_name: str):
    """Scan a specific platform for new KOLs."""
    from app.database import SessionLocal
    from app.models import ScanJob, Platform
    from app.api.scraping import run_scan_job

    db = SessionLocal()
    try:
        platform = db.query(Platform).filter(Platform.name == platform_name).first()
        job = ScanJob(
            job_type="platform_scan",
            platform_id=platform.id if platform else None,
            status="pending",
        )
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    await run_scan_job(job_id, platform_name=platform_name)


async def rescore_all():
    """Re-score all KOLs with latest data."""
    from app.database import SessionLocal
    from app.scoring.engine import score_all_kols

    db = SessionLocal()
    try:
        count = score_all_kols(db)
        print(f"Re-scored {count} KOLs")
    finally:
        db.close()
