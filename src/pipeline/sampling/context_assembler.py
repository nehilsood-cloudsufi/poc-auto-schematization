"""Deterministic context assembly for programmatic sampling.

Assembles a skeleton_summary and data_context dict from the profiler output,
LLM semantic analysis, relational skeleton, and optional grounded StatVars.

Reuses the DataContext.to_skeleton_summary() template with enhanced sections:
- Section 10: GROUNDED STATVARS (if MCP enabled)
- Section 11: DATA WARNINGS (sentinels, functional dependencies)

SIZE GUARDRAIL: skeleton_summary <= 37,500 chars with progressive trimming.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False

from src.agents.sampling.schemas import (
    RelationalSkeleton,
    SemanticAnalysis,
)
from src.agents.template_utils import escape_pvmap_placeholders
from src.pipeline.sampling.profiler import DatasetProfile
from src.pipeline.sampling.statvar_grounder import GroundedStatVar

logger = logging.getLogger(__name__)

# Maximum skeleton_summary size (chars)
MAX_SKELETON_SIZE = 37_500

# Markers for new sections so feedback compaction can drop them
SECTION_10_MARKER = "<!-- SECTION_10_GROUNDED_STATVARS -->"
SECTION_11_MARKER = "<!-- SECTION_11_DATA_WARNINGS -->"


def assemble_context(
    profile: DatasetProfile,
    analysis: SemanticAnalysis,
    skeleton: RelationalSkeleton,
    sampled_file: Path,
    grounded_statvars: Optional[List[GroundedStatVar]] = None,
) -> Tuple[str, dict]:
    """Assemble skeleton_summary and data_context from analysis results.

    Args:
        profile: DatasetProfile from profiler.
        analysis: SemanticAnalysis from LLM.
        skeleton: RelationalSkeleton from LLM.
        sampled_file: Path to the sampled CSV file.
        grounded_statvars: Optional list of grounded StatVars.

    Returns:
        Tuple of (skeleton_summary: str, data_context: dict).
    """
    # Build column roles dict from analysis
    column_roles = {
        col.column_name: col.role
        for col in analysis.columns
    }

    # Build dimension domains from sampled data
    dimension_domains = _build_dimension_domains(sampled_file, skeleton.dimension_columns)

    # Build geography info
    geo_info = _build_geo_info(profile, skeleton, analysis)

    # Build time info
    time_info = _build_time_info(profile, skeleton, analysis)

    # Build value columns info
    value_columns = [
        {"name": vc, "stat_type": analysis.measurement_type}
        for vc in skeleton.value_columns
    ]

    # Generate place resolution hints
    place_hints = _generate_place_hints(geo_info, profile, skeleton)

    # Generate one-shot example
    one_shot = _generate_one_shot(
        geo_info, time_info, skeleton, dimension_domains,
        analysis.population_type, analysis.measurement_type, value_columns,
    )

    # Build column stats for Section 1.5
    column_stats = _build_column_stats(profile, analysis)

    # Assemble skeleton summary
    skeleton_summary = _assemble_skeleton_summary(
        profile=profile,
        analysis=analysis,
        skeleton=skeleton,
        column_roles=column_roles,
        dimension_domains=dimension_domains,
        geo_info=geo_info,
        time_info=time_info,
        value_columns=value_columns,
        place_hints=place_hints,
        one_shot=one_shot,
        column_stats=column_stats,
        grounded_statvars=grounded_statvars,
    )

    # Apply size guardrail
    skeleton_summary = _apply_size_guardrail(
        skeleton_summary, dimension_domains, column_stats, profile
    )

    # Escape PVMAP placeholders for ADK safety
    skeleton_summary = escape_pvmap_placeholders(skeleton_summary)

    # Build data_context dict (backward compatible)
    data_context = _build_data_context_dict(
        profile=profile,
        analysis=analysis,
        skeleton=skeleton,
        column_roles=column_roles,
        dimension_domains=dimension_domains,
        geo_info=geo_info,
        time_info=time_info,
        value_columns=value_columns,
        place_hints=place_hints,
        column_stats=column_stats,
        skeleton_summary=skeleton_summary,
        sampled_file=sampled_file,
    )

    # Write data_context.json for caching
    _write_context_cache(sampled_file, data_context, skeleton_summary)

    return skeleton_summary, data_context


def _build_dimension_domains(
    sampled_file: Path, dimension_columns: List[str]
) -> Dict[str, List[str]]:
    """Extract unique dimension values from sampled data."""
    if not PANDAS_AVAILABLE or not sampled_file.exists():
        return {}

    try:
        df = pd.read_csv(
            sampled_file, encoding='utf-8', on_bad_lines='skip', low_memory=False
        )
        domains = {}
        for col in dimension_columns:
            if col in df.columns:
                domains[col] = sorted([str(v) for v in df[col].dropna().unique()])
        return domains
    except Exception as e:
        logger.warning("Failed to build dimension domains: %s", e)
        return {}


def _build_geo_info(
    profile: DatasetProfile,
    skeleton: RelationalSkeleton,
    analysis: SemanticAnalysis,
) -> Dict[str, Any]:
    """Build geography info dict."""
    place_col = skeleton.place_column
    col_profile = profile.columns.get(place_col)
    if not col_profile:
        return {}

    # Get semantic type from analysis
    semantic_type = None
    for col in analysis.columns:
        if col.column_name == place_col:
            semantic_type = col.semantic_type
            break

    return {
        "column": place_col,
        "format": semantic_type or col_profile.semantic_type or "NAME",
        "unique_values": col_profile.cardinality,
        "sample_values": col_profile.sample_values[:5],
    }


def _build_time_info(
    profile: DatasetProfile,
    skeleton: RelationalSkeleton,
    analysis: SemanticAnalysis,
) -> Dict[str, Any]:
    """Build time info dict."""
    time_col = skeleton.time_column
    col_profile = profile.columns.get(time_col)
    if not col_profile:
        return {}

    semantic_type = None
    for col in analysis.columns:
        if col.column_name == time_col:
            semantic_type = col.semantic_type
            break

    return {
        "column": time_col,
        "format": semantic_type or col_profile.semantic_type or "YYYY",
        "sample_values": col_profile.sample_values[:5],
    }


def _generate_place_hints(
    geo_info: Dict[str, Any],
    profile: DatasetProfile,
    skeleton: RelationalSkeleton,
) -> List[Dict[str, str]]:
    """Generate place -> DCID resolution hints.

    Reuses logic from DataContextGenerator._generate_place_resolution_hints().
    """
    if not geo_info:
        return []

    geo_format = geo_info.get("format", "NAME")
    sample_values = geo_info.get("sample_values", [])

    GEO_FORMAT_MAP = {
        'FIPS_STATE': ('geoId/{val:0>2}', 'geoId/'),
        'FIPS_COUNTY': ('geoId/{val:0>5}', 'geoId/'),
        'FIPS': ('geoId/{val}', 'geoId/'),
        'ISO_2': ('country/{val}', 'country/'),
        'ISO_3': ('country/{val}', 'country/'),
        'DC_DCID': ('{val}', ''),
        'NAME': ('{val}', ''),  # NAME needs per-value resolution, not wikidataId/ prefix
        'NUMERIC_CODE': ('geoId/{val}', 'geoId/'),
    }

    format_info = GEO_FORMAT_MAP.get(geo_format)
    if not format_info:
        return []

    _, prefix = format_info
    hints = []
    for raw in sample_values[:5]:
        raw_str = str(raw).strip()
        if geo_format == 'FIPS_STATE':
            try:
                suggested = f"geoId/{int(raw_str):02d}"
            except (ValueError, TypeError):
                suggested = f"geoId/{raw_str}"
        elif geo_format == 'FIPS_COUNTY':
            try:
                suggested = f"geoId/{int(raw_str):05d}"
            except (ValueError, TypeError):
                suggested = f"geoId/{raw_str}"
        elif geo_format == 'DC_DCID':
            suggested = raw_str
        elif geo_format == 'NAME':
            # NAME format: suggest country/ prefix as a hint, but mark as
            # needing resolution (wikidataId/{name} is NOT a valid DCID)
            suggested = f"country/TODO_RESOLVE_{raw_str.replace(' ', '_')}"
        elif prefix:
            suggested = f"{prefix}{raw_str}"
        else:
            suggested = raw_str

        hints.append({
            "raw_value": raw_str,
            "suggested_dcid": suggested,
        })

    return hints


def _generate_one_shot(
    geo_info: Dict[str, Any],
    time_info: Dict[str, Any],
    skeleton: RelationalSkeleton,
    dimension_domains: Dict[str, List[str]],
    population_type: str,
    measurement_type: str,
    value_columns: List[Dict],
) -> str:
    """Generate a one-shot PVMAP example.

    Reuses logic from DataContextGenerator._generate_one_shot_example().
    """
    GEO_FORMAT_MAP = {
        'FIPS_STATE': ('geoId/{val:0>2}', 'geoId/'),
        'FIPS_COUNTY': ('geoId/{val:0>5}', 'geoId/'),
        'FIPS': ('geoId/{val}', 'geoId/'),
        'ISO_2': ('country/{val}', 'country/'),
        'ISO_3': ('country/{val}', 'country/'),
        'DC_DCID': ('{val}', ''),
        'NAME': ('wikidataId/{val}', 'wikidataId/'),
        'NUMERIC_CODE': ('geoId/{val}', 'geoId/'),
    }

    lines = ["key,property,value"]

    # Place anchor
    if geo_info:
        geo_col = geo_info.get("column", "")
        geo_format = geo_info.get("format", "NAME")
        geo_unique = geo_info.get("unique_values", 0)
        geo_samples = geo_info.get("sample_values", [])
        format_info = GEO_FORMAT_MAP.get(geo_format)
        if format_info:
            _, prefix = format_info
            if geo_format == 'FIPS_STATE':
                lines.append(f'{geo_col},#Format,observationAbout=geoId/{{Number:0>2}}')
            elif geo_format == 'FIPS_COUNTY':
                lines.append(f'{geo_col},#Format,observationAbout=geoId/{{Number:0>5}}')
            elif geo_format == 'DC_DCID':
                lines.append(f'{geo_col},observationAbout,{{Data}}')
            elif geo_format == 'NAME' and 0 < geo_unique <= 10 and geo_samples:
                # For NAME format with low cardinality, enumerate per-value
                # rows so the LLM sees it must resolve each name to a DCID.
                # wikidataId/{name} is NOT valid — the LLM must find real DCIDs.
                for val in geo_samples:
                    val_str = str(val).strip()
                    lines.append(
                        f'{geo_col}:{val_str},observationAbout,'
                        f'TODO_RESOLVE_DCID_FOR_{val_str.replace(" ", "_")}'
                    )
            elif prefix:
                lines.append(f'{geo_col},observationAbout,{prefix}{{Data}}')
            else:
                lines.append(f'{geo_col},observationAbout,{{Data}}')
        else:
            lines.append(f'{geo_col},observationAbout,{{Data}}')

    # Time anchor — use {Number} for numeric year formats, {Data} otherwise
    if time_info:
        time_col = time_info.get("column", "")
        time_format = time_info.get("format", "")
        NUMERIC_TIME_FORMATS = {"YYYY", "YEAR", "year", "yyyy"}
        if time_format in NUMERIC_TIME_FORMATS:
            lines.append(f'{time_col},observationDate,{{Number}}')
        else:
            lines.append(f'{time_col},observationDate,{{Data}}')

    # Dimension values (enumerate for dims with <=10 values)
    for dim in skeleton.dimension_columns:
        values = dimension_domains.get(dim, [])
        if 0 < len(values) <= 10:
            for val in values:
                val_str = str(val)
                dim_prop = dim.lower().replace(' ', '')
                lines.append(f'{dim}:{val_str},{dim_prop},{val_str}')

    # Value column with StatVar properties
    if value_columns:
        vc = value_columns[0]
        vc_name = vc.get("name", "Value")
        meas = measurement_type.lower()
        lines.append(
            f'{vc_name},value,{{Number}},populationType,{population_type},'
            f'measuredProperty,{meas},statType,measuredValue'
        )

    return "\n".join(lines)


def _build_column_stats(
    profile: DatasetProfile, analysis: SemanticAnalysis
) -> Dict[str, Dict[str, Any]]:
    """Build column stats dict for Section 1.5."""
    stats = {}
    for col_name, col_profile in profile.columns.items():
        stats[col_name] = {
            "dtype": col_profile.dtype,
            "cardinality": col_profile.cardinality,
            "null_pct": col_profile.null_pct,
            "sample_values": col_profile.sample_values,
            "semantic_type": col_profile.semantic_type,
            "is_numeric_categorical": col_profile.is_numeric_categorical,
        }
    return stats


def _assemble_skeleton_summary(
    profile: DatasetProfile,
    analysis: SemanticAnalysis,
    skeleton: RelationalSkeleton,
    column_roles: Dict[str, str],
    dimension_domains: Dict[str, List[str]],
    geo_info: Dict[str, Any],
    time_info: Dict[str, Any],
    value_columns: List[Dict],
    place_hints: List[Dict[str, str]],
    one_shot: str,
    column_stats: Dict[str, Dict[str, Any]],
    grounded_statvars: Optional[List[GroundedStatVar]] = None,
) -> str:
    """Assemble the 11-section skeleton summary markdown."""
    lines = []
    dataset_name = Path(profile.file_path).parent.parent.name

    # === Section 1: Topology & Structure ===
    lines.append("## 1. TOPOLOGY & STRUCTURE")
    lines.append("")
    lines.append(f"- **Dataset:** {dataset_name}")
    lines.append(f"- **Format:** {analysis.topology}")
    lines.append(f"- **Rows:** {profile.total_rows}  |  **Columns:** {profile.total_columns}")
    lines.append("")
    if profile.headers:
        lines.append(f"**ALL column headers (exact, case-sensitive):** `{'`, `'.join(profile.headers)}`")
    lines.append("")

    # === Section 1.5: Column Reference Table ===
    if column_stats:
        lines.append("## 1.5 COLUMN REFERENCE TABLE (USE EXACT NAMES AS PVMAP KEYS)")
        lines.append("")
        lines.append("| Column Header (EXACT) | Type | Unique Values | Semantic | Sample Values |")
        lines.append("|------------------------|------|---------------|----------|---------------|")
        for col, stats in column_stats.items():
            dtype = stats.get("dtype", "?")
            cardinality = stats.get("cardinality", "?")
            sem_type = stats.get("semantic_type") or ""
            is_num_cat = " [num-cat]" if stats.get("is_numeric_categorical") else ""
            samples = stats.get("sample_values", [])
            samples_str = ", ".join(str(v) for v in samples[:5])
            if len(samples_str) > 50:
                samples_str = samples_str[:47] + "..."
            sentinel_warning = ""
            col_profile = profile.columns.get(col)
            if col_profile and col_profile.sentinel_values:
                sentinel_warning = f" SENTINEL:{','.join(col_profile.sentinel_values[:3])}"
            lines.append(
                f"| `{col}` | {dtype}{is_num_cat} | {cardinality} | {sem_type} | {samples_str}{sentinel_warning} |"
            )
        lines.append("")

    # === Section 2: Column Classifications ===
    lines.append("## 2. COLUMN CLASSIFICATIONS")
    lines.append("")
    if column_roles:
        lines.append("| Column | Role | Confidence |")
        lines.append("|--------|------|------------|")
        for col_cls in analysis.columns:
            lines.append(f"| `{col_cls.column_name}` | {col_cls.role} | {col_cls.confidence} |")

    ignored = [name for name, role in column_roles.items() if role == "metadata"]
    if ignored:
        lines.append("")
        lines.append(f"**Ignored columns** (metadata/constant — do NOT map): `{'`, `'.join(ignored)}`")

    # Functional dependency notes
    if profile.functional_dependencies:
        lines.append("")
        lines.append("**Functional dependencies:**")
        for dep in profile.functional_dependencies[:5]:
            lines.append(f"- `{dep['source']}` determines `{dep['target']}`")
    lines.append("")

    # === Section 3: Anchor Analysis ===
    lines.append("## 3. ANCHOR ANALYSIS")
    lines.append("")
    if geo_info:
        geo_col = geo_info.get("column", "Unknown")
        geo_fmt = geo_info.get("format", "Unknown")
        geo_samples = geo_info.get("sample_values", [])
        lines.append(f"**Geography:** Column `{geo_col}` — Format: {geo_fmt}")
        if geo_samples:
            lines.append(f"  Sample values: {', '.join(str(v) for v in geo_samples[:5])}")
        if place_hints:
            lines.append("  **Place -> DCID resolution hints:**")
            for hint in place_hints[:5]:
                lines.append(f"  - `{hint.get('raw_value', '?')}` -> `{hint.get('suggested_dcid', '?')}`")
    else:
        lines.append("**Geography:** Not detected (CRITICAL: must identify)")
    lines.append("")

    if time_info:
        time_col = time_info.get("column", "Unknown")
        time_fmt = time_info.get("format", "Unknown")
        time_samples = time_info.get("sample_values", [])
        lines.append(f"**Time:** Column `{time_col}` — Format: {time_fmt}")
        if time_samples:
            lines.append(f"  Sample values: {', '.join(str(v) for v in time_samples[:5])}")
    else:
        lines.append("**Time:** Not detected")
    lines.append("")

    # === Section 4: Dimension Deep Dive ===
    lines.append("## 4. DIMENSION DEEP DIVE")
    lines.append("")
    if skeleton.dimension_columns:
        for dim in skeleton.dimension_columns:
            values = dimension_domains.get(dim, [])
            values_preview = values[:15]
            values_str = ", ".join(str(v) for v in values_preview)
            if len(values) > 15:
                values_str += f", ... ({len(values)} total)"
            lines.append(f"- **`{dim}`** ({len(values)} values): [{values_str}]")
            agg_flags_dict = skeleton.get_aggregate_flags_dict()
            agg_vals = agg_flags_dict.get(dim, [])
            if agg_vals:
                lines.append(
                    f"  Aggregate values detected: {', '.join(agg_vals)} "
                    "-- consider dropping constraint or mapping to empty value"
                )

        # Dependency edges
        qualifier_edges = [e for e in skeleton.edges if e.relationship == "qualifier"]
        if qualifier_edges:
            lines.append("")
            lines.append("**Dimension -> Value relationships:**")
            for edge in qualifier_edges[:10]:
                prop = f" (dc_property: {edge.dc_property})" if edge.dc_property else ""
                lines.append(f"- `{edge.source}` qualifies `{edge.target}`{prop}")
    else:
        lines.append("- No dimension columns detected")
    lines.append("")

    # === Section 5: Measurement & Units ===
    lines.append("## 5. MEASUREMENT & UNITS")
    lines.append("")
    if value_columns:
        for vc in value_columns:
            vc_name = vc.get("name", "Unknown")
            vc_type = vc.get("stat_type", analysis.measurement_type)
            lines.append(f"- Value Column: `{vc_name}` (StatType: {vc_type})")
    else:
        lines.append("- No value columns detected")
    lines.append(f"- **Population Type:** {analysis.population_type}")
    lines.append(f"- **Measurement Type:** {analysis.measurement_type}")
    lines.append("")

    # === Section 6: StatVar Pattern ===
    lines.append("## 6. STATVAR PATTERN (P+M+C Formula)")
    lines.append("")
    if skeleton.statvar_pattern:
        lines.append(f"`{skeleton.statvar_pattern}`")
    else:
        lines.append("- Pattern not yet determined")
    lines.append("")

    # === Section 7: One-Shot PVMAP Example ===
    lines.append("## 7. ONE-SHOT PVMAP EXAMPLE")
    lines.append("")
    if one_shot:
        lines.append("```csv")
        lines.append(one_shot)
        lines.append("```")
    else:
        lines.append("_No one-shot example available._")
    lines.append("")

    # === Section 8: Pre-Formatted DC Detection ===
    lines.append("## 8. PRE-FORMATTED DATA COMMONS DETECTION")
    lines.append("")
    if analysis.is_preformatted_dc:
        lines.append("**YES -- This data is already in Data Commons format.**")
        lines.append("Use passthrough mapping:")
        lines.append("```csv")
        lines.append("key,property,value")
        lines.append("observationAbout,observationAbout,{Data}")
        lines.append("observationDate,observationDate,{Data}")
        lines.append("variableMeasured,variableMeasured,{Data}")
        lines.append("value,value,{Number}")
        lines.append("```")
    else:
        lines.append("Not pre-formatted. Generate PVMAP from scratch.")
    lines.append("")

    # === Section 9: Coverage ===
    lines.append("## 9. COVERAGE")
    lines.append("")
    total_combos = 1
    for dim in skeleton.dimension_columns:
        vals = dimension_domains.get(dim, [])
        total_combos *= max(1, len(vals))
    lines.append(f"- Total Dimension Combinations: {total_combos}")
    lines.append("")
    lines.append("**IMPORTANT:** Generate PVMAP for ALL dimension combinations, not just those in sample.")
    lines.append("")
    lines.append("**KEY MATCHING RULE:** Every key in your PVMAP must EXACTLY match a column header from Section 1.5 (case-sensitive), or be a cell value in COLUMN:VALUE format.")
    lines.append("")

    # === Section 10: Grounded StatVars (optional) ===
    if grounded_statvars:
        confirmed = [sv for sv in grounded_statvars if sv.confirmed]
        if confirmed:
            lines.append(SECTION_10_MARKER)
            lines.append("## 10. GROUNDED STATVARS (Verified in Data Commons)")
            lines.append("")
            for sv in confirmed[:10]:
                lines.append(f"- `{sv.dcid}`: {sv.description}")
            lines.append("")

    # === Section 11: Data Warnings ===
    warnings = _build_data_warnings(profile, skeleton)
    if warnings:
        lines.append(SECTION_11_MARKER)
        lines.append("## 11. DATA WARNINGS")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def _build_data_warnings(
    profile: DatasetProfile, skeleton: RelationalSkeleton
) -> List[str]:
    """Build data warning strings for Section 11."""
    warnings = []

    # Sentinel warnings
    for col_name, col_profile in profile.columns.items():
        if col_profile.sentinel_values and col_name in skeleton.value_columns:
            sentinels = ", ".join(col_profile.sentinel_values[:5])
            warnings.append(
                f"Column `{col_name}` contains sentinel values [{sentinels}] "
                "-- skip rows with these values"
            )

    # Metadata row warnings
    if profile.metadata_rows:
        warnings.append(
            f"Detected {len(profile.metadata_rows)} metadata row(s) (units/descriptions) "
            "— excluded from profiling and sampling"
        )
        for row in profile.metadata_rows[:3]:
            pairs = [
                f"{k}: {v}" for k, v in row.items()
                if v is not None and str(v).strip()
            ]
            if pairs:
                warnings.append(f"  Metadata row content: {', '.join(pairs[:8])}")
        warnings.append("Use this information to understand units, formats, and column semantics.")

    # Functional dependency warnings
    for dep in profile.functional_dependencies[:3]:
        warnings.append(
            f"Column `{dep['source']}` fully determines `{dep['target']}` "
            "-- avoid mapping both as independent dimensions"
        )

    # Aggregate row warnings
    for dim, agg_vals in profile.aggregate_flags.items():
        if dim in skeleton.dimension_columns:
            vals = ", ".join(agg_vals[:5])
            warnings.append(
                f"Dimension `{dim}` has aggregate rows [{vals}] "
                "-- map with #Aggregate or drop constraint"
            )

    return warnings


def _apply_size_guardrail(
    skeleton: str,
    dimension_domains: Dict[str, List[str]],
    column_stats: Dict[str, Dict[str, Any]],
    profile: DatasetProfile,
) -> str:
    """Progressive trimming to stay under MAX_SKELETON_SIZE."""
    if len(skeleton) <= MAX_SKELETON_SIZE:
        return skeleton

    logger.warning(
        "Skeleton summary is %d chars (max %d), applying trims",
        len(skeleton), MAX_SKELETON_SIZE,
    )

    # Trim 1: Reduce Section 4 dimension values (15 -> 5)
    # This is a rough trim via string replacement
    for dim, values in dimension_domains.items():
        if len(values) > 5:
            old_preview = ", ".join(str(v) for v in values[:15])
            new_preview = ", ".join(str(v) for v in values[:5])
            if len(values) > 5:
                new_preview += f", ... ({len(values)} total)"
            skeleton = skeleton.replace(old_preview, new_preview, 1)

    if len(skeleton) <= MAX_SKELETON_SIZE:
        return skeleton

    # Trim 2: Reduce Section 1.5 sample values (5 -> 2)
    for col_name, stats in column_stats.items():
        samples = stats.get("sample_values", [])
        if len(samples) > 2:
            old_str = ", ".join(str(v) for v in samples[:5])
            new_str = ", ".join(str(v) for v in samples[:2])
            skeleton = skeleton.replace(old_str, new_str, 1)

    if len(skeleton) <= MAX_SKELETON_SIZE:
        return skeleton

    # Trim 3: Drop Section 11 (DATA WARNINGS)
    if SECTION_11_MARKER in skeleton:
        idx = skeleton.index(SECTION_11_MARKER)
        # Find next section or end
        next_section = skeleton.find("\n## ", idx + len(SECTION_11_MARKER))
        if next_section == -1:
            skeleton = skeleton[:idx].rstrip()
        else:
            skeleton = skeleton[:idx] + skeleton[next_section:]

    if len(skeleton) <= MAX_SKELETON_SIZE:
        return skeleton

    # Trim 4: Drop Section 10 (GROUNDED STATVARS)
    if SECTION_10_MARKER in skeleton:
        idx = skeleton.index(SECTION_10_MARKER)
        next_section = skeleton.find("\n## ", idx + len(SECTION_10_MARKER))
        if next_section == -1:
            skeleton = skeleton[:idx].rstrip()
        else:
            skeleton = skeleton[:idx] + skeleton[next_section:]

    if len(skeleton) > MAX_SKELETON_SIZE:
        logger.warning(
            "Skeleton still %d chars after all trims (max %d)",
            len(skeleton), MAX_SKELETON_SIZE,
        )

    return skeleton


def _build_data_context_dict(
    profile: DatasetProfile,
    analysis: SemanticAnalysis,
    skeleton: RelationalSkeleton,
    column_roles: Dict[str, str],
    dimension_domains: Dict[str, List[str]],
    geo_info: Dict[str, Any],
    time_info: Dict[str, Any],
    value_columns: List[Dict],
    place_hints: List[Dict[str, str]],
    column_stats: Dict[str, Dict[str, Any]],
    skeleton_summary: str,
    sampled_file: Path,
) -> dict:
    """Build backward-compatible data_context dict."""
    total_combos = 1
    for dim in skeleton.dimension_columns:
        vals = dimension_domains.get(dim, [])
        total_combos *= max(1, len(vals))

    return {
        "dataset_name": Path(profile.file_path).parent.parent.name,
        "topology": analysis.topology,
        "population_type": analysis.population_type,
        "geography": geo_info,
        "time": time_info,
        "column_roles": column_roles,
        "dimension_columns": skeleton.dimension_columns,
        "dimension_domains": dimension_domains,
        "hidden_constraints": [],
        "value_columns": value_columns,
        "measurement_type": analysis.measurement_type,
        "statvar_pattern": skeleton.statvar_pattern,
        "total_combinations": total_combos,
        "sample_combinations": 0,
        "coverage_percent": 0.0,
        "total_rows": profile.total_rows,
        "total_columns": profile.total_columns,
        "all_columns": profile.headers,
        "ignored_columns": [n for n, r in column_roles.items() if r == "metadata"],
        "aggregate_values": skeleton.get_aggregate_flags_dict(),
        "place_resolution_hints": place_hints,
        "is_preformatted_dc": analysis.is_preformatted_dc,
        "column_stats": column_stats,
        "sampled_file": str(sampled_file),
        # Nested for backward compat with ProgrammaticSamplingAgent._populate_state_from_context
        "skeleton_summary": skeleton_summary,
        "success": True,
        "data_context": {
            "dataset_name": Path(profile.file_path).parent.parent.name,
            "column_roles": column_roles,
            "dimension_columns": skeleton.dimension_columns,
            "row_count": profile.total_rows,
            "column_count": profile.total_columns,
            "sampled_file": str(sampled_file),
        },
    }


def _write_context_cache(
    sampled_file: Path, data_context: dict, skeleton_summary: str
) -> None:
    """Write data_context.json for caching."""
    context_file = sampled_file.parent / "data_context.json"
    try:
        def json_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            if hasattr(obj, 'tolist'):
                return obj.tolist()
            return str(obj)

        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(data_context, f, indent=2, default=json_serializer)
        logger.info("Wrote context cache to %s", context_file)
    except Exception as e:
        logger.warning("Failed to write context cache: %s", e)
