from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL as _SA_URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from urllib.parse import urlparse
import os

# ── Raw URL ───────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sujas.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite  = DATABASE_URL.startswith("sqlite")
_is_pooler  = ":6543" in DATABASE_URL   # Supabase PgBouncer (IPv4, transaction mode)
_is_pg      = not _is_sqlite

# ── Rebuild URL with safely-encoded password ──────────────────────────────────
# DB_PASSWORD lets you store the raw password (with @, #, etc.) separately
# so the URL doesn't break during parsing.
_db_password = os.getenv("DB_PASSWORD")
if _db_password and _is_pg:
    _p = urlparse(DATABASE_URL)
    # For Supabase pooler the username in the URL may be URL-encoded
    # (e.g. postgres.projref becomes postgres.projref after unquoting)
    from urllib.parse import unquote
    _username = unquote(_p.username) if _p.username else "postgres"
    DATABASE_URL = str(_SA_URL.create(
        drivername="postgresql+psycopg2",
        username=_username,
        password=_db_password,          # SQLAlchemy encodes special chars here
        host=_p.hostname,
        port=_p.port or (6543 if _is_pooler else 5432),
        database=(_p.path or "/postgres").lstrip("/"),
        query={"sslmode": "require"},
    ))
elif _is_pg and "sslmode" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL += f"{sep}sslmode=require"

# ── Engine ────────────────────────────────────────────────────────────────────
if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
elif _is_pooler:
    # PgBouncer transaction mode — NullPool only, no special connect_args.
    # psycopg2 does not use server-side prepared statements by default,
    # so NullPool alone is sufficient for transaction mode compatibility.
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
