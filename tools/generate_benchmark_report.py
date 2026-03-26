"""Generate a .docx benchmark report for the PV accuracy factor analysis study."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURES_CSV = os.path.join(_REPO_ROOT, "analysis", "factor_analysis", "dataset_features_and_accuracy.csv")
CORR_CSV = os.path.join(_REPO_ROOT, "analysis", "factor_analysis", "correlation_summary.csv")
CHART_DIR = os.path.join(_REPO_ROOT, "analysis", "factor_analysis", "charts")
OUTPUT_PATH = os.path.join(_REPO_ROOT, "analysis", "pvmap_benchmark_study.docx")

# ---------------------------------------------------------------------------
# Color / verdict helpers
# ---------------------------------------------------------------------------

VERDICT_COLORS: dict[str, str] = {
    "SUPPORTED": "2E7D32",
    "REJECTED": "C62828",
    "PARTIALLY SUPPORTED": "E65100",
}


def get_verdict_color(verdict: str) -> str:
    """Return a hex color string for a verdict label."""
    return VERDICT_COLORS[verdict]


def format_stat_row(spearman_r: float, p_value: float, n: int) -> dict[str, str]:
    """Return a dict row for a statistics table."""
    significant = "Yes" if p_value < 0.05 else "No"
    return {
        "Spearman r": f"{spearman_r:.3f}",
        "p-value": f"{p_value:.3f}",
        "N": str(n),
        "Significant (p<0.05)": significant,
    }


# ---------------------------------------------------------------------------
# OxmlElement helpers
# ---------------------------------------------------------------------------

def _set_cell_shading(cell: Any, color_hex: str) -> None:
    """Set background shading on a table cell using OxmlElement."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tcPr.append(shd)


def _add_page_number_footer(doc: Document) -> None:
    """Add centered page number footer to all sections."""
    for section in doc.sections:
        footer = section.footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fld_char_begin = OxmlElement("w:fldChar")
        fld_char_begin.set(qn("w:fldCharType"), "begin")
        instr_text = OxmlElement("w:instrText")
        instr_text.set(qn("xml:space"), "preserve")
        instr_text.text = " PAGE "
        fld_char_end = OxmlElement("w:fldChar")
        fld_char_end.set(qn("w:fldCharType"), "end")
        run = p.add_run()
        run._element.append(fld_char_begin)
        run._element.append(instr_text)
        run._element.append(fld_char_end)


# ---------------------------------------------------------------------------
# Table builder
# ---------------------------------------------------------------------------

def _add_table(doc: Document, headers: list[str], rows: list[dict[str, str]]) -> None:
    """Add a formatted table with shaded header row."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"

    # Header row
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        _set_cell_shading(hdr_cells[i], "D6E4F0")
        for para in hdr_cells[i].paragraphs:
            for run in para.runs:
                run.font.bold = True
                run.font.size = Pt(9)
                run.font.name = "Calibri"

    # Data rows
    for r_idx, row in enumerate(rows, start=1):
        row_cells = table.rows[r_idx].cells
        for c_idx, header in enumerate(headers):
            row_cells[c_idx].text = str(row.get(header, ""))
            for para in row_cells[c_idx].paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9)
                    run.font.name = "Calibri"


# ---------------------------------------------------------------------------
# Document style setup
# ---------------------------------------------------------------------------

def _setup_document_styles(doc: Document) -> None:
    """Configure default Normal style and margins."""
    # Default paragraph font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    pf = style.paragraph_format
    pf.line_spacing = 1.15 * Pt(11)  # 1.15 line spacing approximation

    # Margins: 1 inch all sides
    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(2.54)
        section.right_margin = Cm(2.54)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    """Add a heading paragraph."""
    doc.add_heading(text, level=level)


def _add_chart(doc: Document, chart_filename: str, caption: str) -> None:
    """Add a chart image centered with an italic caption below."""
    chart_path = os.path.join(CHART_DIR, chart_filename)
    if os.path.exists(chart_path):
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run()
        run.add_picture(chart_path, width=Inches(6))
    else:
        doc.add_paragraph(f"[Chart not found: {chart_filename}]")

    caption_para = doc.add_paragraph()
    caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_run = caption_para.add_run(caption)
    caption_run.italic = True
    caption_run.font.size = Pt(9)
    caption_run.font.name = "Calibri"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _add_title_page(doc: Document) -> None:
    """Add title page content."""
    doc.add_paragraph()
    doc.add_paragraph()

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run("PV Accuracy Factor Analysis")
    title_run.bold = True
    title_run.font.size = Pt(24)
    title_run.font.name = "Calibri"

    subtitle_para = doc.add_paragraph()
    subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle_para.add_run("What Predicts Automated Schematization Success?")
    subtitle_run.font.size = Pt(16)
    subtitle_run.font.name = "Calibri"

    doc.add_paragraph()

    author_para = doc.add_paragraph()
    author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    author_run = author_para.add_run("Nehil Sood")
    author_run.font.size = Pt(13)
    author_run.font.name = "Calibri"

    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date_para.add_run("March 2026")
    date_run.font.size = Pt(12)
    date_run.font.name = "Calibri"

    doc.add_paragraph()

    desc_para = doc.add_paragraph()
    desc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    desc_run = desc_para.add_run("An analysis of 48 datasets evaluated with Gemini 3 Pro")
    desc_run.font.size = Pt(11)
    desc_run.font.name = "Calibri"
    desc_run.italic = True

    doc.add_page_break()


def _add_executive_summary(doc: Document) -> None:
    """Section 1: Executive Summary."""
    _add_heading(doc, "1. Executive Summary", level=1)

    bullets = [
        "Domain is the strongest predictor of PV accuracy. Datasets from well-covered domains "
        "(Census/Demographics, Employment/Labor, Environment) achieve significantly higher accuracy "
        "than those from Education, Crime/Safety, or Brazilian/Latin American sources.",
        "Column count has negligible correlation with accuracy (Spearman r = -0.099, p = 0.499). "
        "More columns do not make schematization harder in a statistically meaningful way.",
        "Row count is similarly uncorrelated (r = -0.051, p = 0.729). Dataset size does not predict "
        "difficulty.",
        "Numeric-to-categorical ratio shows the strongest continuous-feature signal (r = 0.202, "
        "p = 0.161), suggesting that datasets with more numeric columns are somewhat easier to "
        "schematize — but this falls short of statistical significance.",
        "Schema coverage tier (Strong vs Weak) is a useful proxy for expected accuracy. Domains "
        "with richer Data Commons schema coverage consistently outperform those without.",
    ]
    for bullet in bullets:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(bullet).font.name = "Calibri"


def _add_methodology(doc: Document) -> None:
    """Section 2: Methodology."""
    _add_heading(doc, "2. Methodology", level=1)

    _add_heading(doc, "2.1 Benchmark Description", level=2)
    doc.add_paragraph(
        "The benchmark consists of 48 real-world datasets spanning 10 domains, each processed "
        "by the automated PVMAP generation pipeline using Gemini 3 Pro. PV accuracy is computed "
        "as the fraction of property-value pairs in the generated PVMAP that match the ground "
        "truth annotation."
    )

    _add_heading(doc, "2.2 Features Extracted", level=2)
    doc.add_paragraph("Seven structural features were extracted from each dataset:")

    feature_headers = ["Feature", "Description", "Type"]
    feature_rows = [
        {"Feature": "column_count", "Description": "Total number of columns in the dataset", "Type": "Continuous"},
        {"Feature": "row_count", "Description": "Total number of rows (observations)", "Type": "Continuous"},
        {"Feature": "numeric_column_count", "Description": "Count of numeric columns", "Type": "Continuous"},
        {"Feature": "categorical_column_count", "Description": "Count of categorical (string) columns", "Type": "Continuous"},
        {"Feature": "numeric_to_categorical_ratio", "Description": "Ratio of numeric to categorical columns", "Type": "Continuous"},
        {"Feature": "max_column_cardinality", "Description": "Max unique values in any single column", "Type": "Continuous"},
        {"Feature": "mean_column_cardinality", "Description": "Mean unique values across all columns", "Type": "Continuous"},
    ]
    _add_table(doc, feature_headers, feature_rows)
    doc.add_paragraph()

    _add_heading(doc, "2.3 Statistical Method", level=2)
    doc.add_paragraph(
        "Spearman rank correlation was used to measure the monotonic relationship between each "
        "structural feature and PV accuracy. Spearman's rho is robust to outliers and non-normal "
        "distributions. Significance threshold: p < 0.05 (two-tailed). All correlations are "
        "computed on n = 48 datasets."
    )

    _add_heading(doc, "2.4 Correlation Overview", level=2)
    doc.add_paragraph(
        "Figure 1 shows the absolute Spearman correlation coefficient for each factor against "
        "PV accuracy. No single continuous feature exceeds the conventional small-effect threshold "
        "of |r| = 0.3, indicating that domain and schema coverage (categorical factors) are the "
        "primary drivers."
    )
    _add_chart(doc, "correlation_summary.png", "Figure 1. Spearman |r| for each structural factor vs PV accuracy.")


def _add_hypothesis_section(
    doc: Document,
    hypothesis_id: str,
    title: str,
    rationale: str,
    chart_filename: str,
    stats: list[dict[str, str]],
    verdict: str,
    interpretation: str,
    figure_num: int,
    figure_caption: str,
) -> None:
    """Add a complete hypothesis section (H1-H5)."""
    _add_heading(doc, f"{hypothesis_id}: {title}", level=2)

    rationale_para = doc.add_paragraph()
    bold_run = rationale_para.add_run("Rationale: ")
    bold_run.bold = True
    bold_run.font.name = "Calibri"
    rationale_para.add_run(rationale).font.name = "Calibri"

    _add_chart(doc, chart_filename, f"Figure {figure_num}. {figure_caption}")

    doc.add_paragraph()

    # Stats table
    if stats:
        stat_headers = list(stats[0].keys())
        _add_table(doc, stat_headers, stats)
        doc.add_paragraph()

    # Verdict
    verdict_para = doc.add_paragraph()
    verdict_label_run = verdict_para.add_run("Verdict: ")
    verdict_label_run.bold = True
    verdict_label_run.font.name = "Calibri"
    verdict_run = verdict_para.add_run(verdict)
    verdict_run.bold = True
    verdict_run.font.name = "Calibri"
    color_hex = get_verdict_color(verdict)
    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)
    verdict_run.font.color.rgb = RGBColor(r, g, b)

    # Interpretation
    interp_para = doc.add_paragraph()
    interp_label_run = interp_para.add_run("Interpretation: ")
    interp_label_run.bold = True
    interp_label_run.font.name = "Calibri"
    interp_para.add_run(interpretation).font.name = "Calibri"

    doc.add_paragraph()


def _add_hypotheses_section(doc: Document, df: pd.DataFrame) -> None:
    """Section 3: Hypotheses and Results."""
    _add_heading(doc, "3. Hypotheses & Results", level=1)

    # H1: Column count
    _add_hypothesis_section(
        doc=doc,
        hypothesis_id="H1",
        title="Column Count Does Not Predict PV Accuracy",
        rationale=(
            "Datasets with more columns require the LLM to map more properties, "
            "potentially increasing the chance of errors or hallucinations. "
            "We hypothesize a negative correlation between column count and accuracy."
        ),
        chart_filename="h1_column_count.png",
        stats=[format_stat_row(spearman_r=-0.099, p_value=0.499, n=48)],
        verdict="REJECTED",
        interpretation=(
            "Column count shows negligible negative correlation (r = -0.099) that is far from "
            "statistical significance (p = 0.499). Wide datasets are not harder to schematize "
            "than narrow ones. The hypothesis is rejected."
        ),
        figure_num=2,
        figure_caption="Column count (log scale) vs PV accuracy, colored by domain.",
    )

    # H2: Numeric ratio
    _add_hypothesis_section(
        doc=doc,
        hypothesis_id="H2",
        title="Numeric Column Ratio Shows Weak Positive Signal",
        rationale=(
            "Numeric columns have cleaner mapping targets (quantity, unit) in Data Commons. "
            "A higher ratio of numeric to categorical columns may make schematization easier, "
            "leading to higher PV accuracy."
        ),
        chart_filename="h2_numeric_ratio.png",
        stats=[format_stat_row(spearman_r=0.202, p_value=0.161, n=48)],
        verdict="PARTIALLY SUPPORTED",
        interpretation=(
            "The positive correlation (r = 0.202) is in the expected direction but does not "
            "reach significance (p = 0.161). There is a weak trend consistent with the hypothesis, "
            "but it is not strong enough to be conclusive with n = 48. Partially supported."
        ),
        figure_num=3,
        figure_caption="Numeric-to-categorical ratio vs PV accuracy. Triangles indicate all-categorical datasets.",
    )

    # H3: Domain breakdown
    domain_stats_rows = []
    for domain, grp in df.groupby("domain"):
        domain_stats_rows.append({
            "Domain": domain,
            "Mean PV Accuracy (%)": f"{grp['pv_accuracy'].mean():.1f}",
            "Median PV Accuracy (%)": f"{grp['pv_accuracy'].median():.1f}",
            "N": str(len(grp)),
        })
    domain_stats_rows.sort(key=lambda x: float(x["Mean PV Accuracy (%)"]), reverse=True)

    _add_hypothesis_section(
        doc=doc,
        hypothesis_id="H3",
        title="Domain Strongly Predicts PV Accuracy",
        rationale=(
            "Data Commons schema vocabulary coverage varies greatly by domain. "
            "Domains with rich existing StatVar hierarchies (Census, Employment) "
            "should yield higher accuracy than poorly-covered domains (Brazil/LatAm, Education)."
        ),
        chart_filename="h3_domain_boxplot.png",
        stats=domain_stats_rows,
        verdict="SUPPORTED",
        interpretation=(
            "Domain is the strongest predictor in the study. Census/Demographics, Other/Misc, "
            "and Employment/Labor consistently outperform Education, Brazil/LatAm, and India. "
            "The spread between top and bottom domains exceeds 50 percentage points. Supported."
        ),
        figure_num=4,
        figure_caption="PV accuracy distribution by domain (horizontal box plots with individual dataset points).",
    )

    # H4: Row count
    _add_hypothesis_section(
        doc=doc,
        hypothesis_id="H4",
        title="Row Count Does Not Predict PV Accuracy",
        rationale=(
            "Larger datasets (more rows) might challenge the sampling strategy, reducing "
            "the representative quality of the data fed to the LLM and lowering accuracy."
        ),
        chart_filename="h4_row_count.png",
        stats=[format_stat_row(spearman_r=-0.051, p_value=0.729, n=48)],
        verdict="REJECTED",
        interpretation=(
            "Row count is essentially uncorrelated with PV accuracy (r = -0.051, p = 0.729). "
            "Dataset size has no meaningful effect on schematization quality. The hypothesis "
            "that larger datasets are harder is rejected."
        ),
        figure_num=5,
        figure_caption="Row count (log scale) vs PV accuracy, colored by domain.",
    )

    # H5: Schema coverage tiers — compute dynamically
    from tools.generate_analysis_charts import SCHEMA_COVERAGE_TIERS
    df2 = df.copy()
    df2["tier"] = df2["domain"].map(lambda d: SCHEMA_COVERAGE_TIERS.get(d, "Weak"))

    strong_domains = [d for d, t in SCHEMA_COVERAGE_TIERS.items() if t == "Strong"]
    weak_domains = [d for d, t in SCHEMA_COVERAGE_TIERS.items() if t == "Weak"]

    strong_avg = df2[df2["tier"] == "Strong"]["pv_accuracy"].mean()
    moderate_avg = df2[df2["tier"] == "Moderate"]["pv_accuracy"].mean()
    weak_avg = df2[df2["tier"] == "Weak"]["pv_accuracy"].mean()

    tier_stats = [
        {
            "Tier": "Strong",
            "Domains": ", ".join(strong_domains),
            "Mean PV Accuracy (%)": f"{strong_avg:.1f}",
            "N": str(len(df2[df2["tier"] == "Strong"])),
        },
        {
            "Tier": "Moderate",
            "Domains": ", ".join([d for d, t in SCHEMA_COVERAGE_TIERS.items() if t == "Moderate"]),
            "Mean PV Accuracy (%)": f"{moderate_avg:.1f}",
            "N": str(len(df2[df2["tier"] == "Moderate"])),
        },
        {
            "Tier": "Weak",
            "Domains": ", ".join(weak_domains),
            "Mean PV Accuracy (%)": f"{weak_avg:.1f}",
            "N": str(len(df2[df2["tier"] == "Weak"])),
        },
    ]

    _add_hypothesis_section(
        doc=doc,
        hypothesis_id="H5",
        title="Schema Coverage Tier Predicts PV Accuracy",
        rationale=(
            "Domains with well-developed Data Commons schema vocabulary (Strong tier) should "
            "yield higher accuracy because the LLM has more valid property options to choose from "
            "and the schema injection provides better guidance."
        ),
        chart_filename="h5_schema_coverage.png",
        stats=tier_stats,
        verdict="SUPPORTED",
        interpretation=(
            f"Strong-tier domains achieve mean PV accuracy of {strong_avg:.1f}% compared to "
            f"{moderate_avg:.1f}% for Moderate and {weak_avg:.1f}% for Weak. "
            "The gap between Strong and Weak tiers confirms that schema coverage is a key "
            "predictor of automated schematization success. Supported."
        ),
        figure_num=6,
        figure_caption="Mean PV accuracy by domain grouped by schema coverage tier (Strong / Moderate / Weak).",
    )


def _add_dataset_clusters(doc: Document, df: pd.DataFrame) -> None:
    """Section 4: Dataset Clusters."""
    _add_heading(doc, "4. Dataset Clusters", level=1)

    doc.add_paragraph(
        "Datasets can be grouped into four performance clusters based on domain, structure, "
        "and accuracy characteristics:"
    )

    cluster_headers = ["Dataset", "Domain", "PV Accuracy (%)"]

    # Group 1: Zurich Wiki
    _add_heading(doc, "Group 1: Zurich Wiki (High Accuracy, Clean Structure)", level=2)
    doc.add_paragraph(
        "Small, well-structured datasets from Zurich municipal statistics. "
        "Consistent structure with few columns and clear semantics. Average ~45% PV accuracy."
    )
    zurich_rows = df[df["dataset"].str.startswith("zurich")].copy()
    zurich_rows = zurich_rows.sort_values("pv_accuracy", ascending=False)
    g1_rows = [
        {"Dataset": r["dataset"], "Domain": r["domain"], "PV Accuracy (%)": f"{r['pv_accuracy']:.1f}"}
        for _, r in zurich_rows.iterrows()
    ]
    _add_table(doc, cluster_headers, g1_rows)
    doc.add_paragraph()

    # Group 2: Clean Economic/Census
    _add_heading(doc, "Group 2: Clean Economic / Census (Medium-High Accuracy)", level=2)
    doc.add_paragraph(
        "Well-curated national statistics and economic datasets with clear column semantics "
        "and strong Data Commons schema alignment."
    )
    g2_names = [
        "undata", "usa_dol_minimum_wage", "opendataforafrica_ethiopia_statistics",
        "census_v2_saipe", "bis_bis_central_bank_policy_rate", "census_v2_sahie",
        "world_bank_commodity_market", "opendataforafrica_kenya_census",
    ]
    g2_df = df[df["dataset"].isin(g2_names)].sort_values("pv_accuracy", ascending=False)
    g2_rows = [
        {"Dataset": r["dataset"], "Domain": r["domain"], "PV Accuracy (%)": f"{r['pv_accuracy']:.1f}"}
        for _, r in g2_df.iterrows()
    ]
    _add_table(doc, cluster_headers, g2_rows)
    doc.add_paragraph()

    # Group 3: Health/Survey
    _add_heading(doc, "Group 3: Health / Survey (Medium Accuracy)", level=2)
    doc.add_paragraph(
        "Health surveys and epidemiological datasets with moderate complexity. "
        "Accuracy is limited by survey-specific terminology and indirect observation structures."
    )
    g3_names = [
        "inpe_fire", "india_nfhs", "brfss_nchs_asthma_prevalence",
        "cdc_social_vulnerability_index", "doctoratedegreeemployment", "us_cdc_single_race",
    ]
    g3_df = df[df["dataset"].isin(g3_names)].sort_values("pv_accuracy", ascending=False)
    g3_rows = [
        {"Dataset": r["dataset"], "Domain": r["domain"], "PV Accuracy (%)": f"{r['pv_accuracy']:.1f}"}
        for _, r in g3_df.iterrows()
    ]
    _add_table(doc, cluster_headers, g3_rows)
    doc.add_paragraph()

    # Group 4: Complex/Low Accuracy
    _add_heading(doc, "Group 4: Complex / Low Accuracy", level=2)
    doc.add_paragraph(
        "Highly complex or domain-specific datasets where the pipeline struggles. "
        "Includes Brazilian government statistics, South Korean pivot tables, and crash data."
    )
    g4_names = [
        "us_crash_fars_crashdata", "crdc_import_crdc_harassment_or_bullying",
        "brazil_visdata_FoodBasketDistribution", "brazil_visdata_brazil_rural_development_program",
        "brazil_sidra_ibge", "southkorea_statistics_education", "southkorea_statistics_employment",
    ]
    g4_df = df[df["dataset"].isin(g4_names)].sort_values("pv_accuracy", ascending=False)
    g4_rows = [
        {"Dataset": r["dataset"], "Domain": r["domain"], "PV Accuracy (%)": f"{r['pv_accuracy']:.1f}"}
        for _, r in g4_df.iterrows()
    ]
    _add_table(doc, cluster_headers, g4_rows)
    doc.add_paragraph()


def _add_conclusions(doc: Document, df: pd.DataFrame) -> None:
    """Section 5: Conclusions."""
    _add_heading(doc, "5. Conclusions", level=1)

    from tools.generate_analysis_charts import SCHEMA_COVERAGE_TIERS
    df2 = df.copy()
    df2["tier"] = df2["domain"].map(lambda d: SCHEMA_COVERAGE_TIERS.get(d, "Weak"))
    strong_avg = df2[df2["tier"] == "Strong"]["pv_accuracy"].mean()
    weak_avg = df2[df2["tier"] == "Weak"]["pv_accuracy"].mean()
    overall_avg = df["pv_accuracy"].mean()

    paragraphs = [
        (
            "Domain is the dominant predictor of PV accuracy.",
            f" Across 48 datasets, domain explains more variance in PV accuracy than any structural "
            f"feature. Datasets in Census/Demographics, Employment/Labor, and Environment domains "
            f"achieve substantially higher accuracy than Education, Crime/Safety, or Brazil/LatAm datasets."
        ),
        (
            "Schema coverage tier is a practical proxy for expected performance.",
            f" The average PV accuracy for Strong-tier domains ({strong_avg:.1f}%) is markedly higher "
            f"than for Weak-tier domains ({weak_avg:.1f}%), a gap of {strong_avg - weak_avg:.1f} "
            f"percentage points. Teams prioritizing high-accuracy output should focus on domains with "
            f"rich Data Commons schema coverage."
        ),
        (
            "Structural complexity (column count, row count) is not a reliable difficulty signal.",
            f" Neither column count (r = -0.099) nor row count (r = -0.051) correlates significantly "
            f"with PV accuracy. Dataset size and width are poor predictors of schematization difficulty."
        ),
        (
            "Numeric content has a weak positive association with accuracy.",
            f" The numeric-to-categorical ratio shows the strongest continuous signal (r = 0.202, p = 0.161), "
            f"consistent with the idea that numeric columns map more cleanly to Data Commons quantity "
            f"properties. This effect warrants further investigation with a larger dataset."
        ),
        (
            "Overall pipeline performance averages {:.1f}% PV accuracy.".format(overall_avg),
            f" This reflects the challenge of fully automated schematization across diverse real-world "
            f"datasets. Targeted improvements in weak-tier domains — particularly better schema examples "
            f"and domain-specific prompt tuning — represent the highest-leverage opportunities."
        ),
    ]

    for bold_lead, rest in paragraphs:
        p = doc.add_paragraph()
        bold_run = p.add_run(bold_lead)
        bold_run.bold = True
        bold_run.font.name = "Calibri"
        rest_run = p.add_run(rest)
        rest_run.font.name = "Calibri"


def _add_appendix(doc: Document, df: pd.DataFrame) -> None:
    """Appendix: Dataset Reference table with aliases."""
    _add_heading(doc, "Appendix: Dataset Reference", level=1)
    doc.add_paragraph(
        "The following table maps short chart labels (aliases) to full dataset names "
        "for datasets where the alias differs from the full name."
    )

    from tools.generate_analysis_charts import build_alias_table
    alias_df = build_alias_table(df)

    if alias_df.empty:
        doc.add_paragraph("All dataset names are short enough to display directly in charts.")
        return

    headers = ["Alias", "Full Dataset Name", "Domain", "PV Accuracy (%)"]
    rows = []
    for _, row in alias_df.sort_values("alias").iterrows():
        rows.append({
            "Alias": row["alias"],
            "Full Dataset Name": row["full_name"],
            "Domain": row["domain"],
            "PV Accuracy (%)": f"{row['pv_accuracy']:.1f}",
        })

    _add_table(doc, headers, rows)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_report(output_path: str = OUTPUT_PATH) -> str:
    """Build the full benchmark report .docx and return the output path."""
    df = pd.read_csv(FEATURES_CSV)

    doc = Document()
    _setup_document_styles(doc)
    _add_page_number_footer(doc)

    # Title page
    _add_title_page(doc)

    # Section 1: Executive Summary
    _add_executive_summary(doc)
    doc.add_paragraph()

    # Section 2: Methodology
    _add_methodology(doc)
    doc.add_paragraph()

    # Section 3: Hypotheses & Results
    _add_hypotheses_section(doc, df)

    # Section 4: Dataset Clusters
    _add_dataset_clusters(doc, df)

    # Section 5: Conclusions
    _add_conclusions(doc, df)

    # Appendix
    doc.add_page_break()
    _add_appendix(doc, df)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


if __name__ == "__main__":
    out = build_report()
    print(f"Report saved to: {out}")
