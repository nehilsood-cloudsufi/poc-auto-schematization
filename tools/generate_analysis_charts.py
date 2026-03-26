"""Generate analysis charts for PV accuracy benchmark study."""

import numpy as np
import pandas as pd

DOMAIN_PALETTE = {
    "Census/Demographics": "#2196F3",
    "Economics/Finance": "#4CAF50",
    "Health": "#F44336",
    "Education": "#FF9800",
    "Employment/Labor": "#9C27B0",
    "Environment": "#009688",
    "Crime/Safety": "#795548",
    "Brazil/LatAm": "#FFD600",
    "India": "#E91E63",
    "Other/Misc": "#607D8B",
}

SCHEMA_COVERAGE_TIERS = {
    "Census/Demographics": "Strong",
    "Employment/Labor": "Strong",
    "Environment": "Strong",
    "Other/Misc": "Strong",
    "Economics/Finance": "Moderate",
    "Health": "Moderate",
    "Education": "Weak",
    "Crime/Safety": "Weak",
    "Brazil/LatAm": "Weak",
    "India": "Weak",
}


def get_schema_coverage_tier(domain: str) -> str:
    """Return the schema coverage tier for a domain."""
    return SCHEMA_COVERAGE_TIERS.get(domain, "Weak")


def get_outlier_indices(
    x: list[float], y: list[float], n: int = 5
) -> set[int]:
    """Return indices of top-n and bottom-n outliers by residual from linear trend."""
    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)
    x_fit = np.log10(x_arr) if np.all(x_arr > 0) else x_arr
    valid = np.isfinite(x_fit) & np.isfinite(y_arr)
    if valid.sum() < 3:
        return set(range(len(x)))
    coeffs = np.polyfit(x_fit[valid], y_arr[valid], 1)
    predicted = np.polyval(coeffs, x_fit)
    residuals = y_arr - predicted
    sorted_idx = np.argsort(residuals)
    bottom_n = set(sorted_idx[:n].tolist())
    top_n = set(sorted_idx[-n:].tolist())
    return top_n | bottom_n


def make_short_alias(dataset_name: str) -> str:
    """Create a short alias for a dataset name for chart labels."""
    if len(dataset_name) <= 15:
        return dataset_name
    parts = dataset_name.split("_")
    if parts[0] == "brazil" and "visdata" in parts:
        rest = [p for p in parts if p not in ("brazil", "visdata")]
        # Split CamelCase tokens and collect uppercase letters
        initials = []
        for token in rest:
            if token and token[0].isupper():
                # CamelCase: take each uppercase letter
                initials.extend(c for c in token if c.isupper())
            elif token:
                initials.append(token[0].upper())
        return f"brazil_{''.join(initials)}"
    if parts[0] == "zurich":
        nums = [p for p in parts if p.isdigit()]
        return f"zurich_{nums[0]}" if nums else f"zurich_{'_'.join(parts[1:3])}"
    prefix = parts[0]
    rest_initials = "".join(p[0] for p in parts[1:] if p and p[0].isalpha() and p != prefix)
    if len(rest_initials) <= 1:
        return f"{prefix}_{'_'.join(parts[-2:])}" if len(parts) > 2 else dataset_name
    return f"{prefix}_{rest_initials}"


def build_alias_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build a reference table mapping short aliases to full dataset names."""
    rows = []
    for _, row in df.iterrows():
        alias = make_short_alias(row["dataset"])
        if alias != row["dataset"]:
            rows.append({
                "alias": alias,
                "full_name": row["dataset"],
                "domain": row["domain"],
                "pv_accuracy": row["pv_accuracy"],
            })
    return pd.DataFrame(rows)
