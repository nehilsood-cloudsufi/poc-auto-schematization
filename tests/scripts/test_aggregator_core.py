"""Tests for aggregator_core.build_dataset_record."""
from pathlib import Path

import pytest

from scripts.batch_lib.aggregator_core import build_dataset_record, compute_accuracy
from scripts.batch_lib.pricing import PricingTable


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_run"


@pytest.fixture
def pricing(tmp_path):
    import json
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps({
        "models": {
            "gemini-3.1-pro-preview": {"input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0, "is_estimate": True},
            "gemini-2.5-pro":         {"input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0, "is_estimate": False},
        },
        "fallback": {"input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0, "is_estimate": True},
    }))
    return PricingTable.load(p)


def test_compute_accuracy_basic():
    r = compute_accuracy(pvs_matched=12, pvs_modified=18, pvs_deleted=3, nodes_matched=2, nodes_gt=14, nodes_generated=16)
    # pv_accuracy = 12 / (12+18+3) * 100 = 36.36
    assert r["pv_accuracy"] == pytest.approx(36.36, rel=1e-2)
    # node_accuracy = min(2, 14) / 14 * 100 = 14.29
    assert r["node_accuracy"] == pytest.approx(14.29, rel=1e-2)
    # node_coverage = 16 / 14 * 100 = 114.29
    assert r["node_coverage"] == pytest.approx(114.29, rel=1e-2)


def test_compute_accuracy_handles_zero_denominator():
    r = compute_accuracy(pvs_matched=0, pvs_modified=0, pvs_deleted=0, nodes_matched=0, nodes_gt=0, nodes_generated=0)
    assert r["pv_accuracy"] == 0.0
    assert r["node_accuracy"] == 0.0
    assert r["node_coverage"] == 0.0


def test_build_dataset_record_from_fixture(pricing):
    rec = build_dataset_record(
        dataset="dsA",
        run_dir=FIXTURE / "dsA",
        input_csv=None,
        pricing=pricing,
        baseline_pv=None, baseline_node=None,
        status="passed",
    )

    assert rec["dataset"] == "dsA"
    assert rec["status"] == "passed"
    assert rec["accuracy"]["pv_accuracy"] == pytest.approx(36.36, rel=1e-2)
    assert rec["accuracy"]["pvs_matched"] == 12

    # Totals across 4 calls: 1500 + 3000 + 6800 + 3900 = 15200
    assert rec["tokens_total"]["total"] == 15200
    assert set(rec["tokens_by_agent"].keys()) == {"SamplingAgent", "SchemaSelectionAgent", "Generator", "FeedbackAgent"}
    assert rec["tokens_by_agent"]["SchemaSelectionAgent"]["model"] == "gemini-2.5-pro"
    assert rec["cost_usd"]["total"] > 0
    assert rec["timing_seconds"]["validation"] == 240.0


def test_build_dataset_record_missing_eval_marks_passed_with_warnings(tmp_path, pricing):
    """If diff_results.json is absent AND generated_pvmap.csv exists, status becomes passed_with_warnings."""
    run_dir = tmp_path / "dsX"
    run_dir.mkdir()
    (run_dir / "llm_calls.jsonl").write_text("")
    (run_dir / "generated_pvmap.csv").write_text("Node\ndcid:x\n")
    rec = build_dataset_record(
        dataset="dsX", run_dir=run_dir, input_csv=None, pricing=pricing,
        baseline_pv=None, baseline_node=None, status="passed",
    )
    assert rec["accuracy"]["pv_accuracy"] is None
    assert rec["status"] == "passed_with_warnings"


def test_build_dataset_record_applies_baseline_delta(pricing):
    rec = build_dataset_record(
        dataset="dsA", run_dir=FIXTURE / "dsA", input_csv=None, pricing=pricing,
        baseline_pv=36.4, baseline_node=14.3, status="passed",
    )
    assert rec["accuracy"]["delta_pv_vs_doc_gemini3pro"] == pytest.approx(
        rec["accuracy"]["pv_accuracy"] - 36.4, abs=0.01
    )
    assert rec["accuracy"]["delta_node_vs_doc_gemini3pro"] == pytest.approx(
        rec["accuracy"]["node_accuracy"] - 14.3, abs=0.01
    )


def test_build_dataset_record_crashed_status(tmp_path, pricing):
    """Crashed dataset: no artifacts, record still builds with nulls."""
    run_dir = tmp_path / "dsY"
    run_dir.mkdir()
    rec = build_dataset_record(
        dataset="dsY", run_dir=run_dir, input_csv=None, pricing=pricing,
        baseline_pv=None, baseline_node=None, status="crashed",
    )
    assert rec["status"] == "crashed"
    assert rec["tokens_total"]["total"] == 0
    assert rec["accuracy"]["pv_accuracy"] is None
