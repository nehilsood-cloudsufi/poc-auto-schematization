"""Tests for batch_benchmark arg parser."""
from scripts.batch_benchmark import build_parser


def test_parser_defaults():
    p = build_parser()
    ns = p.parse_args(["--datasets-file", "x.txt", "--output-dir", "/tmp/z"])
    assert ns.concurrency == 3
    assert ns.timeout == 2700
    assert ns.mcp_port_base == 3000


def test_parser_resume_failed():
    p = build_parser()
    ns = p.parse_args([
        "--datasets-file", "x.txt", "--output-dir", "/tmp/z",
        "--resume-failed", "/tmp/failed.json",
    ])
    assert ns.resume_failed == "/tmp/failed.json"
