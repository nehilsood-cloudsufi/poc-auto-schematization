"""Generate analysis charts for PV accuracy benchmark study."""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from adjustText import adjust_text

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


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

CHART_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "analysis", "factor_analysis", "charts",
)
CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "analysis", "factor_analysis", "dataset_features_and_accuracy.csv",
)
CORR_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "analysis", "factor_analysis", "correlation_summary.csv",
)
FIGSIZE = (10, 6)
DPI = 300


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _setup_style() -> None:
    """Apply common chart style."""
    sns.set_style("whitegrid")
    plt.rcParams.update({
        "font.family": ["Arial", "Helvetica", "sans-serif"],
        "font.size": 10,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "axes.grid": True,
        "grid.alpha": 0.3,
    })


def _add_trend_line(ax, x, y, spearman_r: float, p_value: float) -> None:
    """Add a dashed gray OLS trend line and Spearman annotation to ax."""
    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)
    valid = np.isfinite(x_arr) & np.isfinite(y_arr) & (x_arr > 0)
    x_fit = np.log10(x_arr[valid]) if ax.get_xscale() == "log" else x_arr[valid]
    coeffs = np.polyfit(x_fit, y_arr[valid], 1)
    x_line_fit = np.linspace(x_fit.min(), x_fit.max(), 100)
    x_line_plot = 10 ** x_line_fit if ax.get_xscale() == "log" else x_line_fit
    ax.plot(
        x_line_plot,
        np.polyval(coeffs, x_line_fit),
        "--",
        color="gray",
        alpha=0.7,
        linewidth=1.5,
    )
    ax.annotate(
        f"Spearman r = {spearman_r:.3f}\np = {p_value:.3f}",
        xy=(0.95, 0.05),
        xycoords="axes fraction",
        ha="right",
        va="bottom",
        fontsize=9,
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="white",
            edgecolor="gray",
            alpha=0.8,
        ),
    )


def _label_outliers(ax, df: pd.DataFrame, x_col: str, y_col: str, n: int = 5) -> None:
    """Label top/bottom n outliers by residual using short aliases."""
    x_vals = df[x_col].tolist()
    y_vals = df[y_col].tolist()
    outlier_idx = get_outlier_indices(x_vals, y_vals, n=n)
    texts = []
    for i in outlier_idx:
        row = df.iloc[i]
        label = make_short_alias(row["dataset"])
        texts.append(
            ax.text(
                row[x_col],
                row[y_col],
                label,
                fontsize=7,
                ha="center",
            )
        )
    if texts:
        adjust_text(
            texts,
            ax=ax,
            arrowprops=dict(arrowstyle="-", color="gray", lw=0.5),
        )


# ---------------------------------------------------------------------------
# Chart functions
# ---------------------------------------------------------------------------

def chart_h1_column_count(df: pd.DataFrame) -> str:
    """H1: column_count (log x) vs pv_accuracy scatter, colored by domain."""
    _setup_style()
    fig, ax = plt.subplots(figsize=FIGSIZE)

    for domain, grp in df.groupby("domain"):
        color = DOMAIN_PALETTE.get(domain, "#607D8B")
        ax.scatter(
            grp["column_count"],
            grp["pv_accuracy"],
            label=domain,
            color=color,
            alpha=0.8,
            s=60,
            edgecolors="white",
            linewidths=0.5,
        )

    ax.set_xscale("log")
    _add_trend_line(ax, df["column_count"], df["pv_accuracy"], spearman_r=-0.099, p_value=0.499)
    _label_outliers(ax, df, "column_count", "pv_accuracy")

    ax.set_xlabel("Column Count (log scale)")
    ax.set_ylabel("PV Accuracy (%)")
    ax.set_title("H1: Column Count vs PV Accuracy")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.7)
    plt.tight_layout()

    os.makedirs(CHART_DIR, exist_ok=True)
    out_path = os.path.join(CHART_DIR, "h1_column_count.png")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def chart_h2_numeric_ratio(df: pd.DataFrame) -> str:
    """H2: numeric_to_categorical_ratio vs pv_accuracy scatter."""
    _setup_style()
    fig, ax = plt.subplots(figsize=FIGSIZE)

    zero_mask = df["numeric_to_categorical_ratio"] == 0
    nonzero = df[~zero_mask]
    zeros = df[zero_mask]

    for domain, grp in nonzero.groupby("domain"):
        color = DOMAIN_PALETTE.get(domain, "#607D8B")
        ax.scatter(
            grp["numeric_to_categorical_ratio"],
            grp["pv_accuracy"],
            label=domain,
            color=color,
            alpha=0.8,
            s=60,
            edgecolors="white",
            linewidths=0.5,
        )

    if not zeros.empty:
        for domain, grp in zeros.groupby("domain"):
            color = DOMAIN_PALETTE.get(domain, "#607D8B")
            ax.scatter(
                grp["numeric_to_categorical_ratio"],
                grp["pv_accuracy"],
                marker="^",
                color=color,
                alpha=0.8,
                s=70,
                edgecolors="white",
                linewidths=0.5,
            )
        ax.annotate(
            "triangles = all-categorical (ratio = 0)",
            xy=(0.02, 0.95),
            xycoords="axes fraction",
            ha="left",
            va="top",
            fontsize=8,
            style="italic",
        )

    _add_trend_line(
        ax,
        df["numeric_to_categorical_ratio"],
        df["pv_accuracy"],
        spearman_r=0.202,
        p_value=0.161,
    )
    _label_outliers(ax, df, "numeric_to_categorical_ratio", "pv_accuracy")

    ax.set_xlabel("Numeric-to-Categorical Ratio")
    ax.set_ylabel("PV Accuracy (%)")
    ax.set_title("H2: Numeric-to-Categorical Ratio vs PV Accuracy")

    # Deduplicate legend entries
    handles, labels = ax.get_legend_handles_labels()
    seen: dict = {}
    for h, l in zip(handles, labels):
        if l not in seen:
            seen[l] = h
    ax.legend(seen.values(), seen.keys(), loc="upper right", fontsize=8, framealpha=0.7)
    plt.tight_layout()

    os.makedirs(CHART_DIR, exist_ok=True)
    out_path = os.path.join(CHART_DIR, "h2_numeric_ratio.png")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def chart_h3_domain_boxplot(df: pd.DataFrame) -> str:
    """H3: horizontal box plot of pv_accuracy by domain, sorted by median."""
    _setup_style()

    domain_medians = df.groupby("domain")["pv_accuracy"].median().sort_values(ascending=False)
    domain_order = domain_medians.index.tolist()

    # Build labels with N counts
    n_counts = df.groupby("domain")["pv_accuracy"].count()
    y_labels = [f"{d} (n={n_counts[d]})" for d in domain_order]

    fig, ax = plt.subplots(figsize=(10, 7))

    data_by_domain = [df[df["domain"] == d]["pv_accuracy"].tolist() for d in domain_order]
    bp = ax.boxplot(
        data_by_domain,
        vert=False,
        patch_artist=True,
        tick_labels=y_labels,
    )

    for patch, domain in zip(bp["boxes"], domain_order):
        patch.set_facecolor(DOMAIN_PALETTE.get(domain, "#607D8B"))
        patch.set_alpha(0.6)

    # Strip plot overlay
    for i, domain in enumerate(domain_order, start=1):
        grp = df[df["domain"] == domain]
        jitter = np.random.default_rng(42).uniform(-0.2, 0.2, size=len(grp))
        ax.scatter(
            grp["pv_accuracy"],
            np.full(len(grp), i) + jitter,
            color=DOMAIN_PALETTE.get(domain, "#607D8B"),
            alpha=0.7,
            s=30,
            zorder=3,
        )

    ax.set_xlabel("PV Accuracy (%)")
    ax.set_title("H3: PV Accuracy by Domain")
    plt.tight_layout()

    os.makedirs(CHART_DIR, exist_ok=True)
    out_path = os.path.join(CHART_DIR, "h3_domain_boxplot.png")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def chart_h4_row_count(df: pd.DataFrame) -> str:
    """H4: row_count (log x) vs pv_accuracy scatter, colored by domain."""
    _setup_style()
    fig, ax = plt.subplots(figsize=FIGSIZE)

    for domain, grp in df.groupby("domain"):
        color = DOMAIN_PALETTE.get(domain, "#607D8B")
        ax.scatter(
            grp["row_count"],
            grp["pv_accuracy"],
            label=domain,
            color=color,
            alpha=0.8,
            s=60,
            edgecolors="white",
            linewidths=0.5,
        )

    ax.set_xscale("log")
    _add_trend_line(ax, df["row_count"], df["pv_accuracy"], spearman_r=-0.051, p_value=0.729)
    _label_outliers(ax, df, "row_count", "pv_accuracy")

    ax.set_xlabel("Row Count (log scale)")
    ax.set_ylabel("PV Accuracy (%)")
    ax.set_title("H4: Row Count vs PV Accuracy")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.7)
    plt.tight_layout()

    os.makedirs(CHART_DIR, exist_ok=True)
    out_path = os.path.join(CHART_DIR, "h4_row_count.png")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def chart_h5_schema_coverage(df: pd.DataFrame) -> str:
    """H5: grouped bar chart — domains grouped by Strong/Moderate/Weak tier."""
    _setup_style()

    df = df.copy()
    df["tier"] = df["domain"].map(get_schema_coverage_tier)

    tier_order = ["Strong", "Moderate", "Weak"]
    tier_colors = {"Strong": "#4CAF50", "Moderate": "#FF9800", "Weak": "#F44336"}

    # Mean accuracy per domain
    domain_means = df.groupby(["tier", "domain"])["pv_accuracy"].mean().reset_index()

    fig, ax = plt.subplots(figsize=FIGSIZE)

    x_positions = []
    x_labels = []
    current_x = 0
    gap = 0.8  # gap between tier groups
    bar_width = 0.6

    tier_x_ranges: dict = {}
    for tier in tier_order:
        tier_data = domain_means[domain_means["tier"] == tier].sort_values("pv_accuracy", ascending=False)
        if tier_data.empty:
            continue
        tier_start = current_x
        for _, row in tier_data.iterrows():
            bar = ax.bar(
                current_x,
                row["pv_accuracy"],
                width=bar_width,
                color=DOMAIN_PALETTE.get(row["domain"], "#607D8B"),
                alpha=0.85,
                edgecolor="white",
            )
            # Value label on bar
            ax.text(
                current_x,
                row["pv_accuracy"] + 0.5,
                f"{row['pv_accuracy']:.1f}%",
                ha="center",
                va="bottom",
                fontsize=7,
            )
            x_positions.append(current_x)
            x_labels.append(row["domain"].split("/")[0])
            current_x += 1
        tier_end = current_x - 1
        tier_x_ranges[tier] = (tier_start, tier_end)
        current_x += gap

    # Tier average lines
    for tier, (x_start, x_end) in tier_x_ranges.items():
        tier_avg = domain_means[domain_means["tier"] == tier]["pv_accuracy"].mean()
        ax.hlines(
            tier_avg,
            x_start - bar_width / 2,
            x_end + bar_width / 2,
            colors=tier_colors[tier],
            linestyles="--",
            linewidth=1.5,
            label=f"{tier} avg = {tier_avg:.1f}%",
        )

    # Gap annotation between Strong and Moderate tiers
    if "Strong" in tier_x_ranges and "Moderate" in tier_x_ranges:
        strong_avg = domain_means[domain_means["tier"] == "Strong"]["pv_accuracy"].mean()
        moderate_avg = domain_means[domain_means["tier"] == "Moderate"]["pv_accuracy"].mean()
        gap_val = strong_avg - moderate_avg
        if gap_val != 0:
            strong_end_x = tier_x_ranges["Strong"][1]
            moderate_start_x = tier_x_ranges["Moderate"][0]
            mid_x = (strong_end_x + moderate_start_x) / 2
            mid_y = (strong_avg + moderate_avg) / 2
            ax.annotate(
                f"Δ {gap_val:.1f}pp",
                xy=(mid_x, mid_y),
                fontsize=8,
                ha="center",
                color="black",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="lightyellow", edgecolor="gray", alpha=0.8),
            )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Mean PV Accuracy (%)")
    ax.set_title("H5: PV Accuracy by Schema Coverage Tier")

    # Legend: tier patches + avg lines
    tier_patches = [
        mpatches.Patch(facecolor=tier_colors[t], label=t) for t in tier_order if t in tier_x_ranges
    ]
    line_handles, line_labels = ax.get_legend_handles_labels()
    ax.legend(
        handles=tier_patches + line_handles,
        labels=[t for t in tier_order if t in tier_x_ranges] + line_labels,
        loc="upper right",
        fontsize=8,
        framealpha=0.7,
    )
    plt.tight_layout()

    os.makedirs(CHART_DIR, exist_ok=True)
    out_path = os.path.join(CHART_DIR, "h5_schema_coverage.png")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def chart_correlation_summary() -> str:
    """Horizontal bar chart of Spearman |r| per factor from correlation_summary.csv."""
    _setup_style()

    corr_df = pd.read_csv(CORR_CSV_PATH)
    corr_df = corr_df.sort_values("spearman_r", ascending=True)

    colors = ["#2196F3" if r >= 0 else "#F44336" for r in corr_df["spearman_r"]]

    fig, ax = plt.subplots(figsize=FIGSIZE)
    bars = ax.barh(
        corr_df["factor"],
        corr_df["spearman_r"].abs(),
        color=colors,
        edgecolor="white",
        alpha=0.85,
    )

    # p-value annotations
    for bar, (_, row) in zip(bars, corr_df.iterrows()):
        sign = "+" if row["spearman_r"] >= 0 else "-"
        ax.text(
            bar.get_width() + 0.005,
            bar.get_y() + bar.get_height() / 2,
            f"p={row['p_value']:.3f} ({sign})",
            va="center",
            fontsize=8,
        )

    # Dashed line at |r| = 0.3 (conventional small-effect threshold)
    ax.axvline(0.3, color="black", linestyle="--", linewidth=1, alpha=0.6, label="|r| = 0.3")

    ax.set_xlabel("|Spearman r|")
    ax.set_title("Correlation Summary: Factors vs PV Accuracy")
    ax.legend(fontsize=9)

    # Color legend patches
    pos_patch = mpatches.Patch(facecolor="#2196F3", label="Positive correlation")
    neg_patch = mpatches.Patch(facecolor="#F44336", label="Negative correlation")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles=handles + [pos_patch, neg_patch],
        labels=labels + ["Positive correlation", "Negative correlation"],
        fontsize=8,
        loc="lower right",
    )

    plt.tight_layout()

    os.makedirs(CHART_DIR, exist_ok=True)
    out_path = os.path.join(CHART_DIR, "correlation_summary.png")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_all_charts() -> dict[str, str]:
    """Generate all 6 analysis charts. Returns dict of name -> output path."""
    df = pd.read_csv(CSV_PATH)

    paths = {
        "h1_column_count": chart_h1_column_count(df),
        "h2_numeric_ratio": chart_h2_numeric_ratio(df),
        "h3_domain_boxplot": chart_h3_domain_boxplot(df),
        "h4_row_count": chart_h4_row_count(df),
        "h5_schema_coverage": chart_h5_schema_coverage(df),
        "correlation_summary": chart_correlation_summary(),
    }

    for name, path in paths.items():
        print(f"  {name}: {path}")

    return paths


if __name__ == "__main__":
    generate_all_charts()
