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


import glob

DOMAIN_TAXONOMY = {
    # Economics/Finance
    "bis_bis_central_bank_policy_rate": "Economics/Finance",
    "fao_currency_and_exchange_rate": "Economics/Finance",
    "world_bank_commodity_market": "Economics/Finance",
    "us_bls_cpi_category": "Economics/Finance",
    "us_bls_us_cpi": "Economics/Finance",
    "us_federal_reserve_h15_interest_rates": "Economics/Finance",
    "commerce_eda": "Economics/Finance",
    "us_census_us_monthly_retail_sales": "Economics/Finance",
    "india_rbistatedomesticproduct": "Economics/Finance",
    "database_on_indian_economy_india_rbi_state_statistics": "Economics/Finance",
    # Census/Demographics
    "census_v2_sahie": "Census/Demographics",
    "census_v2_saipe": "Census/Demographics",
    "us_census": "Census/Demographics",
    "opendataforafrica_ethiopia_statistics": "Census/Demographics",
    "opendataforafrica_kenya_census": "Census/Demographics",
    "opendataforafrica_rwanda_census": "Census/Demographics",
    "finland_census": "Census/Demographics",
    "ireland_census": "Census/Demographics",
    "statistics_new_zealand_new_zealand_census": "Census/Demographics",
    "mexico_subnational_population_statistics_mexico_census_aa2": "Census/Demographics",
    "child_birth": "Census/Demographics",
    "zurich_bev_3240_wiki": "Census/Demographics",
    "zurich_bev_3903_age10_wiki": "Census/Demographics",
    "zurich_bev_3903_hel_wiki": "Census/Demographics",
    "zurich_bev_3903_sex_wiki": "Census/Demographics",
    "zurich_bev_4031_hel_wiki": "Census/Demographics",
    "zurich_bev_4031_sex_wiki": "Census/Demographics",
    "zurich_bev_4031_wiki": "Census/Demographics",
    # Health
    "brfss_nchs_asthma_prevalence": "Health",
    "cdc_social_vulnerability_index": "Health",
    "india_ndap_india_nss_health_ailments": "Health",
    "nyu_diabetes_texas": "Health",
    "us_cdc_single_race": "Health",
    "southkorea_statistics_health": "Health",
    "india_nfhs": "Health",
    # Education
    "ccd_enrollment": "Education",
    "school_retention": "Education",
    "school_algebra1": "Education",
    "school_finance": "Education",
    "us_urban_school_teachers": "Education",
    "ncses_median_annual_salary": "Education",
    "ncses_ncses_demographics_seh_import": "Education",
    "ncses_research_doctorate_recipients": "Education",
    "ipeds": "Education",
    "us_bachelors_degree_data": "Education",
    "us_steam_degrees_data": "Education",
    "doctoratedegreeemployment": "Education",
    "southkorea_statistics_education": "Education",
    # Employment/Labor
    "usa_dol": "Employment/Labor",
    "usa_dol_minimum_wage": "Employment/Labor",
    "southkorea_statistics_employment": "Employment/Labor",
    "us_bls_bls_ces": "Employment/Labor",
    "us_bls_bls_ces_state": "Employment/Labor",
    "ntia_internet_use_survey": "Employment/Labor",
    # Environment
    "inpe_fire": "Environment",
    "oecd_wastewater_treatment": "Environment",
    # Crime/Safety
    "fbi_fbigovcrime": "Crime/Safety",
    "crdc_import_crdc_harassment_or_bullying": "Crime/Safety",
    "crdc_instructional_wifi_devices": "Crime/Safety",
    "us_crash_fars_crashdata": "Crime/Safety",
    # Brazil
    "brazil_sidra_ibge": "Brazil/LatAm",
    "brazil_visdata_FoodBasketDistribution": "Brazil/LatAm",
    "brazil_visdata_brazil_rural_development_program": "Brazil/LatAm",
    # India
    "india_ndap": "India",
    # Other
    "undata": "Other/Misc",
    "uae_bayanat": "Other/Misc",
    "google_sustainability_financial_incentives": "Other/Misc",
    "zurich_wir_2552_wiki": "Other/Misc",
    "oecd_regional_education": "Education",
}


def get_domain(dataset_name: str) -> str:
    """Return the domain category for a dataset. Falls back to Other/Misc."""
    return DOMAIN_TAXONOMY.get(dataset_name, "Other/Misc")


def find_input_csv(dataset_name: str, input_base_dir: str) -> str | None:
    """Find the input CSV for a dataset. Returns path or None if not found.

    Looks for input/{dataset}/test_data/*_input.csv, takes the first match.
    """
    pattern = f"{input_base_dir}/{dataset_name}/test_data/*_input.csv"
    matches = sorted(glob.glob(pattern))
    if matches:
        return matches[0]

    # Fallback: any CSV in test_data
    pattern = f"{input_base_dir}/{dataset_name}/test_data/*.csv"
    matches = sorted(glob.glob(pattern))
    return matches[0] if matches else None


import math

STRUCTURAL_FACTORS = [
    "column_count",
    "row_count",
    "numeric_column_count",
    "categorical_column_count",
    "numeric_to_categorical_ratio",
    "max_column_cardinality",
    "mean_column_cardinality",
]


def _spearman_r(x: list[float], y: list[float]) -> tuple[float, float]:
    """Compute Spearman rank correlation and approximate p-value.

    No scipy needed -- ranks the values and computes Pearson on ranks.
    P-value uses t-distribution approximation.
    """
    n = len(x)
    if n < 3:
        return 0.0, 1.0

    def _rank(vals):
        indexed = sorted(enumerate(vals), key=lambda t: t[1])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1  # 1-based average rank for ties
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx, ry = _rank(x), _rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))

    if dx == 0 or dy == 0:
        return 0.0, 1.0

    r = num / (dx * dy)
    # t-distribution approximation for p-value
    if abs(r) >= 1.0:
        p = 0.0
    else:
        t_stat = r * math.sqrt((n - 2) / (1 - r * r))
        # Approximate two-tailed p-value using normal for large-ish n
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))

    return r, p


def compute_correlations(
    features_df: pd.DataFrame,
    target: str = "pv_accuracy",
    factors: list[str] | None = None,
) -> pd.DataFrame:
    """Compute Spearman rank correlations between each factor and the target metric.

    Returns DataFrame with columns: factor, spearman_r, p_value, n.
    Sorted by absolute correlation strength (descending).
    Only includes rows where both factor and target are non-null.
    """
    if factors is None:
        factors = STRUCTURAL_FACTORS

    rows = []
    for factor in factors:
        if factor not in features_df.columns:
            continue
        valid = features_df[[target, factor]].dropna()
        if len(valid) < 5:  # Need at least 5 data points
            continue
        r, p = _spearman_r(valid[target].tolist(), valid[factor].tolist())
        rows.append({
            "factor": factor,
            "spearman_r": round(r, 3),
            "p_value": round(p, 4),
            "n": len(valid),
        })

    result = pd.DataFrame(rows)
    if len(result) > 0:
        result = result.sort_values("spearman_r", key=abs, ascending=False).reset_index(drop=True)
    return result
