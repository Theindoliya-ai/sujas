from __future__ import annotations

from datetime import date, datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, computed_field, field_validator, model_validator

# ── Month helpers ─────────────────────────────────────────────────────────────

VALID_MONTHS: list[str] = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_MONTH_LOOKUP: dict[str, str] = {m.lower(): m for m in VALID_MONTHS}


def normalize_month(value: str) -> str:
    normalized = _MONTH_LOOKUP.get(value.strip().lower())
    if not normalized:
        raise ValueError(
            f"Invalid month '{value}'. Must be one of: {', '.join(VALID_MONTHS)}"
        )
    return normalized


# ── SujasSummary ──────────────────────────────────────────────────────────────

class SujasSummaryBase(BaseModel):
    title: str
    content_html: str
    date: date

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v.strip()

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        """Accept ISO strings (YYYY-MM-DD) and date objects."""
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError:
                raise ValueError("date must be in YYYY-MM-DD format")
        return v


class SujasSummaryCreate(SujasSummaryBase):
    """month is auto-derived from date on the server; not required from client."""
    pass


class SujasSummaryUpdate(BaseModel):
    title: Optional[str] = None
    content_html: Optional[str] = None
    date: Optional[date] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("title must not be empty")
        return v.strip() if v else v

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError:
                raise ValueError("date must be in YYYY-MM-DD format")
        return v


class SujasSummaryResponse(SujasSummaryBase):
    id: int
    month: str
    pdf_file: Optional[str] = None
    created_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def slug(self) -> str:
        """SEO-friendly date path: YYYY/MM/DD — maps to GET /sujas/{year}/{month}/{day}."""
        return self.date.strftime("%Y/%m/%d")

    @computed_field  # type: ignore[misc]
    @property
    def pdf_url(self) -> Optional[str]:
        """
        Full URL ready for the frontend.
        - Cloudinary uploads: returned as-is (already absolute https://)
        - Legacy local files: served from /uploads/<filename>
        """
        if not self.pdf_file:
            return None
        if self.pdf_file.startswith("http"):
            return self.pdf_file  # Cloudinary secure_url — use directly
        filename = os.path.basename(self.pdf_file)
        return f"/uploads/{filename}"

    model_config = {"from_attributes": True}


# Need os for computed_field
import os  # noqa: E402 – placed here to keep class definition readable


# ── Paginated list wrapper ────────────────────────────────────────────────────

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    results: List[T]


# ── BlogPost ──────────────────────────────────────────────────────────────────

class BlogPostCreate(BaseModel):
    title:        str
    excerpt:      Optional[str] = None
    content_html: str
    is_published: bool = False

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v.strip()


class BlogPostUpdate(BaseModel):
    title:        Optional[str] = None
    excerpt:      Optional[str] = None
    content_html: Optional[str] = None
    is_published: Optional[bool] = None


class BlogPostResponse(BaseModel):
    id:           int
    title:        str
    slug:         str
    excerpt:      Optional[str] = None
    content_html: str
    is_published: bool
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}


# ── EconomicsChapter ──────────────────────────────────────────────────────────

class EconomicsChapterBase(BaseModel):
    chapter_no: int
    chapter_name: str
    chapter_name_hindi: Optional[str] = None
    topic: str
    content_html: str
    youtube_url: Optional[str] = None
    is_live: bool = False

    @field_validator("chapter_no")
    @classmethod
    def chapter_no_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("chapter_no must be a positive integer")
        return v

    @field_validator("chapter_name")
    @classmethod
    def chapter_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("chapter_name must not be empty")
        return v.strip()

    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("topic must not be empty")
        return v.strip()

    @field_validator("youtube_url")
    @classmethod
    def youtube_url_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip():
            return v.strip()
        return None


class EconomicsChapterCreate(EconomicsChapterBase):
    pass


class EconomicsChapterUpdate(BaseModel):
    chapter_no: Optional[int] = None
    chapter_name: Optional[str] = None
    chapter_name_hindi: Optional[str] = None
    topic: Optional[str] = None
    content_html: Optional[str] = None
    youtube_url: Optional[str] = None
    is_live: Optional[bool] = None

    @field_validator("chapter_no")
    @classmethod
    def chapter_no_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("chapter_no must be a positive integer")
        return v

    @field_validator("chapter_name")
    @classmethod
    def chapter_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("chapter_name must not be empty")
        return v.strip() if v else v

    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("topic must not be empty")
        return v.strip() if v else v

    @field_validator("youtube_url")
    @classmethod
    def youtube_url_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip():
            return v.strip()
        return None


class EconomicsChapterResponse(EconomicsChapterBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── AdminUser ─────────────────────────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("username must be at least 3 characters")
        if not v.isalnum():
            raise ValueError("username must contain only letters and digits")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("password must contain at least one digit")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("new_password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("new_password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("new_password must contain at least one digit")
        return v


class AdminUserResponse(BaseModel):
    id: int
    username: str

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
