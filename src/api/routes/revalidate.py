"""Revalidation endpoint — run stat_var_processor on edited PVMAP."""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from src.api.services.run_state import get_or_load_run
from src.api.services.revalidation_service import revalidate as revalidate_pvmap
from src.api.services.file_manager import get_output_files

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/runs/{run_id}/revalidate")
async def revalidate(run_id: str, request: Request):
    """Run stat_var_processor validation on the current PVMAP."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    output_dir = run_dir / "output" / run.dataset_name
    input_data = run_dir / "input" / "input.csv"
    pvmap_path = output_dir / "generated_pvmap.csv"

    if not input_data.exists():
        raise HTTPException(status_code=400, detail="Input data not found")
    if not pvmap_path.exists():
        raise HTTPException(status_code=400, detail="PVMAP not found")

    metadata_path = output_dir / "output_metadata.csv"

    result = revalidate_pvmap(
        input_data=input_data,
        pvmap_path=pvmap_path,
        metadata_path=metadata_path if metadata_path.exists() else None,
        output_dir=output_dir,
    )

    # Include list of output files that were regenerated
    output_files = list(get_output_files(output_dir).keys())
    result["output_files"] = output_files

    return result
