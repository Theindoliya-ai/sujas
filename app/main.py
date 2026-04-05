import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routes import auth_router, admin_router, summaries_router, economics_router, blog_router

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# Ensure uploads directory exists before StaticFiles tries to mount it
os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        import logging
        logging.getLogger("app").error("DB create_all failed: %s", exc)
    yield


app = FastAPI(
    title="SUJAS Summary API",
    description="Backend for SUJAS daily summaries.\n\nAuth: `POST /api/v1/login` | Summaries: `/api/v1/sujas` | Economics: `/api/v1/economics` | Admin: `/api/v1/admin`",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving (uploaded PDFs) ──────────────────────────────────────
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")       # /login  /register
app.include_router(admin_router, prefix="/api/v1")      # /admin/me  /admin/change-password
app.include_router(summaries_router, prefix="/api/v1")  # /sujas
app.include_router(economics_router, prefix="/api/v1")  # /economics
app.include_router(blog_router, prefix="/api/v1")       # /blog


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "SUJAS Summary API"}


# ── Entry point (python app/main.py or Render start command) ─────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False,
    )
