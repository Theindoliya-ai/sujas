from sqlalchemy import create_engine
from sqlalchemy.engine import URL as _SA_URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sujas.db")

# Render supplies postgres:// — SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite   = DATABASE_URL.startswith("sqlite")
_is_supabase = "supabase.co" in DATABASE_URL

# ── Rebuild URL safely if DB_PASSWORD is set separately ───────────────────
# This avoids URL-parsing failures when the password contains special
# characters such as '@', '/', '?', '#', etc.
_db_password = os.getenv("DB_PASSWORD")
if _db_password and not _is_sqlite:
    _p = urlparse(DATABASE_URL)
    DATABASE_URL = str(_SA_URL.create(
        drivername="postgresql+psycopg2",
        username=_p.username or "postgres",
        password=_db_password,
        host=_p.hostname,
        port=_p.port or 5432,
        database=(_p.path or "/postgres").lstrip("/"),
        query={"sslmode": "require"} if _is_supabase else {},
    ))

elif _is_supabase and "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

# ── Engine kwargs ──────────────────────────────────────────────────────────
if _is_sqlite:
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
    }
else:
    _engine_kwargs = {
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
