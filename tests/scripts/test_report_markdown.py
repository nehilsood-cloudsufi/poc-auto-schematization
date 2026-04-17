"""Tests for report_markdown.render_report."""
import pytest

from scripts.batch_lib.report_markdown import render_report


SAMPLE_RECORDS = [
    {
        "dataset": "ds1", "status": "passed",
        "complexity": {"raw_rows": 1000, "cleaned_rows": 990, "columns": 10, "file_size_mb": 0.5, "skeleton_bytes": 4000, "observation_rows": None},
        "accuracy": {"pv_accuracy": 30.0, "node_accuracy": 20.0, "node_coverage": 100.0,
                     "pvs_matched": 10, "pvs_modified": 5, "pvs_deleted": 5,
                     "nodes_matched": 2, "nodes_gt": 10, "nodes_generated": 10,
                     "delta_pv_vs_doc_gemini3pro": 5.0, "delta_node_vs_doc_gemini3pro": -2.0},
        "tokens_total": {"prompt": 1000, "thoughts": 100, "response": 200, "total": 1300},
        "tokens_by_agent": {"Generator": {"model": "gemini-3.1-pro-preview", "calls": 3, "total": 1300, "cost_usd": 0.02, "duration_ms": 5000, "prompt":1000,"thoughts":100,"response":200}},
        "cost_usd": {"total": 0.02, "by_agent": {"Generator": 0.02}, "pricing_version": "v1"},
        "timing_seconds": {"total": 60.0},
        "run_meta": {"attempt_count": 2, "git_sha": "abc", "schema_category": "Health", "sampling_strategy": "head"},
    },
    {
        "dataset": "ds2", "status": "timed_out",
        "complexity": {"raw_rows": 5000, "cleaned_rows": None, "columns": 20, "file_size_mb": 2.0, "skeleton_bytes": None, "observation_rows": None},
        "accuracy": {"pv_accuracy": None, "node_accuracy": None, "node_coverage": None,
                     "pvs_matched": None, "pvs_modified": None, "pvs_deleted": None,
                     "nodes_matched": None, "nodes_gt": None, "nodes_generated": None,
                     "delta_pv_vs_doc_gemini3pro": None, "delta_node_vs_doc_gemini3pro": None},
        "tokens_total": {"prompt": 0, "thoughts": 0, "response": 0, "total": 0},
        "tokens_by_agent": {},
        "cost_usd": {"total": 0.0, "by_agent": {}, "pricing_version": "v1"},
        "timing_seconds": {"total": 2700.0},
        "run_meta": {"attempt_count": None, "git_sha": "abc", "schema_category": None, "sampling_strategy": None},
    },
]


def test_render_report_smoke():
    md = render_report(
        records=SAMPLE_RECORDS,
        pricing_raw={"_source": "test"},
        run_meta={"git_sha": "abc1234", "generated_at": "2026-04-17T12:00:00", "cli_args": "--model=gemini-3.1-pro-preview"},
    )
    assert "# Batch Benchmark Report" in md
    assert "ds1" in md and "ds2" in md
    assert "Average PV accuracy" in md
    assert "| Agent |" in md  # per-agent aggregate table
    assert "30.0" in md       # pv_accuracy for ds1


def test_render_report_counts_failed():
    md = render_report(records=SAMPLE_RECORDS, pricing_raw={}, run_meta={})
    # timed_out counted
    assert "timed_out" in md.lower() or "timeout" in md.lower()


def test_render_report_handles_empty():
    md = render_report(records=[], pricing_raw={}, run_meta={})
    assert "# Batch Benchmark Report" in md
    assert "No datasets" in md or "0 datasets" in md
