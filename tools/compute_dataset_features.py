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


import pandas as pd


def _is_numeric_column(series: pd.Series, threshold: float = 0.8) -> bool:
    """Check if >threshold of non-null values in a column parse as numbers."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    numeric_count = pd.to_numeric(non_null, errors="coerce").notna().sum()
    return (numeric_count / len(non_null)) >= threshold


def extract_structural_features(csv_path: str) -> dict[str, float]:
    """Extract structural features from a CSV file.

    Returns dict with: column_count, row_count, numeric_column_count,
    categorical_column_count, numeric_to_categorical_ratio,
    max_column_cardinality, mean_column_cardinality.
    """
    df = pd.read_csv(csv_path, low_memory=False)

    numeric_cols = [c for c in df.columns if _is_numeric_column(df[c])]
    categorical_cols = [c for c in df.columns if c not in numeric_cols]

    cardinalities = [df[c].nunique() for c in df.columns]

    cat_count = len(categorical_cols)
    return {
        "column_count": len(df.columns),
        "row_count": len(df),
        "numeric_column_count": len(numeric_cols),
        "categorical_column_count": cat_count,
        "numeric_to_categorical_ratio": len(numeric_cols) / cat_count if cat_count > 0 else 0,
        "max_column_cardinality": max(cardinalities) if cardinalities else 0,
        "mean_column_cardinality": sum(cardinalities) / len(cardinalities) if cardinalities else 0,
    }
