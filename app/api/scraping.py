import asyncio
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import ScanJob, Platform
from app import templates

router = APIRouter(prefix="/scans")

# Map platform names to their scraper classes
SCRAPER_MAP = {
    "youtube": "app.scrapers.youtube.YouTubeScraper",
    "xiaohongshu": "app.scrapers.xiaohongshu.XiaohongshuScraper",
    "bilibili": "app.scrapers.bilibili.BilibiliScraper",
    "twitter": "app.scrapers.twitter.TwitterScraper",
    "instagram": "app.scrapers.instagram.InstagramScraper",
    "facebook": "app.scrapers.facebook.FacebookScraper",
    "tiktok": "app.scrapers.tiktok.TikTokScraper",
    "threads": "app.scrapers.threads.ThreadsScraper",
}


def get_scraper(platform_name: str):
    """Dynamically import and return a scraper instance."""
    import importlib
    class_path = SCRAPER_MAP.get(platform_name)
    if not class_path:
        return None
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


async def scan_platform(db, search, platform_name: str, keywords, job: ScanJob) -> int:
    """Run a scan for a single platform. Returns number of KOLs found."""
    from app.scrapers.utils import save_kol_from_scrape

    scraper = get_scraper(platform_name)
    if not scraper:
        return 0

    platform = db.query(Platform).filter(Platform.name == platform_name).first()
    if not platform or not platform.is_active:
        return 0

    kols_found = 0
    urls = await search.search_platform_kols(platform_name, keywords)

    for url in urls:
        try:
            profile_data = await scraper.scrape_profile(url)
            if profile_data and profile_data.get("name"):
                save_kol_from_scrape(db, profile_data, platform)
                kols_found += 1
        except Exception as e:
            job.error_log = (job.error_log or "") + f"\n[{platform_name}] Error scraping {url}: {e}"
            db.commit()

    return kols_found


async def run_scan_job(job_id: int, platform_name: str = None, keywords: list = None):
    """Background task to run a scan job."""
    db = SessionLocal()
    try:
        job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        try:
            from app.scrapers.search_engine import SearchEngineScraper
            search = SearchEngineScraper()
            kols_found = 0

            if platform_name:
                # Single platform scan
                kols_found = await scan_platform(db, search, platform_name, keywords, job)
            else:
                # Full discovery: scan all active platforms
                active_platforms = (
                    db.query(Platform)
                    .filter(Platform.is_active == True)
                    .order_by(Platform.priority)
                    .all()
                )
                for p in active_platforms:
                    try:
                        found = await scan_platform(db, search, p.name, keywords, job)
                        kols_found += found
                    except Exception as e:
                        job.error_log = (job.error_log or "") + f"\n[{p.name}] Platform error: {e}"
                        db.commit()

            # Auto-score all discovered KOLs
            try:
                from app.scoring.engine import score_all_kols
                score_all_kols(db)
            except Exception as e:
                job.error_log = (job.error_log or "") + f"\nScoring error: {e}"

            job.status = "completed"
            job.kols_found = kols_found
            job.completed_at = datetime.utcnow()
        except Exception as e:
            job.status = "failed"
            job.error_log = str(e)
            job.completed_at = datetime.utcnow()

        db.commit()
    finally:
        db.close()


@router.get("")
async def scan_list(request: Request, db: Session = Depends(get_db)):
    scans = db.query(ScanJob).order_by(ScanJob.created_at.desc()).limit(50).all()
    platforms = db.query(Platform).filter(Platform.is_active == True).order_by(Platform.priority).all()
    return templates.TemplateResponse("scan_config.html", {
        "request": request,
        "scans": scans,
        "platforms": platforms,
    })


@router.post("/trigger")
async def trigger_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    platform_name: str = Form(None),
    keywords: str = Form(""),
):
    import json
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not kw_list:
        kw_list = None  # Will use default keywords

    platform_id = None
    if platform_name:
        platform = db.query(Platform).filter(Platform.name == platform_name).first()
        if platform:
            platform_id = platform.id

    job = ScanJob(
        job_type="platform_scan" if platform_name else "full_discovery",
        platform_id=platform_id,
        status="pending",
        search_keywords=json.dumps(kw_list, ensure_ascii=False) if kw_list else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_scan_job, job.id, platform_name, kw_list)

    return templates.TemplateResponse("_scan_triggered.html", {
        "request": request,
        "job": job,
    })
