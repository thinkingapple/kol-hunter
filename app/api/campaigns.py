from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db, SessionLocal
from app.models import OutreachCampaign, OutreachEmail, EmailTemplate, KOL
from app import templates

router = APIRouter(prefix="/campaigns")


@router.get("")
async def campaign_list(request: Request, db: Session = Depends(get_db)):
    campaigns = db.query(OutreachCampaign).order_by(OutreachCampaign.created_at.desc()).all()
    return templates.TemplateResponse("campaigns.html", {
        "request": request,
        "campaigns": campaigns,
    })


@router.post("/create")
async def create_campaign(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    description: str = Form(""),
    language: str = Form("zh"),
    template_id: int = Form(None),
):
    campaign = OutreachCampaign(
        name=name,
        description=description,
        language=language,
        template_id=template_id,
    )
    db.add(campaign)
    db.commit()
    return RedirectResponse(f"/campaigns/{campaign.id}", status_code=303)


@router.get("/{campaign_id}")
async def campaign_detail(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    campaign = db.query(OutreachCampaign).options(
        joinedload(OutreachCampaign.emails).joinedload(OutreachEmail.kol),
        joinedload(OutreachCampaign.template),
    ).filter(OutreachCampaign.id == campaign_id).first()
    if not campaign:
        return RedirectResponse("/campaigns", status_code=303)

    # Get available KOLs with email for adding to campaign
    available_kols = (
        db.query(KOL)
        .filter(KOL.email.isnot(None), KOL.email != "")
        .filter(KOL.status.notin_(["blacklisted", "rejected"]))
        .order_by(KOL.total_score.desc())
        .all()
    )

    email_templates = db.query(EmailTemplate).all()

    return templates.TemplateResponse("campaign_detail.html", {
        "request": request,
        "campaign": campaign,
        "available_kols": available_kols,
        "email_templates": email_templates,
    })


@router.post("/{campaign_id}/add-kols")
async def add_kols_to_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    kol_ids: str = Form(""),
):
    campaign = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not campaign:
        return RedirectResponse("/campaigns", status_code=303)

    template = None
    if campaign.template_id:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == campaign.template_id).first()

    ids = [int(x.strip()) for x in kol_ids.split(",") if x.strip()]
    for kol_id in ids:
        kol = db.query(KOL).filter(KOL.id == kol_id).first()
        if not kol or not kol.email:
            continue
        # Check not already in campaign
        existing = db.query(OutreachEmail).filter(
            OutreachEmail.campaign_id == campaign_id,
            OutreachEmail.kol_id == kol_id,
        ).first()
        if existing:
            continue

        subject = template.subject_template.replace("{{ kol.name }}", kol.name) if template else f"{kol.name} - Partnership Inquiry"
        body = template.body_template.replace("{{ kol.name }}", kol.name) if template else f"Dear {kol.name},\n\nWe would like to discuss a partnership opportunity."

        email = OutreachEmail(
            campaign_id=campaign_id,
            kol_id=kol_id,
            to_email=kol.email,
            subject=subject,
            body_html=body,
            status="pending",
        )
        db.add(email)

    db.commit()
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)


async def send_campaign_emails(campaign_id: int):
    """Background task to send emails for a campaign."""
    import asyncio
    db = SessionLocal()
    try:
        emails = db.query(OutreachEmail).filter(
            OutreachEmail.campaign_id == campaign_id,
            OutreachEmail.status == "pending",
        ).all()

        for email_record in emails:
            try:
                from app.outreach.manager import send_single_email
                success = await send_single_email(email_record.to_email, email_record.subject, email_record.body_html)
                if success:
                    email_record.status = "sent"
                    email_record.sent_at = datetime.utcnow()
                else:
                    email_record.status = "failed"
                    email_record.error_message = "Send returned failure"
                db.commit()
                await asyncio.sleep(30)  # Rate limit
            except Exception as e:
                email_record.status = "failed"
                email_record.error_message = str(e)
                db.commit()

        campaign = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
        if campaign:
            campaign.total_sent = db.query(OutreachEmail).filter(
                OutreachEmail.campaign_id == campaign_id,
                OutreachEmail.status == "sent",
            ).count()
            campaign.status = "completed"
            db.commit()
    finally:
        db.close()


@router.post("/{campaign_id}/send")
async def send_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    campaign = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if campaign:
        campaign.status = "active"
        db.commit()
        background_tasks.add_task(send_campaign_emails, campaign_id)
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)
