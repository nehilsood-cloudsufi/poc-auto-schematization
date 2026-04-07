"""File upload endpoint."""
import io
import logging
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
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="CSV has no data rows")

    if not dataset_name:
        dataset_name = input_csv.filename.replace(".csv", "").replace(" ", "_")

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
