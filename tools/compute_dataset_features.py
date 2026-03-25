"""Extract dataset structural features and correlate with PV accuracy."""

import re


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
