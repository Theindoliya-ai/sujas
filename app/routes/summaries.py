from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date as date_type, date
import re

from app.database import get_db
from app.models import SujasSummary, AdminUser
from app.schemas import (
    SujasSummaryResponse,
    PaginatedResponse,
    normalize_month,
    VALID_MONTHS,
)
from app.utils import get_current_admin, save_pdf, delete_file

router = APIRouter(prefix="/sujas", tags=["SUJAS Summaries"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, summary_id: int) -> SujasSummary:
    summary = db.query(SujasSummary).filter(SujasSummary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    return summary


# ── GET /sujas/{id}/pdf  (signed download redirect) ──────────────────────────

@router.get("/{summary_id}/pdf", summary="Download the attached PDF")
def download_pdf(summary_id: int, db: Session = Depends(get_db)):
    """
    Generates a signed Cloudinary URL and redirects the browser to it.
    The signed URL bypasses Strict Transformations and auth restrictions.
    """
    from fastapi.responses import RedirectResponse
    import cloudinary
    import cloudinary.utils

    summary = _get_or_404(db, summary_id)
    if not summary.pdf_file:
        raise HTTPException(status_code=404, detail="This summary has no PDF attached.")

    pdf_url = summary.pdf_file

    if "cloudinary.com" in pdf_url:
        # Extract public_id from stored URL.
        # For raw resources the extension IS part of the public_id —
        # do NOT strip it or Cloudinary returns 404.
        # URL: https://res.cloudinary.com/{cloud}/raw/upload/v{ver}/{public_id}
        url_path = pdf_url.split("?")[0]
        parts    = url_path.split("/upload/")
        if len(parts) == 2:
            after = parts[1]
            # Strip optional version segment  v1234567890/
            if after.startswith("v") and "/" in after:
                after = after.split("/", 1)[1]
            public_id = after   # keep full path including .pdf extension

            # Signed URL — bypasses Strict Transformations & access restrictions
            signed_url, _ = cloudinary.utils.cloudinary_url(
                public_id,
                resource_type="raw",
                sign_url=True,
            )
            return RedirectResponse(url=signed_url)

    # Fallback for legacy local file paths
    return RedirectResponse(url=pdf_url)


# ── GET /sujas ────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=PaginatedResponse[SujasSummaryResponse],
    summary="List summaries (optionally filtered by month or date)",
)
def list_summaries(
    month: Optional[str] = Query(
        None,
        description="Full month name, e.g. 'April'. Case-insensitive.",
        examples={"april": {"value": "April"}},
    ),
    summary_date: Optional[date] = Query(
        None,
        alias="date",
        description="Exact date filter in YYYY-MM-DD format.",
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_db),
):
    """
    Returns summaries sorted by date descending.

    **Filters (all optional, combinable):**
    - `month` — e.g. `?month=April`
    - `date`  — e.g. `?date=2025-04-01`
    """
    q = db.query(SujasSummary)

    if month:
        try:
            canonical_month = normalize_month(month)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        q = q.filter(SujasSummary.month == canonical_month)

    if summary_date:
        q = q.filter(SujasSummary.date == summary_date)

    total = q.count()
    offset = (page - 1) * page_size
    results = q.order_by(SujasSummary.date.desc()).offset(offset).limit(page_size).all()

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=results,
    )


# ── GET /sujas/{year}/{month}/{day}  (SEO-friendly, registered first) ─────────

@router.get(
    "/{year}/{month}/{day}",
    response_model=SujasSummaryResponse,
    summary="Get a summary by date  e.g. /sujas/2026/04/01",
)
def get_summary_by_date(
    year:  int = Path(..., ge=2000, le=2100, description="4-digit year"),
    month: int = Path(..., ge=1,    le=12,   description="Month 1–12"),
    day:   int = Path(..., ge=1,    le=31,   description="Day 1–31"),
    db: Session = Depends(get_db),
):
    """
    SEO-friendly canonical URL for a summary.

    Example: `GET /api/v1/sujas/2026/04/01`

    Returns the same payload as the ID-based route.
    Backward-compatible: `GET /api/v1/sujas/{id}` still works.
    """
    try:
        target = date_type(year, month, day)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{year}/{month:02d}/{day:02d} is not a valid date.",
        )

    summary = db.query(SujasSummary).filter(SujasSummary.date == target).first()
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No summary found for {target.isoformat()}.",
        )
    return summary


# ── GET /sujas/{id}  (backward-compatible, integer ID) ────────────────────────

@router.get(
    "/{summary_id}",
    response_model=SujasSummaryResponse,
    summary="Get a single summary by ID (legacy)",
)
def get_summary(summary_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, summary_id)


# ── POST /sujas ───────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=SujasSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new summary (admin only)",
)
async def create_summary(
    title: str = Form(..., description="Summary title"),
    content_html: str = Form(..., description="HTML body of the summary"),
    date: date = Form(..., description="Summary date in YYYY-MM-DD format"),
    pdf_file: Optional[UploadFile] = File(None, description="Optional PDF attachment"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    """
    Creates a summary. `month` is automatically derived from `date`
    (e.g., 2025-04-01 → "April"), so clients do not need to pass it.

    Requires Bearer token from `POST /api/v1/admin/login`.
    """
    if not title.strip():
        raise HTTPException(status_code=422, detail="title must not be empty")

    pdf_filename = await save_pdf(pdf_file) if pdf_file else None
    month = date.strftime("%B")  # "January" … "December"

    summary = SujasSummary(
        title=title.strip(),
        content_html=content_html,
        date=date,
        month=month,
        pdf_file=pdf_filename,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


# ── PUT /sujas/{id} ───────────────────────────────────────────────────────────

@router.put(
    "/{summary_id}",
    response_model=SujasSummaryResponse,
    summary="Replace a summary (admin only)",
)
async def update_summary(
    summary_id: int,
    title: Optional[str] = Form(None),
    content_html: Optional[str] = Form(None),
    date: Optional[date] = Form(None, description="YYYY-MM-DD"),
    replace_pdf: bool = Form(
        False,
        description="Set true to remove the existing PDF even if no new file is uploaded",
    ),
    pdf_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    """
    Partial-update semantics: only supplied fields are changed.
    To swap the PDF, upload a new `pdf_file`.
    To remove the PDF without replacement, pass `replace_pdf=true`.
    """
    summary = _get_or_404(db, summary_id)

    if title is not None:
        if not title.strip():
            raise HTTPException(status_code=422, detail="title must not be empty")
        summary.title = title.strip()

    if content_html is not None:
        summary.content_html = content_html

    if date is not None:
        summary.date = date
        summary.month = date.strftime("%B")

    if pdf_file:
        delete_file(summary.pdf_file)
        summary.pdf_file = await save_pdf(pdf_file)
    elif replace_pdf:
        delete_file(summary.pdf_file)
        summary.pdf_file = None

    db.commit()
    db.refresh(summary)
    return summary


# ── DELETE /sujas/{id} ────────────────────────────────────────────────────────

@router.delete(
    "/{summary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a summary (admin only)",
)
def delete_summary(
    summary_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    summary = _get_or_404(db, summary_id)
    delete_file(summary.pdf_file)
    db.delete(summary)
    db.commit()
