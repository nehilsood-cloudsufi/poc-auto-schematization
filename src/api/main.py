"""FastAPI application for PVMAP Generation Pipeline.

In development: run with `uvicorn src.api.main:app --reload --port 8000`
In production: FastAPI serves React static files from frontend/dist/
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.config import UI_OUTPUT_DIR

logger = logging.getLogger(__name__)


def create_app(output_dir: Optional[Path] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Agent B: Auto Schematization",
        description="PVMAP Generation Pipeline API",
        version="1.0.0",
    )

    app.state.output_dir = output_dir or UI_OUTPUT_DIR

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    # Serve React static files in production
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True))

    return app


app = create_app()
