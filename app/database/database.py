from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sujas.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite  = DATABASE_URL.startswith("sqlite")
_is_pooler  = ":6543" in DATABASE_URL

# ── Engine ────────────────────────────────────────────────────────────────────
if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

elif _is_pooler:
    # Supabase PgBouncer transaction mode (port 6543).
    # SQLAlchemy's URL parser mishandles the dotted username
    # (postgres.projref) — use a psycopg2 creator function instead
    # so credentials are passed as plain keyword args, bypassing URL encoding.
    import psycopg2
    from urllib.parse import urlparse, unquote

    _db_password = os.getenv("DB_PASSWORD")
    _p = urlparse(DATABASE_URL)
    _host     = _p.hostname
    _port     = _p.port or 6543
    _dbname   = (_p.path or "/postgres").lstrip("/")
    _user     = unquote(_p.username) if _p.username else "postgres"
    _password = _db_password if _db_password else unquote(_p.password or "")

    def _creator():
        return psycopg2.connect(
            host=_host,
            port=_port,
            dbname=_dbname,
            user=_user,
            password=_password,
            sslmode="require",
            connect_timeout=10,
        )

    engine = create_engine(
        "postgresql+psycopg2://",
        creator=_creator,
        poolclass=NullPool,
    )

else:
    # Standard PostgreSQL (non-pooler)
    _db_password = os.getenv("DB_PASSWORD")
    if _db_password:
        from sqlalchemy.engine import URL as _SA_URL
        from urllib.parse import urlparse, unquote
        _p = urlparse(DATABASE_URL)
        DATABASE_URL = str(_SA_URL.create(
            drivername="postgresql+psycopg2",
            username=unquote(_p.username or "postgres"),
            password=_db_password,
            host=_p.hostname,
            port=_p.port or 5432,
            database=(_p.path or "/postgres").lstrip("/"),
            query={"sslmode": "require"},
        ))
    elif "sslmode" not in DATABASE_URL:
        sep = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL += f"{sep}sslmode=require"

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
