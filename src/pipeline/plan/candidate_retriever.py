"""Retrieve grounding candidates per column from Schema.org and schema vocab.

This is a pure programmatic component (no LLM) that runs before the plan agent
to provide initial property/value candidates for each column based on heuristic
role assignment and vocabulary lookup.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from src.api.models.plan import CandidateSource, ColumnRole, PropertyValueCandidate
from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

logger = logging.getLogger(__name__)

# Semantic types classified as place identifiers
_PLACE_SEMANTIC_TYPES = {
    "fips_state", "fips_county", "iso_2", "iso_3", "country_name",
    "us_state_name", "us_state_abbrev", "geoid", "place",
}

# Semantic types classified as date identifiers
_DATE_SEMANTIC_TYPES = {
    "yyyy", "yyyy-mm", "yyyy-mm-dd", "yyyymm", "yyyymmdd",
    "date", "year", "quarter", "month",
}

# Hardcoded candidates for well-known roles
_PLACE_CANDIDATES = [
    PropertyValueCandidate(
        property="observationAbout",
        value_expression="{place_column}",
        confidence=0.95,
        source=CandidateSource.SCHEMA_ORG,
        reason="Column identified as place/geography by profiler",
    ),
]

_DATE_CANDIDATES = [
    PropertyValueCandidate(
        property="observationDate",
        value_expression="{date_column}",
        confidence=0.95,
        source=CandidateSource.SCHEMA_ORG,
        reason="Column identified as date/time by profiler",
    ),
]

_MEASURE_CANDIDATES = [
    PropertyValueCandidate(
        property="value",
        value_expression="{value_column}",
        confidence=0.85,
        source=CandidateSource.SCHEMA_ORG,
        reason="High-cardinality numeric column likely holds observed values",
    ),
]


def _tokenize(name: str) -> List[str]:
    """Split a column name into lowercase word tokens.

    Handles camelCase, snake_case, and separator-based names.
    """
    # Insert space before uppercase letters in camelCase
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    # Replace common separators with spaces
    spaced = re.sub(r"[_\-.:/ ]+", " ", spaced)
    return [tok.lower() for tok in spaced.split() if tok]


class CandidateRetriever:
    """Retrieve grounding candidates for columns from Schema.org + schema vocab."""

    def __init__(self) -> None:
        self._schema_org = SchemaOrgVocab.instance()

    # ------------------------------------------------------------------
    # Role assignment
    # ------------------------------------------------------------------

    def _assign_role(self, col: dict) -> ColumnRole:
        """Heuristic role assignment based on column profile dict.

        Args:
            col: Column profile dict (from ColumnProfile.to_dict() / DatasetProfile).

        Returns:
            A ColumnRole enum value.
        """
        semantic_type = (col.get("semantic_type") or "").lower()
        dtype = col.get("dtype", "")
        cardinality = col.get("cardinality", 0)
        cardinality_ratio = col.get("cardinality_ratio", 0.0)
        looks_like_place = col.get("looks_like_place", False)
        looks_like_date = col.get("looks_like_date", False)

        # Place detection
        if semantic_type in _PLACE_SEMANTIC_TYPES or looks_like_place:
            return ColumnRole.OBSERVATION_ABOUT

        # Date detection
        if semantic_type in _DATE_SEMANTIC_TYPES or looks_like_date:
            return ColumnRole.OBSERVATION_DATE

        # Ignored: empty or constant columns
        if cardinality == 0 or dtype == "Empty":
            return ColumnRole.IGNORED
        if cardinality == 1:
            return ColumnRole.IGNORED

        # Measure: high-cardinality numeric
        if dtype in ("Float", "Integer") and cardinality_ratio > 0.3:
            return ColumnRole.MEASURE

        # Default: dimension
        return ColumnRole.DIMENSION

    # ------------------------------------------------------------------
    # Schema.org candidates
    # ------------------------------------------------------------------

    def _get_schemaorg_candidates(self, col: dict) -> List[PropertyValueCandidate]:
        """Retrieve candidates from Schema.org vocabulary.

        For well-known semantic types (place, date, measure), returns hardcoded
        high-confidence candidates. Otherwise searches Schema.org by column name.

        Args:
            col: Column profile dict.

        Returns:
            List of PropertyValueCandidate objects.
        """
        semantic_type = (col.get("semantic_type") or "").lower()
        looks_like_place = col.get("looks_like_place", False)
        looks_like_date = col.get("looks_like_date", False)
        dtype = col.get("dtype", "")
        cardinality_ratio = col.get("cardinality_ratio", 0.0)

        # Known place
        if semantic_type in _PLACE_SEMANTIC_TYPES or looks_like_place:
            return list(_PLACE_CANDIDATES)

        # Known date
        if semantic_type in _DATE_SEMANTIC_TYPES or looks_like_date:
            return list(_DATE_CANDIDATES)

        # Known measure
        if dtype in ("Float", "Integer") and cardinality_ratio > 0.3:
            return list(_MEASURE_CANDIDATES)

        # Unknown: search Schema.org by column name
        col_name = col.get("name", "")
        if not col_name:
            return []

        results = self._schema_org.search_properties(col_name, limit=3)
        candidates = []
        for hit in results:
            prop_name = hit.get("name", "")
            desc = hit.get("description", "")
            candidates.append(
                PropertyValueCandidate(
                    property=prop_name,
                    value_expression=f"{{{col_name}}}",
                    confidence=0.50,
                    source=CandidateSource.SCHEMA_ORG,
                    reason=f"Schema.org match: {desc[:80]}" if desc else f"Schema.org property: {prop_name}",
                )
            )
        return candidates

    # ------------------------------------------------------------------
    # Schema vocab candidates
    # ------------------------------------------------------------------

    def _get_vocab_candidates(
        self, col: dict, schema_vocab: str
    ) -> List[PropertyValueCandidate]:
        """Retrieve candidates from schema vocab JSON.

        Parses the vocab JSON and fuzzy-matches column name tokens against
        property names in the vocabulary.

        Args:
            col: Column profile dict.
            schema_vocab: Raw JSON string of a schema_vocab.json file.

        Returns:
            List of PropertyValueCandidate objects.
        """
        if not schema_vocab:
            return []

        try:
            vocab = json.loads(schema_vocab)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse schema_vocab JSON")
            return []

        # Extract property names from stat_var_skeletons
        properties: List[str] = []
        skeletons = vocab.get("stat_var_skeletons", {})
        for prop_list in skeletons.values():
            for prop in prop_list:
                if prop not in properties:
                    properties.append(prop)

        # Also include properties from property_vocabulary keys
        prop_vocab = vocab.get("property_vocabulary", {})
        for prop in prop_vocab:
            if prop not in properties:
                properties.append(prop)

        if not properties:
            return []

        col_name = col.get("name", "")
        col_tokens = set(_tokenize(col_name))

        if not col_tokens:
            return []

        candidates = []
        for prop in properties:
            prop_tokens = set(_tokenize(prop))
            if not prop_tokens:
                continue

            overlap = col_tokens & prop_tokens
            if not overlap:
                continue

            confidence = min(0.40 + 0.15 * len(overlap), 0.80)

            # Build value expression from property_vocabulary if available
            vocab_values = prop_vocab.get(prop, [])
            if vocab_values:
                value_expr = f"dcid:{vocab_values[0]}"
            else:
                value_expr = f"{{{col_name}}}"

            candidates.append(
                PropertyValueCandidate(
                    property=prop,
                    value_expression=value_expr,
                    confidence=round(confidence, 2),
                    source=CandidateSource.SCHEMA_VOCAB,
                    reason=f"Vocab match: {len(overlap)} word overlap ({', '.join(sorted(overlap))})",
                )
            )

        # Sort by confidence descending
        candidates.sort(key=lambda c: -c.confidence)
        return candidates

    # ------------------------------------------------------------------
    # Merge + dedup
    # ------------------------------------------------------------------

    def _merge_candidates(
        self, candidates: List[PropertyValueCandidate]
    ) -> List[PropertyValueCandidate]:
        """Merge and deduplicate candidates from multiple sources.

        When the same property appears from multiple sources, keeps the one
        with the highest confidence. If confidence is tied, prefers the most
        specific value_expression (the one without generic `{column}` pattern).

        Args:
            candidates: Combined list of candidates from all sources.

        Returns:
            Deduplicated list sorted by confidence descending.
        """
        best: Dict[str, PropertyValueCandidate] = {}
        for cand in candidates:
            key = cand.property
            if key not in best:
                best[key] = cand
            else:
                existing = best[key]
                if cand.confidence > existing.confidence:
                    best[key] = cand
                elif cand.confidence == existing.confidence:
                    # Prefer more specific value_expression (not a bare {column} template)
                    existing_is_generic = existing.value_expression.startswith("{") and existing.value_expression.endswith("}")
                    cand_is_generic = cand.value_expression.startswith("{") and cand.value_expression.endswith("}")
                    if existing_is_generic and not cand_is_generic:
                        best[key] = cand

        merged = list(best.values())
        merged.sort(key=lambda c: -c.confidence)
        return merged

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve_for_column(
        self, col: dict, schema_vocab: str = ""
    ) -> Tuple[ColumnRole, List[PropertyValueCandidate], str]:
        """Retrieve role and candidates for a single column.

        Args:
            col: Column profile dict.
            schema_vocab: Raw JSON string of schema_vocab.json (may be empty).

        Returns:
            Tuple of (role, merged_candidates, evidence_summary).
        """
        role = self._assign_role(col)

        # Gather candidates from all sources
        schema_org_cands = self._get_schemaorg_candidates(col)
        vocab_cands = self._get_vocab_candidates(col, schema_vocab)
        all_cands = schema_org_cands + vocab_cands

        merged = self._merge_candidates(all_cands)

        # Build evidence summary
        col_name = col.get("name", "unknown")
        parts = [f"role={role.value}"]
        if schema_org_cands:
            parts.append(f"{len(schema_org_cands)} Schema.org candidate(s)")
        if vocab_cands:
            parts.append(f"{len(vocab_cands)} vocab candidate(s)")
        evidence = f"[{col_name}] {', '.join(parts)}"

        return role, merged, evidence

    def retrieve_all(
        self, columns: Dict[str, dict], schema_vocab: str = ""
    ) -> Dict[str, Tuple[ColumnRole, List[PropertyValueCandidate], str]]:
        """Retrieve roles and candidates for all columns.

        Args:
            columns: Dict mapping column name to column profile dict.
            schema_vocab: Raw JSON string of schema_vocab.json (may be empty).

        Returns:
            Dict mapping column name to (role, candidates, evidence) tuple.
        """
        results = {}
        for col_name, col_dict in columns.items():
            results[col_name] = self.retrieve_for_column(col_dict, schema_vocab)
        return results


# --- ADK Agent Wrapper ---
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types


class CandidateRetrieverAgent(BaseAgent):
    """ADK agent wrapper for CandidateRetriever. Runs before MappingPlanAgent."""

    def __init__(self, name: str = "CandidateRetriever"):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx: InvocationContext):
        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Retrieving grounding candidates per column...")]
        ))

        retriever = CandidateRetriever()

        # Parse column profiles from skeleton_summary
        skeleton = ctx.session.state.get("skeleton_summary", "")
        columns = _parse_columns_from_skeleton(skeleton)

        schema_vocab = ctx.session.state.get("schema_vocab_content", "")

        results = retriever.retrieve_all(columns, schema_vocab)

        # Format as JSON for the plan agent
        import json as _json
        pool = {}
        for col_name, (role, candidates, evidence) in results.items():
            pool[col_name] = {
                "proposed_role": role.value,
                "evidence": evidence,
                "candidates": [c.model_dump() for c in candidates],
            }

        ctx.session.state["candidate_pool"] = _json.dumps(pool, indent=2)
        logger.info("Candidate retrieval complete: %d columns, %d total candidates",
                    len(pool), sum(len(v["candidates"]) for v in pool.values()))

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text=f"Retrieved candidates for {len(pool)} columns")]
        ))


def _parse_columns_from_skeleton(skeleton: str) -> dict:
    """Parse column info from skeleton_summary markdown table into dict format for retrieve_all.

    The skeleton has a markdown table like:
    | Column | Type | Unique | ...
    Returns dict keyed by column name with profile info.
    """
    columns = {}
    in_table = False
    for line in skeleton.split("\n"):
        if "|" not in line:
            if in_table:
                break  # End of first table — stop parsing
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if not cells:
            continue
        if cells[0] == "Column" or cells[0] == "Column Header (EXACT)":
            if in_table:
                break  # Hit a second table header — stop
            in_table = True
            continue
        if cells[0].startswith("---"):
            # Separator row — skip but don't change in_table state
            continue
        if not in_table:
            continue
        if len(cells) >= 2:
            name = cells[0].strip("`")
            dtype = cells[1] if len(cells) > 1 else "String"
            cardinality = 0
            if len(cells) > 2:
                try:
                    cardinality = int(cells[2])
                except ValueError:
                    pass

            # Detect semantic type
            semantic = cells[3] if len(cells) > 3 and cells[3] != "-" else None
            sem_type = None
            if semantic:
                sem_lower = semantic.lower()
                if any(k in sem_lower for k in ["place", "geo", "country", "state", "fips", "iso"]):
                    sem_type = "place"
                elif any(k in sem_lower for k in ["date", "year", "time", "period"]):
                    sem_type = "date"

            # Use cardinality to estimate ratio: low cardinality (<=20 unique)
            # suggests a categorical column even if the dtype is numeric.
            if sem_type:
                cardinality_ratio = 0.05  # semantic type detected — likely dimension
            elif dtype in ("Float", "Integer") and cardinality > 20:
                cardinality_ratio = 0.5  # likely continuous measure
            elif dtype in ("Float", "Integer") and cardinality > 0:
                cardinality_ratio = 0.05  # low-cardinality numeric — likely coded dimension
            else:
                cardinality_ratio = 0.5 if dtype in ("Float", "Integer") else 0.05
            samples = cells[4].split(", ")[:3] if len(cells) > 4 else []

            columns[name] = {
                "name": name,
                "dtype": dtype,
                "semantic_type": sem_type,
                "cardinality": cardinality,
                "cardinality_ratio": cardinality_ratio,
                "sample_values": samples,
            }

    return columns
