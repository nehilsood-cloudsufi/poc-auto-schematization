"""FastAPI application for PVMAP Generation Pipeline.

In development: run with `uvicorn src.api.main:app --reload --port 8000`
In production: FastAPI serves React static files from frontend/dist/
"""
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.config import UI_OUTPUT_DIR
from src.api.middleware.auth import IAPAuthMiddleware, UserEmailLogFilter

logger = logging.getLogger(__name__)


def create_app(output_dir: Optional[Path] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Auto Schematization Agent",
        description="PVMAP Generation Pipeline API",
        version="0.2.0",
    )

    app.state.output_dir = output_dir or UI_OUTPUT_DIR

    extra_origins = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            *extra_origins,
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(IAPAuthMiddleware)
    logging.getLogger().addFilter(UserEmailLogFilter())

    from src.api.routes.upload import router as upload_router
    app.include_router(upload_router, prefix="/api")

    from src.api.routes.runs import router as runs_router
    app.include_router(runs_router, prefix="/api")

    from src.api.routes.files import router as files_router
    app.include_router(files_router, prefix="/api")

    from src.api.routes.feedback import router as feedback_router
    app.include_router(feedback_router, prefix="/api")

    from src.api.routes.revalidate import router as revalidate_router
    app.include_router(revalidate_router, prefix="/api")

    from src.api.routes.plan import router as plan_router
    app.include_router(plan_router, prefix="/api")

    from src.api.ws.progress import router as ws_router
    app.include_router(ws_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.2.0"}

    # Serve React static files in production
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        from fastapi.responses import FileResponse

        # Serve static assets (JS, CSS, fonts, images) directly
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")))

        # Catch-all: serve index.html for any non-API route (React Router handles it)
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # Serve actual static files if they exist (favicon, etc.)
            file_path = frontend_dist / full_path
            # Guard against path traversal (e.g. "../../etc/passwd")
            resolved = file_path.resolve()
            if not str(resolved).startswith(str(frontend_dist.resolve())):
                return FileResponse(frontend_dist / "index.html")
            if full_path and resolved.is_file():
                return FileResponse(resolved)
            # Otherwise serve index.html for client-side routing
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
