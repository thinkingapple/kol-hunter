from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailTemplate, ScheduledTask, Platform
from app import templates

router = APIRouter(prefix="/settings")


@router.get("")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    email_templates = db.query(EmailTemplate).order_by(EmailTemplate.language, EmailTemplate.template_type).all()
    scheduled_tasks = db.query(ScheduledTask).all()
    platforms = db.query(Platform).order_by(Platform.priority).all()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "email_templates": email_templates,
        "scheduled_tasks": scheduled_tasks,
        "platforms": platforms,
    })


@router.get("/templates")
async def templates_page(request: Request, db: Session = Depends(get_db)):
    email_templates = db.query(EmailTemplate).order_by(EmailTemplate.language, EmailTemplate.template_type).all()
    return templates.TemplateResponse("templates_mgmt.html", {
        "request": request,
        "email_templates": email_templates,
    })


@router.post("/templates/create")
async def create_template(
    db: Session = Depends(get_db),
    name: str = Form(...),
    language: str = Form("zh"),
    template_type: str = Form("initial_outreach"),
    subject_template: str = Form(...),
    body_template: str = Form(...),
):
    tmpl = EmailTemplate(
        name=name,
        language=language,
        template_type=template_type,
        subject_template=subject_template,
        body_template=body_template,
    )
    db.add(tmpl)
    db.commit()
    return RedirectResponse("/settings/templates", status_code=303)


@router.post("/templates/{tmpl_id}/update")
async def update_template(
    tmpl_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    subject_template: str = Form(...),
    body_template: str = Form(...),
):
    tmpl = db.query(EmailTemplate).filter(EmailTemplate.id == tmpl_id).first()
    if tmpl:
        tmpl.name = name
        tmpl.subject_template = subject_template
        tmpl.body_template = body_template
        db.commit()
    return RedirectResponse("/settings/templates", status_code=303)


@router.post("/templates/{tmpl_id}/delete")
async def delete_template(tmpl_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(EmailTemplate).filter(EmailTemplate.id == tmpl_id).first()
    if tmpl:
        db.delete(tmpl)
        db.commit()
    return RedirectResponse("/settings/templates", status_code=303)


@router.post("/platforms/{platform_id}/toggle")
async def toggle_platform(platform_id: int, db: Session = Depends(get_db)):
    platform = db.query(Platform).filter(Platform.id == platform_id).first()
    if platform:
        platform.is_active = not platform.is_active
        db.commit()
    return RedirectResponse("/settings", status_code=303)
