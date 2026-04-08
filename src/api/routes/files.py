"""File serving, editing, and download endpoints."""
import io
import logging
import zipfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from src.api.services.run_state import get_or_load_run
from src.api.services.file_manager import get_output_files

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_output_dir(run_id: str, base_dir: Path) -> Path:
    """Get the output directory for a run, or raise 404."""
    run = get_or_load_run(run_id, base_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    return output_dir


@router.get("/runs/{run_id}/files")
async def list_files(run_id: str, request: Request):
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir)
    files = get_output_files(output_dir)
    return {"files": list(files.keys())}


@router.get("/runs/{run_id}/files/{filename}")
async def get_file(run_id: str, filename: str, request: Request):
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir)
    fpath = output_dir / filename

    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if filename.endswith(".csv"):
        try:
            import numpy as np
            # Handle empty or near-empty CSV files gracefully
            if fpath.stat().st_size <= 1:
                return {
                    "type": "csv",
                    "filename": filename,
                    "rows": [],
                    "columns": [],
                    "row_count": 0,
                }
            df = pd.read_csv(fpath)
            if df.empty:
                return {
                    "type": "csv",
                    "filename": filename,
                    "rows": [],
                    "columns": list(df.columns),
                    "row_count": 0,
                }
            df = df.replace([np.inf, -np.inf], "").fillna("")
            # Convert all values to strings to avoid JSON serialization issues
            # with mixed types, NaN remnants, or numpy scalars
            rows = [
                {col: str(v) if v != "" else "" for col, v in row.items()}
                for row in df.to_dict(orient="records")
            ]
            return {
                "type": "csv",
                "filename": filename,
                "rows": rows,
                "columns": list(df.columns),
                "row_count": len(df),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse CSV: {e}")
    else:
        try:
            content = fpath.read_text(encoding="utf-8")
            return {"type": "text", "filename": filename, "content": content}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")


@router.put("/runs/{run_id}/files/{filename}")
async def update_file(run_id: str, filename: str, body: dict, request: Request):
    """Save edited file. Body: {"rows": [...]} for CSV, {"content": "..."} for text."""
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir)
    fpath = output_dir / filename

    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "rows" in body and filename.endswith(".csv"):
        df = pd.DataFrame(body["rows"])
        df.to_csv(fpath, index=False)
    elif "content" in body:
        fpath.write_text(body["content"], encoding="utf-8")
    else:
        raise HTTPException(status_code=400, detail="Provide 'rows' for CSV or 'content' for text")

    return {"saved": True, "filename": filename}


@router.get("/runs/{run_id}/download")
async def download_zip(run_id: str, request: Request):
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in sorted(output_dir.rglob("*")):
            if fpath.is_file():
                arcname = fpath.relative_to(output_dir)
                zf.write(fpath, arcname)

    run = get_or_load_run(run_id, request.app.state.output_dir)
    zip_filename = f"{run.dataset_name}_outputs.zip" if run else f"{run_id}_outputs.zip"

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
