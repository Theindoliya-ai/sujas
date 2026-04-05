from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./sujas.db",   # local fallback only
)

# Render / some hosts supply postgres:// — SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite   = DATABASE_URL.startswith("sqlite")
_is_supabase = "supabase.co" in DATABASE_URL

# ── Engine kwargs ──────────────────────────────────────────────────────────
if _is_sqlite:
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
    }
else:
    # Append sslmode=require directly to URL for Supabase (more reliable
    # than passing via connect_args with psycopg2)
    if _is_supabase and "sslmode" not in DATABASE_URL:
        DATABASE_URL += "?sslmode=require"

    _engine_kwargs = {
        "connect_args":  {},
        "pool_pre_ping": True,
        "pool_recycle":  300,
        "pool_size":     5,
        "max_overflow":  10,
    }

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
