from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.database import engine, Base, SessionLocal
from app.models import Platform

FRONTEND_DIR = Path(__file__).parent / "frontend"


def seed_platforms(db):
    """Seed the platforms table with default platforms."""
    defaults = [
        ("youtube", "YouTube", 1),
        ("xiaohongshu", "小红书", 2),
        ("bilibili", "Bilibili", 3),
        ("twitter", "X / Twitter", 4),
        ("instagram", "Instagram", 5),
        ("facebook", "Facebook", 6),
        ("tiktok", "TikTok", 7),
        ("threads", "Threads", 8),
    ]
    for name, display_name, priority in defaults:
        existing = db.query(Platform).filter(Platform.name == name).first()
        if not existing:
            db.add(Platform(name=name, display_name=display_name, priority=priority, is_active=True))
    db.commit()


def create_app() -> FastAPI:
    app = FastAPI(title="KOL Hunter", description="富途牛牛 KOL 自动发现与建联工具")

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Seed data
    db = SessionLocal()
    try:
        seed_platforms(db)
    finally:
        db.close()

    # Static files
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

    # Register routers
    from app.api import dashboard, kols, scraping, campaigns, settings, traffic_map
    app.include_router(traffic_map.router)
    app.include_router(dashboard.router)
    app.include_router(kols.router)
    app.include_router(scraping.router)
    app.include_router(campaigns.router)
    app.include_router(settings.router)

    # Scheduler lifecycle
    from app.scheduler.manager import scheduler

    @app.on_event("startup")
    async def startup():
        scheduler.start()
        # Load scheduled tasks from DB
        _load_scheduled_tasks()

    @app.on_event("shutdown")
    async def shutdown():
        scheduler.shutdown()

    return app


def _load_scheduled_tasks():
    """Load persisted scheduled tasks from DB and register with scheduler."""
    from app.scheduler.manager import scheduler
    from app.scheduler.jobs import full_discovery_scan, platform_scan, rescore_all
    from app.models import ScheduledTask

    db = SessionLocal()
    try:
        tasks = db.query(ScheduledTask).filter(ScheduledTask.is_active == True).all()
        for task in tasks:
            job_id = f"scheduled_{task.id}"
            if task.task_type == "full_scan":
                scheduler.add_job(full_discovery_scan, task.cron_expression, job_id)
            elif task.task_type == "platform_scan" and task.platform:
                scheduler.add_job(
                    platform_scan, task.cron_expression, job_id,
                    kwargs={"platform_name": task.platform.name},
                )
            elif task.task_type == "rescore":
                scheduler.add_job(rescore_all, task.cron_expression, job_id)
    except Exception as e:
        print(f"Error loading scheduled tasks: {e}")
    finally:
        db.close()


templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
