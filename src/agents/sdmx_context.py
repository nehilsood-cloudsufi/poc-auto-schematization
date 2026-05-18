"""Render SDMX metadata into prompt context + PVMAP skeleton.

Given the dict produced by :func:`src.tools.sdmx_metadata_extractor.extract_sdmx_metadata`
this module produces:

* :func:`render_sdmx_structure` — a human-readable Markdown block to inject
  into the LLM prompt (``{{SDMX_STRUCTURE}}``).
* :func:`build_sdmx_skeleton` — a deterministic PVMAP skeleton CSV derived
  from the DSD, using the same ``key,prop,val,p1,v1`` shape as
  :func:`src.pipeline.pvmap_skeleton.skeleton_generator.generate_pvmap_skeleton`.
* :func:`classify_sdmx_columns` — utility that labels each CSV column with
  its SDMX role (observationAbout / observationDate / value / unit /
  scalingFactor / dimension / attribute).

SDMX concept IDs vary by agency, so we combine the component-kind from the
DSD (dimension/attribute/measure) with a well-known-ID heuristic.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Cardinality cap for enumerating a codelist into COLUMN:VALUE skeleton rows.
# Above this, we fall back to a passthrough row.
PASSTHROUGH_CARDINALITY_THRESHOLD = 10

# Cap per-codelist rendering so the prompt block stays bounded.
MAX_CODES_RENDERED_PER_LIST = 50

# Well-known SDMX concept IDs → Data Commons role mappings.
# Compared case-insensitively against both the component ID and the
# concept.id.
_KNOWN_PLACE_IDS = {"REF_AREA", "AREA", "COUNTRY", "GEO", "GEO_PICT"}
_KNOWN_TIME_IDS = {"TIME_PERIOD", "TIME", "PERIOD", "YEAR"}
_KNOWN_VALUE_IDS = {"OBS_VALUE", "VALUE"}
_KNOWN_UNIT_IDS = {"UNIT_MEASURE", "UNIT", "UNIT_OF_MEASURE"}
_KNOWN_SCALE_IDS = {"UNIT_MULT", "UNIT_MULTIPLIER", "SCALE"}
_KNOWN_STATUS_IDS = {"OBS_STATUS", "CONF_STATUS"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _first_dataflow(sdmx_json: dict) -> Optional[dict]:
    """Return the first dataflow in the extracted JSON, or None."""
    dfs = sdmx_json.get("dataflows") or []
    return dfs[0] if dfs else None


def _dsd(sdmx_json: dict) -> dict:
    df = _first_dataflow(sdmx_json) or {}
    return df.get("data_structure_definition") or {}


def _component_known_role(comp_id: str, concept_id: str) -> Optional[str]:
    """Return one of: observationAbout, observationDate, value, unit,
    scalingFactor, measurementQualifier — or None if not a known SDMX slot."""
    ids = {(comp_id or "").upper(), (concept_id or "").upper()}
    if ids & _KNOWN_PLACE_IDS:
        return "observationAbout"
    if ids & _KNOWN_TIME_IDS:
        return "observationDate"
    if ids & _KNOWN_VALUE_IDS:
        return "value"
    if ids & _KNOWN_UNIT_IDS:
        return "unit"
    if ids & _KNOWN_SCALE_IDS:
        return "scalingFactor"
    if ids & _KNOWN_STATUS_IDS:
        return "measurementQualifier"
    return None


def _concept_id(comp: dict) -> str:
    c = comp.get("concept") or {}
    return c.get("id", "") or ""


def _codelist(comp: dict) -> Optional[dict]:
    rep = comp.get("representation") or {}
    if rep.get("type") != "enumerated":
        return None
    return rep.get("codelist")


def _match_csv_column(comp_id: str, csv_columns: List[str]) -> Optional[str]:
    """Case-insensitive match from a DSD component ID to an actual CSV header."""
    if not csv_columns:
        return comp_id
    comp_lower = (comp_id or "").lower()
    for col in csv_columns:
        if col.lower() == comp_lower:
            return col
    return None


# ---------------------------------------------------------------------------
# Public: column classification
# ---------------------------------------------------------------------------


def classify_sdmx_columns(
    sdmx_json: dict,
    csv_columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Classify every DSD component into a role + CSV column binding.

    Returns a list of dicts with keys:
      csv_column    — matched CSV header (or the DSD id if unmatched)
      component_id  — DSD component id
      concept_id    — concept identity id
      concept_name  — human-readable concept name
      kind          — "dimension" | "attribute" | "measure"
      role          — observationAbout | observationDate | value | unit |
                      scalingFactor | measurementQualifier | dimension |
                      attribute
      codelist_id   — codelist id if enumerated, else None
      codelist_size — number of codes (0 if non-enumerated)
    """
    csv_columns = csv_columns or []
    dsd = _dsd(sdmx_json)

    rows: List[Dict[str, Any]] = []
    for kind in ("dimensions", "attributes", "measures"):
        for comp in dsd.get(kind, []) or []:
            cid = comp.get("id", "") or ""
            concept = comp.get("concept") or {}
            concept_id = concept.get("id", "") or ""
            concept_name = concept.get("name", "") or cid
            known_role = _component_known_role(cid, concept_id)
            kind_short = {"dimensions": "dimension", "attributes": "attribute", "measures": "measure"}[kind]
            if known_role is None:
                role = kind_short
            else:
                role = known_role
            cl = _codelist(comp) or {}
            rows.append(
                {
                    "csv_column": _match_csv_column(cid, csv_columns) or cid,
                    "component_id": cid,
                    "concept_id": concept_id,
                    "concept_name": concept_name,
                    "kind": kind_short,
                    "role": role,
                    "codelist_id": cl.get("id") if cl else None,
                    "codelist_size": len(cl.get("codes") or []) if cl else 0,
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Public: prompt block
# ---------------------------------------------------------------------------


def render_sdmx_structure(
    sdmx_json: dict,
    csv_columns: Optional[List[str]] = None,
) -> str:
    """Render the SDMX DSD + codelists into a Markdown block for the prompt."""
    df = _first_dataflow(sdmx_json)
    if df is None:
        return "(No SDMX dataflow found in supplied metadata.)"

    dsd = df.get("data_structure_definition") or {}
    attrs = df.get("some_attributes") or {}

    lines: List[str] = []

    # --- Dataflow identity ---
    lines.append("### Dataflow")
    lines.append(f"- id: `{df.get('id', '')}`")
    if df.get("name"):
        lines.append(f"- name: {df['name']}")
    if df.get("description"):
        lines.append(f"- description: {df['description']}")
    if attrs.get("version"):
        lines.append(f"- version: {attrs['version']}")
    if attrs.get("valid_from") or attrs.get("valid_to"):
        lines.append(
            f"- validity: {attrs.get('valid_from', '?')} → {attrs.get('valid_to', 'ongoing')}"
        )

    # --- Column reference table (DSD component → CSV column → role) ---
    classified = classify_sdmx_columns(sdmx_json, csv_columns)
    if classified:
        lines.append("")
        lines.append("### Column reference (DSD component → CSV column → DC role)")
        lines.append("| CSV column | DSD id | Concept | Kind | DC role | Codelist |")
        lines.append("|---|---|---|---|---|---|")
        for row in classified:
            cl = row["codelist_id"] or "—"
            if row["codelist_size"]:
                cl = f"{cl} ({row['codelist_size']} codes)"
            lines.append(
                f"| `{row['csv_column']}` | `{row['component_id']}` | "
                f"{row['concept_name']} | {row['kind']} | {row['role']} | {cl} |"
            )

    # --- Full component detail ---
    for kind_key, kind_label in (
        ("dimensions", "Dimensions (structural — identify each observation)"),
        ("attributes", "Attributes (qualifiers — unit, scale, status)"),
        ("measures", "Measures (the numeric value)"),
    ):
        comps = dsd.get(kind_key) or []
        if not comps:
            continue
        lines.append("")
        lines.append(f"### {kind_label}")
        for comp in comps:
            cid = comp.get("id", "")
            concept = comp.get("concept") or {}
            lines.append(f"- **`{cid}`** — {comp.get('name', '') or concept.get('name', '')}")
            if concept.get("id"):
                lines.append(
                    f"  - concept: `{concept.get('id')}` "
                    f"(scheme `{concept.get('concept_scheme_id', '?')}`)"
                )
            if comp.get("description"):
                lines.append(f"  - description: {comp['description']}")
            cl = _codelist(comp)
            if cl:
                size = len(cl.get("codes") or [])
                lines.append(f"  - codelist: `{cl.get('id')}` ({size} codes)")

    # --- Codelists (authoritative enumerations) ---
    codelists = _collect_codelists(dsd)
    if codelists:
        lines.append("")
        lines.append("### Codelists (authoritative value enumerations)")
        for cl in codelists:
            lines.append("")
            lines.append(f"**`{cl.get('id')}` — {cl.get('name', '')}**")
            codes = cl.get("codes") or []
            if len(codes) > MAX_CODES_RENDERED_PER_LIST:
                lines.append(
                    f"_Showing {MAX_CODES_RENDERED_PER_LIST} of {len(codes)} codes — "
                    "remainder resolved at PVMAP run time via passthrough._"
                )
                codes_to_show = codes[:MAX_CODES_RENDERED_PER_LIST]
            else:
                codes_to_show = codes
            for code in codes_to_show:
                code_id = code.get("id", "")
                name = code.get("name", "")
                if name:
                    lines.append(f"  - `{code_id}` = {name}")
                else:
                    lines.append(f"  - `{code_id}`")

    return "\n".join(lines).strip() + "\n"


def _collect_codelists(dsd: dict) -> List[dict]:
    """Return the unique enumerated codelists referenced across all components."""
    seen: Dict[str, dict] = {}
    for kind in ("dimensions", "attributes", "measures"):
        for comp in dsd.get(kind, []) or []:
            cl = _codelist(comp)
            if not cl:
                continue
            cid = cl.get("id")
            if cid and cid not in seen:
                seen[cid] = cl
    return list(seen.values())


# ---------------------------------------------------------------------------
# Public: deterministic skeleton
# ---------------------------------------------------------------------------


def build_sdmx_skeleton(
    sdmx_json: dict,
    csv_columns: Optional[List[str]] = None,
) -> str:
    """Build a CSV-formatted PVMAP skeleton from the DSD.

    Output matches the shape of
    :func:`src.pipeline.pvmap_skeleton.skeleton_generator.generate_pvmap_skeleton`:
    a header ``key,prop,val`` followed by rows, with extra property/value
    pairs on the value row. Empty string is returned if no components exist.
    """
    classified = classify_sdmx_columns(sdmx_json, csv_columns)
    if not classified:
        return ""

    rows: List[List[str]] = []
    value_row_extras: List[str] = []  # populationType / measuredProperty / statType

    for row in classified:
        col = row["csv_column"]
        role = row["role"]
        comp_id = row["component_id"]

        if role == "observationAbout":
            # Use {Data} — the CSV already has the ISO/FIPS/etc. code directly.
            # The LLM can upgrade this to country/{Data} or geoId/{Data:0>5}
            # once it inspects sample data to infer the format.
            rows.append([col, "observationAbout", "{Data}"])

        elif role == "observationDate":
            rows.append([col, "observationDate", "{Data}"])

        elif role == "value":
            value_row = [col, "value", "{Number}"]
            # Leave populationType + measuredProperty for the LLM — they come
            # from the measure's concept, which is agency-specific.
            value_row.extend(["populationType", "TODO"])
            value_row.extend(["measuredProperty", "TODO"])
            value_row.extend(["statType", "dcs:measuredValue"])
            rows.append(value_row)

        elif role == "unit":
            # Enumerate codelist if small; otherwise passthrough.
            _append_dim_rows(rows, col, comp_id, "unit", row, codelist=_codelist_from_classified(sdmx_json, comp_id))

        elif role == "scalingFactor":
            _append_dim_rows(rows, col, comp_id, "scalingFactor", row, codelist=_codelist_from_classified(sdmx_json, comp_id))

        elif role == "measurementQualifier":
            _append_dim_rows(rows, col, comp_id, "measurementQualifier", row, codelist=_codelist_from_classified(sdmx_json, comp_id))

        else:
            # Generic dimension / attribute. The LLM fills in the DC property
            # name; we just supply the key skeleton.
            _append_dim_rows(rows, col, comp_id, "", row, codelist=_codelist_from_classified(sdmx_json, comp_id))

    if not rows:
        return ""

    max_cols = max(len(r) for r in rows)
    max_cols = max(max_cols, 3)

    # Pad to equal width; header matches skeleton_generator.
    header = ["key", "prop", "val"]
    for i in range(1, (max_cols - 3) // 2 + 1):
        header.extend([f"p{i}", f"v{i}"])
    header = header[:max_cols]

    def _pad(r: List[str]) -> List[str]:
        return r + [""] * (max_cols - len(r))

    def _csv_line(fields: List[str]) -> str:
        out: List[str] = []
        for f in fields:
            if "," in f or '"' in f:
                out.append('"' + f.replace('"', '""') + '"')
            else:
                out.append(f)
        return ",".join(out)

    lines = [_csv_line(header)]
    for r in rows:
        lines.append(_csv_line(_pad(r)))
    return "\n".join(lines) + "\n"


def _codelist_from_classified(sdmx_json: dict, comp_id: str) -> Optional[dict]:
    dsd = _dsd(sdmx_json)
    for kind in ("dimensions", "attributes", "measures"):
        for comp in dsd.get(kind, []) or []:
            if comp.get("id") == comp_id:
                return _codelist(comp)
    return None


def _append_dim_rows(
    rows: List[List[str]],
    col: str,
    comp_id: str,
    dc_prop: str,
    classified_row: Dict[str, Any],
    codelist: Optional[dict],
) -> None:
    """Append either COLUMN:VALUE enumeration rows or a single passthrough."""
    codes = (codelist or {}).get("codes") or []
    size = len(codes)
    if codelist and size and size <= PASSTHROUGH_CARDINALITY_THRESHOLD:
        for code in codes:
            code_id = code.get("id", "")
            if not code_id:
                continue
            rows.append([f"{col}:{code_id}", dc_prop, code_id])
    else:
        rows.append([col, dc_prop, "{Data}"])


__all__ = [
    "render_sdmx_structure",
    "build_sdmx_skeleton",
    "classify_sdmx_columns",
]
