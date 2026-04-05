from .auth import router as auth_router
from .admin import router as admin_router
from .summaries import router as summaries_router
from .chapters import router as economics_router
from .blog import router as blog_router

__all__ = ["auth_router", "admin_router", "summaries_router", "economics_router", "blog_router"]
