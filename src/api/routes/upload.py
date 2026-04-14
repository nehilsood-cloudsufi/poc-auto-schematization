"""File upload endpoint."""
import io
import json
import logging
import re
import uuid

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from src.api.services.file_manager import create_run_directory, save_uploaded_bytes
from src.api.services.run_state import create_run

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_files(
    request: Request,
    input_csv: UploadFile = File(...),
    metadata_csv: UploadFile | None = File(None),
    dataset_name: str | None = Form(None),
):
    """Upload CSV files and create a run directory."""
    output_dir = request.app.state.output_dir

    content = await input_csv.read()

    # Normalize to UTF-8 (handles BOM, Windows-1252, Latin-1)
    try:
        text = content.decode('utf-8-sig')  # strips BOM if present
    except UnicodeDecodeError:
        try:
            text = content.decode('latin-1')  # common fallback for European data
        except UnicodeDecodeError:
            text = content.decode('utf-8', errors='replace')
    content = text.encode('utf-8')

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="CSV has no data rows")

    if not dataset_name:
        raw_name = input_csv.filename or "untitled"
        dataset_name = raw_name.replace(".csv", "").replace(" ", "_")
        # Sanitize: keep only word chars and hyphens to prevent path traversal
        dataset_name = re.sub(r'[^\w\-]', '_', dataset_name)

    run_id = uuid.uuid4().hex[:12]
    run_dir = create_run_directory(run_id, base_dir=output_dir)

    input_path = save_uploaded_bytes(content, run_dir / "input", "input.csv")

    metadata_path = None
    if metadata_csv is not None:
        meta_content = await metadata_csv.read()
        metadata_path = save_uploaded_bytes(
            meta_content, run_dir / "input", "input_metadata.csv"
        )

    # Register run in state
    create_run(
        run_id=run_id,
        dataset_name=dataset_name,
        run_dir=str(run_dir),
        config={},
    )

    # Persist custom dataset name + owner for historical run discovery
    user_email = getattr(request.state, "user_email", "")
    run_info = {"dataset_name": dataset_name, "run_id": run_id, "owner": user_email}
    (run_dir / "run_info.json").write_text(json.dumps(run_info))

    # Log activity
    from src.api.services.activity_log import log_activity
    log_activity(output_dir, user_email, "upload", {"run_id": run_id, "dataset_name": dataset_name})

    return {
        "run_id": run_id,
        "dataset_name": dataset_name,
        "run_dir": str(run_dir),
        "input_path": str(input_path),
        "metadata_path": str(metadata_path) if metadata_path else None,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "preview": df.head(10).fillna("").to_dict(orient="records"),
    }
