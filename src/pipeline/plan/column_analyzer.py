"""Phase A: Programmatic column relationship analyzer.

Computes pairwise column relationships, composite key detection,
place/time format detection, and value profiles using pure Python/pandas.
NO LLM calls -- deterministic structural analysis only.

This module adds PAIRWISE relationship analysis on top of the per-column
profiling in ``src/pipeline/sampling/profiler.py``.
"""

import itertools
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import numpy as np

from src.api.models.plan import ColumnRelationship, RelationshipType

logger = logging.getLogger(__name__)

# --- Total / aggregate indicator tokens ---
TOTAL_TOKENS: Set[str] = {
    "t", "total", "all", "both", "both sexes", "all races",
    "all ages", "overall", "tot",
}
TOTAL_SYMBOLS: Set[str] = {"-", "*", "~"}
TOTAL_NUMERIC: Set[str] = {"00", "000", "999"}

# --- MOE / error-bound keywords for column names ---
_MOE_KEYWORDS = {"moe", "error", "bound", "ci", "variance", "std", "margin"}


# ---------------------------------------------------------------------------
# Pairwise relationship detectors
# ---------------------------------------------------------------------------


def detect_co_referents(df: pd.DataFrame, col_a: str, col_b: str) -> bool:
    """Return True if *col_a* and *col_b* form a 1:1 bijection.

    Both directions must satisfy ``groupby(X)[Y].nunique().max() == 1``.
    Rows where either column is null are excluded. Returns False if fewer
    than 2 valid (non-null) rows remain.
    """
    subset = df[[col_a, col_b]].dropna()
    if len(subset) < 2:
        return False

    a_to_b = int(subset.groupby(col_a)[col_b].nunique().max())
    b_to_a = int(subset.groupby(col_b)[col_a].nunique().max())
    return a_to_b == 1 and b_to_a == 1


def detect_cross_products(df: pd.DataFrame, col_a: str, col_b: str) -> bool:
    """Return True if *col_a* x *col_b* covers >= 80 % of the full grid.

    Skipped when either column has fewer than 2 unique values.
    """
    unique_a = df[col_a].nunique()
    unique_b = df[col_b].nunique()
    if unique_a < 2 or unique_b < 2:
        return False

    actual = df.groupby([col_a, col_b]).ngroups
    expected = unique_a * unique_b
    return actual / expected >= 0.80


def detect_hierarchical(
    df: pd.DataFrame, child_col: str, parent_col: str
) -> bool:
    """Return True if *child_col* -> *parent_col* is many-to-one (not 1:1).

    Conditions:
      - child determines parent (each child value maps to exactly one parent)
      - parent does NOT determine child uniquely (mean children per parent > 1.1)
    """
    subset = df[[child_col, parent_col]].dropna()
    if len(subset) < 2:
        return False

    child_to_parent = int(subset.groupby(child_col)[parent_col].nunique().max())
    if child_to_parent != 1:
        return False  # child does not determine parent

    parent_to_child_mean = float(subset.groupby(parent_col)[child_col].nunique().mean())
    return parent_to_child_mean > 1.1


def detect_qualifiers(
    df: pd.DataFrame, val_col: str, qual_col: str
) -> bool:
    """Return True if *qual_col* qualifies *val_col*.

    Conditions:
      - val_col is numeric
      - qual_col is NOT numeric
      - qual_col has <= 5 unique values
    """
    val_numeric = pd.to_numeric(df[val_col], errors="coerce").notna().mean() > 0.8
    qual_numeric = pd.to_numeric(df[qual_col], errors="coerce").notna().mean() > 0.8
    if not val_numeric or qual_numeric:
        return False
    return df[qual_col].nunique() <= 5


def detect_value_error_bounds(
    df: pd.DataFrame, est_col: str, moe_col: str
) -> bool:
    """Return True if *moe_col* is a margin-of-error for *est_col*.

    Conditions:
      - Both columns are numeric
      - ``abs(moe) < abs(est)`` for >= 95 % of rows
      - *moe_col* name contains an MOE keyword
    """
    # Check name keyword first (cheap)
    moe_lower = moe_col.lower()
    if not any(kw in moe_lower for kw in _MOE_KEYWORDS):
        return False

    est = pd.to_numeric(df[est_col], errors="coerce")
    moe = pd.to_numeric(df[moe_col], errors="coerce")
    valid = est.notna() & moe.notna()
    if valid.sum() < 2:
        return False

    est_v = est[valid]
    moe_v = moe[valid]
    fraction = float((moe_v.abs() < est_v.abs()).mean())
    return fraction >= 0.95


# ---------------------------------------------------------------------------
# Composite key detection
# ---------------------------------------------------------------------------


def detect_composite_key(df: pd.DataFrame) -> List[str]:
    """Find a minimal set of columns that uniquely identifies every row.

    Excludes purely-numeric (float) columns since measure values should
    not be part of a composite key. Tries combinations of size 1 through 5.
    Returns [] if none found.
    """
    if df.empty:
        return []

    # Exclude float columns (measure values); keep int and object/string
    cols = [
        c for c in df.columns
        if not pd.api.types.is_float_dtype(df[c])
    ]
    if not cols:
        # Fallback: try all columns if no non-float columns exist
        cols = list(df.columns)

    n_rows = len(df)

    for size in range(1, min(len(cols), 5) + 1):
        for combo in itertools.combinations(cols, size):
            if df.groupby(list(combo)).ngroups == n_rows:
                return list(combo)
    return []


# ---------------------------------------------------------------------------
# Place / time format detection
# ---------------------------------------------------------------------------

_FIPS_STATE_RE = re.compile(r"^\d{2}$")
_FIPS_COUNTY_RE = re.compile(r"^\d{5}$")
_ISO2_RE = re.compile(r"^[A-Z]{2}$")
_ISO3_RE = re.compile(r"^[A-Z]{3}$")

_PLACE_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (_FIPS_STATE_RE, "fips_state", "geoId/"),
    (_FIPS_COUNTY_RE, "fips_county", "geoId/"),
    (_ISO2_RE, "iso_2", "country/"),
    (_ISO3_RE, "iso_3", "country/"),
]


def detect_place_format(series: pd.Series) -> Optional[Dict[str, Any]]:
    """Detect geographic format from a Series of values.

    Returns a dict with ``format_detected``, ``prefix_rule``, and
    ``resolution_rate``, or None if no pattern matches >= 90 % of values.
    """
    values = series.dropna().astype(str).str.strip()
    if values.empty:
        return None

    total = len(values)
    for pattern, fmt, prefix in _PLACE_PATTERNS:
        matches = values.apply(lambda v, p=pattern: bool(p.match(v))).sum()
        rate = matches / total
        if rate >= 0.90:
            return {
                "format_detected": fmt,
                "prefix_rule": prefix,
                "resolution_rate": round(rate, 4),
            }
    return None


_YYYY_RE = re.compile(r"^(1[89]\d{2}|20\d{2}|2100)$")
_YYYY_MM_RE = re.compile(r"^(1[89]\d{2}|20\d{2}|2100)-(0[1-9]|1[0-2])$")
_YYYY_MM_DD_RE = re.compile(
    r"^(1[89]\d{2}|20\d{2}|2100)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"
)

_TIME_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Check more specific formats first
    (_YYYY_MM_DD_RE, "YYYY-MM-DD"),
    (_YYYY_MM_RE, "YYYY-MM"),
    (_YYYY_RE, "YYYY"),
]


def detect_time_format(series: pd.Series) -> Optional[Dict[str, Any]]:
    """Detect temporal format from a Series.

    Returns a dict with ``format_detected`` and ``resolution_rate``,
    or None if no pattern matches >= 90 % of values.
    """
    values = series.dropna().astype(str).str.strip()
    if values.empty:
        return None

    total = len(values)
    for pattern, fmt in _TIME_PATTERNS:
        matches = values.apply(lambda v, p=pattern: bool(p.match(v))).sum()
        rate = matches / total
        if rate >= 0.90:
            return {
                "format_detected": fmt,
                "resolution_rate": round(rate, 4),
            }
    return None


# ---------------------------------------------------------------------------
# Total / aggregate indicators
# ---------------------------------------------------------------------------


def detect_total_indicators(series: pd.Series) -> List[str]:
    """Return sorted list of values that look like total / aggregate markers."""
    unique_vals = series.dropna().astype(str).unique()
    found: List[str] = []
    for raw in unique_vals:
        stripped = raw.strip()
        lower = stripped.lower()
        if lower in TOTAL_TOKENS or stripped in TOTAL_SYMBOLS or stripped in TOTAL_NUMERIC:
            found.append(stripped)
    return sorted(found)


# ---------------------------------------------------------------------------
# ColumnAnalysis dataclass
# ---------------------------------------------------------------------------


@dataclass
class ColumnAnalysis:
    """Aggregated result of all column relationship checks."""

    relationships: List[ColumnRelationship] = field(default_factory=list)
    composite_key: List[str] = field(default_factory=list)
    place_detections: List[Dict[str, Any]] = field(default_factory=list)
    time_detections: List[Dict[str, Any]] = field(default_factory=list)
    total_indicators: Dict[str, List[str]] = field(default_factory=dict)
    raw_value_profiles: Dict[str, List[str]] = field(default_factory=dict)
    co_referent_groups: List[List[str]] = field(default_factory=list)
    functional_deps: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "relationships": [r.model_dump() for r in self.relationships],
            "composite_key": self.composite_key,
            "place_detections": self.place_detections,
            "time_detections": self.time_detections,
            "total_indicators": self.total_indicators,
            "raw_value_profiles": self.raw_value_profiles,
            "co_referent_groups": self.co_referent_groups,
            "functional_deps": self.functional_deps,
        }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def analyze_columns(df: pd.DataFrame) -> ColumnAnalysis:
    """Run all column analyses and return a consolidated ``ColumnAnalysis``.

    Skips high-cardinality columns (> 100 unique values) for cross-product
    checks to avoid O(n^2) explosion.
    """
    result = ColumnAnalysis()

    if df.empty or len(df.columns) == 0:
        return result

    cols = list(df.columns)

    # --- Per-column checks ---
    for col in cols:
        # Place format
        pf = detect_place_format(df[col])
        if pf is not None:
            result.place_detections.append({"column": col, **pf})

        # Time format
        tf = detect_time_format(df[col])
        if tf is not None:
            result.time_detections.append({"column": col, **tf})

        # Total indicators
        totals = detect_total_indicators(df[col])
        if totals:
            result.total_indicators[col] = totals

        # Raw value profiles for low-cardinality columns
        if df[col].nunique() <= 50:
            result.raw_value_profiles[col] = sorted(
                df[col].dropna().astype(str).unique().tolist()
            )

    # --- Composite key ---
    result.composite_key = detect_composite_key(df)

    # --- Pairwise checks ---
    if len(cols) < 2:
        return result

    cardinalities = {c: df[c].nunique() for c in cols}

    # Track co-referent pairs for group building
    coref_pairs: List[Tuple[str, str]] = []

    for i, col_a in enumerate(cols):
        for col_b in cols[i + 1:]:
            # Co-referents
            if detect_co_referents(df, col_a, col_b):
                coref_pairs.append((col_a, col_b))
                result.relationships.append(
                    ColumnRelationship(
                        column_a=col_a,
                        column_b=col_b,
                        relationship=RelationshipType.CO_REFERENT,
                        strength=1.0,
                        evidence="1:1 bijection",
                        pvmap_implication="Use either column; they are equivalent.",
                    )
                )
                # Co-referents subsume other checks for this pair
                continue

            # Hierarchical (both directions)
            if detect_hierarchical(df, col_a, col_b):
                result.relationships.append(
                    ColumnRelationship(
                        column_a=col_a,
                        column_b=col_b,
                        relationship=RelationshipType.HIERARCHICAL,
                        strength=1.0,
                        evidence=f"{col_a} -> {col_b} many-to-one",
                        pvmap_implication=f"Use {col_a} as finer grain; {col_b} is redundant.",
                    )
                )
                result.functional_deps.append(
                    {"child": col_a, "parent": col_b}
                )
                continue
            elif detect_hierarchical(df, col_b, col_a):
                result.relationships.append(
                    ColumnRelationship(
                        column_a=col_b,
                        column_b=col_a,
                        relationship=RelationshipType.HIERARCHICAL,
                        strength=1.0,
                        evidence=f"{col_b} -> {col_a} many-to-one",
                        pvmap_implication=f"Use {col_b} as finer grain; {col_a} is redundant.",
                    )
                )
                result.functional_deps.append(
                    {"child": col_b, "parent": col_a}
                )
                continue

            # Cross product (skip high-cardinality)
            if cardinalities[col_a] <= 100 and cardinalities[col_b] <= 100:
                if detect_cross_products(df, col_a, col_b):
                    result.relationships.append(
                        ColumnRelationship(
                            column_a=col_a,
                            column_b=col_b,
                            relationship=RelationshipType.CROSS_PRODUCT,
                            strength=0.9,
                            evidence="Cartesian product >= 80% density",
                            pvmap_implication="Independent dimensions; both should map to separate properties.",
                        )
                    )

            # Qualifier (try both directions)
            if detect_qualifiers(df, col_a, col_b):
                result.relationships.append(
                    ColumnRelationship(
                        column_a=col_a,
                        column_b=col_b,
                        relationship=RelationshipType.QUALIFIER,
                        strength=0.8,
                        evidence=f"{col_b} qualifies {col_a} (<=5 unique, non-numeric)",
                        pvmap_implication=f"Map {col_b} as unit/qualifier for {col_a}.",
                    )
                )
            elif detect_qualifiers(df, col_b, col_a):
                result.relationships.append(
                    ColumnRelationship(
                        column_a=col_b,
                        column_b=col_a,
                        relationship=RelationshipType.QUALIFIER,
                        strength=0.8,
                        evidence=f"{col_a} qualifies {col_b} (<=5 unique, non-numeric)",
                        pvmap_implication=f"Map {col_a} as unit/qualifier for {col_b}.",
                    )
                )

            # Value-error bounds (try both directions)
            if detect_value_error_bounds(df, col_a, col_b):
                result.relationships.append(
                    ColumnRelationship(
                        column_a=col_a,
                        column_b=col_b,
                        relationship=RelationshipType.VALUE_ERROR_BOUND,
                        strength=0.95,
                        evidence=f"{col_b} is MOE/error for {col_a}",
                        pvmap_implication=f"Map {col_b} as margin-of-error for {col_a}.",
                    )
                )
            elif detect_value_error_bounds(df, col_b, col_a):
                result.relationships.append(
                    ColumnRelationship(
                        column_a=col_b,
                        column_b=col_a,
                        relationship=RelationshipType.VALUE_ERROR_BOUND,
                        strength=0.95,
                        evidence=f"{col_a} is MOE/error for {col_b}",
                        pvmap_implication=f"Map {col_a} as margin-of-error for {col_b}.",
                    )
                )

    # --- Build co-referent groups (union-find) ---
    result.co_referent_groups = _build_coref_groups(coref_pairs)

    return result


def _build_coref_groups(pairs: List[Tuple[str, str]]) -> List[List[str]]:
    """Union-find to merge pairwise co-referent relationships into groups."""
    if not pairs:
        return []

    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in pairs:
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        union(a, b)

    groups: Dict[str, List[str]] = {}
    for node in parent:
        root = find(node)
        groups.setdefault(root, []).append(node)

    return [sorted(g) for g in groups.values() if len(g) > 1]


# ---------------------------------------------------------------------------
# ADK Agent Wrapper
# ---------------------------------------------------------------------------

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types
import json as _json


class ColumnAnalyzerAgent(BaseAgent):
    """ADK agent that runs Phase A column analysis and stores results in state."""

    def __init__(self, name: str = "ColumnAnalyzer"):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx: InvocationContext):
        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Running Phase A column relationship analysis...")]
        ))

        sampled_data_path = ctx.session.state.get("sampled_data_path", "")
        if not sampled_data_path:
            logger.warning("No sampled_data_path in state -- skipping column analysis")
            ctx.session.state["column_analysis"] = "{}"
            yield Event(author=self.name, content=genai_types.Content(
                parts=[genai_types.Part(text="Skipped: no sampled data path")]
            ))
            return

        from pathlib import Path
        path = Path(str(sampled_data_path))
        if not path.exists():
            logger.warning("Sampled data file not found: %s", path)
            ctx.session.state["column_analysis"] = "{}"
            return

        df = pd.read_csv(path, nrows=1000, encoding="utf-8", on_bad_lines="skip", low_memory=False)
        analysis = analyze_columns(df)

        ctx.session.state["column_analysis"] = _json.dumps(analysis.to_dict(), indent=2)

        n_rels = len(analysis.relationships)
        logger.info("Column analysis complete: %d relationships, composite key: %s", n_rels, analysis.composite_key)

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text=f"Phase A complete: {n_rels} relationships, key: {analysis.composite_key}")]
        ))
