from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
import csv
import io

from app.database import get_db
from app.models import KOL, KOLProfile, Platform
from app import templates

router = APIRouter(prefix="/kols")


@router.get("")
async def kol_list(
    request: Request,
    db: Session = Depends(get_db),
    tier: str = None,
    region: str = None,
    status: str = None,
    platform: str = None,
    has_email: bool = None,
    q: str = None,
    sort: str = "total_score",
    order: str = "desc",
    page: int = 1,
    per_page: int = 50,
):
    query = db.query(KOL).options(joinedload(KOL.profiles).joinedload(KOLProfile.platform))

    if tier:
        query = query.filter(KOL.tier == tier)
    if region:
        query = query.filter(KOL.region == region)
    if status:
        query = query.filter(KOL.status == status)
    if has_email:
        query = query.filter(KOL.email.isnot(None), KOL.email != "")
    if q:
        query = query.filter(or_(KOL.name.contains(q), KOL.name_zh.contains(q)))
    if platform:
        query = query.join(KOL.profiles).join(KOLProfile.platform).filter(Platform.name == platform)

    sort_col = getattr(KOL, sort, KOL.total_score)
    if order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = query.count()
    kols = query.offset((page - 1) * per_page).limit(per_page).all()
    # Deduplicate (joinedload may produce duplicates)
    seen = set()
    unique_kols = []
    for k in kols:
        if k.id not in seen:
            seen.add(k.id)
            unique_kols.append(k)

    platforms = db.query(Platform).filter(Platform.is_active == True).order_by(Platform.priority).all()

    return templates.TemplateResponse("kol_list.html", {
        "request": request,
        "kols": unique_kols,
        "total": total,
        "page": page,
        "per_page": per_page,
        "platforms": platforms,
        "filters": {"tier": tier, "region": region, "status": status, "platform": platform, "has_email": has_email, "q": q},
        "sort": sort,
        "order": order,
    })


@router.get("/export")
async def export_csv(db: Session = Depends(get_db)):
    kols = db.query(KOL).options(joinedload(KOL.profiles).joinedload(KOLProfile.platform)).order_by(KOL.total_score.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Name (ZH)", "Email", "Region", "Score", "Tier", "Status", "Platforms", "Total Followers"])
    seen = set()
    for k in kols:
        if k.id in seen:
            continue
        seen.add(k.id)
        platforms = ", ".join(p.platform.display_name for p in k.profiles if p.platform)
        writer.writerow([k.name, k.name_zh or "", k.email or "", k.region, f"{k.total_score:.1f}", k.tier, k.status, platforms, k.total_followers])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kols_export.csv"},
    )


@router.get("/{kol_id}")
async def kol_detail(kol_id: int, request: Request, db: Session = Depends(get_db)):
    kol = db.query(KOL).options(
        joinedload(KOL.profiles).joinedload(KOLProfile.platform),
        joinedload(KOL.outreach_emails),
    ).filter(KOL.id == kol_id).first()
    if not kol:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse("kol_detail.html", {"request": request, "kol": kol})


@router.post("/{kol_id}/update")
async def update_kol(
    kol_id: int,
    request: Request,
    db: Session = Depends(get_db),
    status: str = Form(None),
    notes: str = Form(None),
    email: str = Form(None),
    tags: str = Form(None),
):
    kol = db.query(KOL).filter(KOL.id == kol_id).first()
    if not kol:
        return RedirectResponse("/kols", status_code=303)
    if status is not None:
        kol.status = status
    if notes is not None:
        kol.notes = notes
    if email is not None:
        kol.email = email
    if tags is not None:
        kol.tags = tags
    db.commit()
    return RedirectResponse(f"/kols/{kol_id}", status_code=303)
