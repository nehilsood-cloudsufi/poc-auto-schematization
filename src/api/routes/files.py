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
from src.api.middleware.auth import require_run_access

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_output_dir(run_id: str, base_dir: Path, request: Request) -> Path:
    """Get the output directory for a run, or raise 404/403."""
    run = get_or_load_run(run_id, base_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    require_run_access(Path(run.run_dir), request)
    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    return output_dir


@router.get("/runs/{run_id}/files")
async def list_files(run_id: str, request: Request):
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir, request)
    files = get_output_files(output_dir)
    return {"files": list(files.keys())}


@router.get("/runs/{run_id}/files/{filename}")
async def get_file(run_id: str, filename: str, request: Request):
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir, request)
    fpath = (output_dir / filename).resolve()

    # Prevent path traversal (e.g., ../../etc/passwd)
    if not str(fpath).startswith(str(output_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")

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
            # Fallback: serve CSV as raw text if JSON serialization fails
            logger.warning("CSV JSON serialization failed for %s: %s — falling back to text", filename, e)
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                return {"type": "text", "filename": filename, "content": content}
            except Exception:
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
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir, request)
    fpath = (output_dir / filename).resolve()

    # Prevent path traversal
    if not str(fpath).startswith(str(output_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "rows" in body and filename.endswith(".csv"):
        rows = body["rows"]
        if not isinstance(rows, list):
            raise HTTPException(status_code=400, detail="'rows' must be a non-null list")
        df = pd.DataFrame(rows)
        df.to_csv(fpath, index=False)
    elif "content" in body:
        fpath.write_text(body["content"], encoding="utf-8")
    else:
        raise HTTPException(status_code=400, detail="Provide 'rows' for CSV or 'content' for text")

    # RLHF logging
    user_email = getattr(request.state, "user_email", "")
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run:
        from src.api.services.rlhf_log import log_interaction
        log_interaction(Path(run.run_dir), user_email, "pvmap_cells_edited", {
            "filename": filename,
            "changed_rows": len(body.get("rows", [])) if "rows" in body else 0,
        })

    return {"saved": True, "filename": filename}


@router.get("/runs/{run_id}/sdmx-metadata")
async def get_sdmx_metadata(run_id: str, request: Request):
    """Return the pre-extracted SDMX metadata JSON for a run, or 404 if not an SDMX run."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    require_run_access(Path(run.run_dir), request)

    sdmx_input_dir = Path(run.run_dir) / "sdmx_input"
    # Prefer the enriched version if the enrichment pipeline has already run.
    enriched_path = sdmx_input_dir / "sdmx_metadata_enriched.json"
    base_path = sdmx_input_dir / "sdmx_metadata.json"
    sdmx_json_path = enriched_path if enriched_path.exists() else base_path
    if not sdmx_json_path.exists():
        raise HTTPException(status_code=404, detail="No SDMX metadata for this run")

    try:
        import json as _json
        data = _json.loads(sdmx_json_path.read_text())
        # Surface whether the caller is seeing enriched data so the UI can badge it.
        return {"data": data, "enriched": enriched_path.exists()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read SDMX metadata: {e}")


@router.get("/runs/{run_id}/download")
async def download_zip(run_id: str, request: Request):
    output_dir = _resolve_output_dir(run_id, request.app.state.output_dir, request)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    import re as _re
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in sorted(output_dir.rglob("*")):
            if not fpath.is_file():
                continue
            # Skip versioned snapshot directories (v1/, v2/, ...) and feedback dirs
            rel = fpath.relative_to(output_dir)
            parts = rel.parts
            if parts and _re.match(r'^v\d+$', parts[0]):
                continue
            if parts and parts[0] == "feedback":
                continue
            zf.write(fpath, rel)

    run = get_or_load_run(run_id, request.app.state.output_dir)
    zip_filename = f"{run.dataset_name}_outputs.zip" if run else f"{run_id}_outputs.zip"

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
