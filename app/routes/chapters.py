from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import EconomicsChapter, AdminUser
from app.schemas import (
    EconomicsChapterCreate,
    EconomicsChapterUpdate,
    EconomicsChapterResponse,
    PaginatedResponse,
)
from app.utils import get_current_admin

router = APIRouter(prefix="/economics", tags=["Economics Survey"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, chapter_id: int) -> EconomicsChapter:
    chapter = db.query(EconomicsChapter).filter(EconomicsChapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter with id={chapter_id} not found",
        )
    return chapter


# ── GET /economics ────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=PaginatedResponse[EconomicsChapterResponse],
    summary="List all economics chapters",
)
def list_chapters(
    search: Optional[str] = Query(None, description="Case-insensitive search on chapter_name"),
    status: Optional[str] = Query(
        None,
        description="'all' returns every chapter (admin use); default returns only live chapters",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns chapters ordered by `chapter_no` ascending.

    - Default: only live (published) chapters are returned.
    - `?status=all`: returns all chapters including drafts (used by admin panel).
    """
    q = db.query(EconomicsChapter)

    if status != 'all':
        q = q.filter(EconomicsChapter.is_live == True)  # noqa: E712

    if search:
        q = q.filter(EconomicsChapter.chapter_name.ilike(f"%{search}%"))

    total = q.count()
    offset = (page - 1) * page_size
    results = q.order_by(EconomicsChapter.chapter_no.asc()).offset(offset).limit(page_size).all()

    return PaginatedResponse(total=total, page=page, page_size=page_size, results=results)


# ── GET /economics/{id} ───────────────────────────────────────────────────────

@router.get(
    "/{chapter_id}",
    response_model=EconomicsChapterResponse,
    summary="Get a single chapter by ID",
)
def get_chapter(chapter_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, chapter_id)


# ── POST /economics ───────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=EconomicsChapterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new economics chapter (admin only)",
)
def create_chapter(
    payload: EconomicsChapterCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    """
    Accepts JSON body:
    ```json
    {
      "chapter_name": "Monetary Policy",
      "content_html": "<p>Content here...</p>"
    }
    ```
    Requires Bearer token.
    """
    if db.query(EconomicsChapter).filter(
        EconomicsChapter.chapter_name == payload.chapter_name
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A chapter named '{payload.chapter_name}' already exists",
        )

    chapter = EconomicsChapter(**payload.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


# ── PUT /economics/{id} ───────────────────────────────────────────────────────

@router.put(
    "/{chapter_id}",
    response_model=EconomicsChapterResponse,
    summary="Update a chapter (admin only)",
)
def update_chapter(
    chapter_id: int,
    payload: EconomicsChapterUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    """
    Partial-update semantics — only the fields present in the request body
    are modified. Omitted fields remain unchanged.

    ```json
    { "chapter_name": "Fiscal Policy (Revised)" }
    ```
    """
    chapter = _get_or_404(db, chapter_id)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body must contain at least one field to update",
        )

    # Guard against renaming to an already-existing chapter name
    new_name = updates.get("chapter_name")
    if new_name and new_name != chapter.chapter_name:
        conflict = db.query(EconomicsChapter).filter(
            EconomicsChapter.chapter_name == new_name
        ).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A chapter named '{new_name}' already exists",
            )

    for field, value in updates.items():
        setattr(chapter, field, value)

    db.commit()
    db.refresh(chapter)
    return chapter


# ── DELETE /economics/{id} ────────────────────────────────────────────────────

@router.delete(
    "/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chapter (admin only)",
)
def delete_chapter(
    chapter_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    chapter = _get_or_404(db, chapter_id)
    db.delete(chapter)
    db.commit()
