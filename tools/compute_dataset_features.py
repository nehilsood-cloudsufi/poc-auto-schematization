"""Extract dataset structural features and correlate with PV accuracy."""

import re
from pathlib import Path


def parse_comparison_table(table_text: str, model_column: str) -> dict[str, float]:
    """Parse a markdown comparison table and extract values for one model column.

    Handles **bold** markers around values. Returns {dataset_name: float_value}.
    """
    lines = [l.strip() for l in table_text.strip().split("\n") if l.strip()]

    # Find header line (first line with |)
    header_line = None
    for i, line in enumerate(lines):
        if "|" in line and "---" not in line:
            header_line = i
            break

    if header_line is None:
        raise ValueError("No header row found in table")

    headers = [h.strip() for h in lines[header_line].split("|")]
    headers = [h for h in headers if h]  # Remove empty strings from leading/trailing |

    # Find the target column index
    col_idx = None
    for i, h in enumerate(headers):
        if h == model_column:
            col_idx = i
            break

    if col_idx is None:
        raise ValueError(f"Column '{model_column}' not found in headers: {headers}")

    result = {}
    for line in lines[header_line + 1:]:
        if "---" in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c != ""]
        if len(cells) <= col_idx:
            continue

        dataset = cells[0].strip()
        raw_value = cells[col_idx].strip()
        # Strip bold markers
        raw_value = raw_value.replace("**", "")
        try:
            result[dataset] = float(raw_value)
        except ValueError:
            continue

    return result


# Map section headers to metric keys
TABLE_SECTIONS = {
    "Node Accuracy": "node_accuracy",
    "Node Coverage": "node_coverage",
    "PV Accuracy": "pv_accuracy",
}


def extract_gemini3pro_metrics(comparison_md_path: str) -> dict[str, dict[str, float]]:
    """Parse the comparison markdown and extract Gemini 3 Pro metrics for all 3 tables.

    Returns {dataset_name: {pv_accuracy: float, node_accuracy: float, node_coverage: float}}
    Only includes datasets with at least one non-zero Gemini 3 Pro metric.
    """
    text = Path(comparison_md_path).read_text()

    # Split into sections by ## headers
    sections = re.split(r"^## ", text, flags=re.MULTILINE)

    # Collect per-dataset metrics
    all_metrics: dict[str, dict[str, float]] = {}

    for section in sections:
        metric_key = None
        for header_keyword, key in TABLE_SECTIONS.items():
            if section.startswith(header_keyword):
                metric_key = key
                break

        if metric_key is None:
            continue

        # Extract the table portion (lines starting with |)
        table_lines = [l for l in section.split("\n") if l.strip().startswith("|")]
        if not table_lines:
            continue

        table_text = "\n".join(table_lines)
        parsed = parse_comparison_table(table_text, model_column="Gemini 3 Pro %")

        for dataset, value in parsed.items():
            if dataset not in all_metrics:
                all_metrics[dataset] = {}
            all_metrics[dataset][metric_key] = value

    # Filter to datasets with at least one non-zero Gemini 3 Pro metric
    filtered = {}
    for dataset, metrics in all_metrics.items():
        if any(v > 0.0 for v in metrics.values()):
            filtered[dataset] = metrics

    return filtered
