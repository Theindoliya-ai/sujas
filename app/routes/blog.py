from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
import re

from app.database import get_db
from app.models import AdminUser
from app.models.models import BlogPost
from app.schemas.schemas import BlogPostCreate, BlogPostUpdate, BlogPostResponse, PaginatedResponse
from app.utils.auth import get_current_admin

router = APIRouter(prefix="/blog", tags=["Blog"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:200]


def _unique_slug(db: Session, base: str, exclude_id: int = None) -> str:
    slug = _slugify(base)
    candidate = slug
    i = 1
    while True:
        q = db.query(BlogPost).filter(BlogPost.slug == candidate)
        if exclude_id:
            q = q.filter(BlogPost.id != exclude_id)
        if not q.first():
            return candidate
        candidate = f"{slug}-{i}"
        i += 1


def _get_or_404(db: Session, post_id: int) -> BlogPost:
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return post


# ── GET /blog ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedResponse[BlogPostResponse])
def list_posts(
    page:      int  = Query(1, ge=1),
    page_size: int  = Query(12, ge=1, le=100),
    all:       bool = Query(False, description="Include unpublished (admin only)"),
    db: Session = Depends(get_db),
):
    q = db.query(BlogPost)
    if not all:
        q = q.filter(BlogPost.is_published == True)
    total   = q.count()
    results = q.order_by(BlogPost.created_at.desc()) \
               .offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(total=total, page=page, page_size=page_size, results=results)


# ── GET /blog/{slug} ──────────────────────────────────────────────────────────

@router.get("/{slug}", response_model=BlogPostResponse)
def get_post(slug: str, db: Session = Depends(get_db)):
    post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
    if not post or not post.is_published:
        # also allow ID-based lookup for admin preview
        try:
            post = _get_or_404(db, int(slug))
        except (ValueError, HTTPException):
            raise HTTPException(status_code=404, detail="Blog post not found")
    return post


# ── POST /blog ────────────────────────────────────────────────────────────────

@router.post("/", response_model=BlogPostResponse, status_code=201)
def create_post(
    payload: BlogPostCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    slug = _unique_slug(db, payload.title)
    post = BlogPost(
        title=payload.title,
        slug=slug,
        excerpt=payload.excerpt,
        content_html=payload.content_html,
        is_published=payload.is_published,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


# ── PUT /blog/{id} ────────────────────────────────────────────────────────────

@router.put("/{post_id}", response_model=BlogPostResponse)
def update_post(
    post_id: int,
    payload: BlogPostUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    post = _get_or_404(db, post_id)
    if payload.title is not None:
        post.title = payload.title.strip()
        post.slug  = _unique_slug(db, payload.title, exclude_id=post_id)
    if payload.excerpt      is not None: post.excerpt      = payload.excerpt
    if payload.content_html is not None: post.content_html = payload.content_html
    if payload.is_published is not None: post.is_published = payload.is_published
    db.commit()
    db.refresh(post)
    return post


# ── DELETE /blog/{id} ─────────────────────────────────────────────────────────

@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
):
    post = _get_or_404(db, post_id)
    db.delete(post)
    db.commit()
