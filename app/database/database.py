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

_is_sqlite    = DATABASE_URL.startswith("sqlite")
_is_supabase  = "supabase.co" in DATABASE_URL

# ── Engine kwargs ──────────────────────────────────────────────────────────
if _is_sqlite:
    # SQLite: single-thread safety guard
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
    }
else:
    # PostgreSQL (Render, Supabase, etc.)
    _connect_args = {}
    if _is_supabase:
        # Supabase requires SSL; reject invalid certs in production
        _connect_args["sslmode"] = "require"

    _engine_kwargs = {
        "connect_args":  _connect_args,
        "pool_pre_ping": True,    # drop stale connections before reuse
        "pool_recycle":  300,     # recycle connections every 5 min
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
