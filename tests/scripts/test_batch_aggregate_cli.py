"""Integration test for batch_aggregate end-to-end on the synthetic fixture."""
import json
import subprocess
import sys
from pathlib import Path


def test_batch_aggregate_produces_all_outputs(tmp_path: Path):
    fixture = Path(__file__).parent / "fixtures" / "synthetic_run"
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    import shutil
    shutil.copytree(fixture / "dsA", runs_dir / "dsA")

    pricing = Path(__file__).parent.parent.parent / "config" / "gemini_pricing.json"
    out_dir = tmp_path

    cmd = [
        sys.executable, "scripts/batch_aggregate.py",
        "--runs-dir", str(runs_dir),
        "--output-dir", str(out_dir),
        "--pricing-file", str(pricing),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).parent.parent.parent))
    assert r.returncode == 0, r.stderr

    # Required outputs
    assert (out_dir / "batch_results.json").exists()
    assert (out_dir / "batch_summary.csv").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "scatter_tokens_vs_rows.png").exists()
    assert (out_dir / "scatter_duration_vs_rows.png").exists()

    data = json.loads((out_dir / "batch_results.json").read_text())
    assert any(r["dataset"] == "dsA" for r in data)
