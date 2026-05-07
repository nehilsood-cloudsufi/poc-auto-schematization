"""SDMX metadata enrichment pipeline.

Adapts the three-stage enrichment approach from
tools/agentic_import/sdmx_support in the datacommonsorg/data reference repo
to run entirely via the Gemini API (no CLI subprocess).

Pipeline:
  Stage 1 — Find:  LLM reads metadata.json, selects ambiguous codes/concepts
                   and writes an enrichment_query for each.
  Stage 2 — Fetch: LLM receives the selected items and writes an
                   enriched_description (≤240 chars) for each.
  Stage 3 — Merge: CollectionMerger splices enriched_description back into
                   the original metadata dict, keyed on 'id'.

Public entry points:
  enrich_sdmx_metadata(metadata, api_key, model) -> dict
  enrich_and_save(json_path, enriched_path, api_key, model) -> dict
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CollectionMerger  (ported from metadata_enricher_merge.py — no absl deps)
# ---------------------------------------------------------------------------

DictOrList = Union[Dict[str, Any], List[Any]]


class CollectionMerger:
    """Merges selected fields from an incoming nested collection into a base one."""

    def merge(
        self,
        base: DictOrList,
        incoming: DictOrList,
        fields_to_update: List[str],
        key_field: str = "id",
        allow_overwrite: bool = False,
    ) -> DictOrList:
        return self._merge_value(
            base,
            incoming,
            fields_to_update=set(fields_to_update),
            key_field=key_field,
            allow_overwrite=allow_overwrite,
            path="",
        )

    def _merge_value(
        self,
        base: DictOrList,
        incoming: DictOrList,
        fields_to_update: Set[str],
        key_field: str,
        allow_overwrite: bool,
        path: str,
    ) -> DictOrList:
        if isinstance(base, dict) and isinstance(incoming, dict):
            return self._merge_dict(base, incoming, fields_to_update, key_field, allow_overwrite, path)
        if isinstance(base, list) and isinstance(incoming, list):
            return self._merge_list(base, incoming, fields_to_update, key_field, allow_overwrite, path)
        if type(base) != type(incoming):
            logger.debug("Type mismatch at %s; skipping.", path or "root")
        return base

    def _merge_dict(self, base, incoming, fields_to_update, key_field, allow_overwrite, path):
        for key, incoming_value in incoming.items():
            next_path = f"{path}.{key}" if path else key
            if key in fields_to_update:
                self._merge_field(base, key, incoming_value, allow_overwrite, next_path)
                continue
            if key not in base:
                continue
            base[key] = self._merge_value(base[key], incoming_value, fields_to_update, key_field, allow_overwrite, next_path)
        return base

    def _merge_list(self, base, incoming, fields_to_update, key_field, allow_overwrite, path):
        base_by_key: Dict[Any, Dict] = {}
        for i, item in enumerate(base):
            if not isinstance(item, dict):
                continue
            kv = item.get(key_field)
            if kv is None or kv in base_by_key:
                continue
            base_by_key[kv] = item

        for item in incoming:
            if not isinstance(item, dict):
                continue
            kv = item.get(key_field)
            if kv is None:
                continue
            base_item = base_by_key.get(kv)
            if base_item is None:
                continue
            self._merge_dict(base_item, item, fields_to_update, key_field, allow_overwrite,
                             f"{path}[{key_field}={kv}]")
        return base

    def _merge_field(self, base, key, incoming_value, allow_overwrite, path):
        if key not in base:
            base[key] = incoming_value
            return
        if allow_overwrite:
            base[key] = incoming_value
        # else: preserve existing value silently


# ---------------------------------------------------------------------------
# Gemini API helper
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    """Single-shot Gemini call; returns the text of the first candidate."""
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return response.text


def _parse_json_response(raw: str, stage: str) -> Optional[dict]:
    """Extract JSON from a Gemini response, stripping markdown fences."""
    text = raw.strip()
    # Strip ```json ... ``` fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Stage %s: could not parse JSON response: %s", stage, e)
        logger.debug("Raw response snippet: %.300s", raw)
        return None


# ---------------------------------------------------------------------------
# Stage 1 — Find items to enrich
# ---------------------------------------------------------------------------

_FIND_PROMPT = """\
You are analyzing SDMX metadata to select codes and concepts that would benefit
from a plain-English enriched description. An enriched description helps a data
scientist map SDMX dimensions to Data Commons statistical variables.

## Input metadata (JSON)
```json
{metadata_json}
```

## Task
1. Review every code in every codelist and every concept in every concept scheme.
2. Select items where the existing name or description is:
   - Absent or empty
   - A single letter or short abbreviation (e.g. "A", "G", "IND_TYPE")
   - A numeric code with no obvious meaning (e.g. "6", "1000")
   - Domain-specific jargon that a general data scientist would not recognise
3. For each selected item, write an `enrichment_query`: a precise web-search
   query (10–20 words) that would return a clear statistical definition.
4. Limit to the 60 most important items (prefer dimension codes over attribute codes).

## Output format
Return a PRUNED version of the input JSON, preserving the exact same nesting
structure but containing ONLY the selected items. Add `"enrichment_query"` to
each selected code or concept object.

Output valid JSON only — no commentary, no markdown fences.
"""

_FETCH_PROMPT = """\
You are enriching SDMX metadata codes and concepts with concise, accurate
plain-English descriptions for use in Data Commons statistical variable mapping.

## Items to enrich (JSON)
```json
{items_json}
```

## Task
For every object that has an `"enrichment_query"` field:
1. Use your knowledge to answer the query and write an `"enriched_description"`:
   - Maximum 240 characters
   - Plain English, factual, specific to the statistical domain
   - Example: "Gross value added, seasonally adjusted, at market prices, millions USD"
2. Remove the `"enrichment_query"` field and replace it with `"enriched_description"`.
3. Preserve all other existing fields unchanged.

## Output format
Return the same JSON structure with `"enriched_description"` populated.
Output valid JSON only — no commentary, no markdown fences.
"""


def find_items_to_enrich(metadata: dict, api_key: str, model: str) -> Optional[dict]:
    """Stage 1: ask Gemini which codes/concepts need enrichment."""
    metadata_json = json.dumps(metadata, indent=2)
    # Cap to avoid exceeding context — truncate very large metadata
    if len(metadata_json) > 120_000:
        logger.warning(
            "SDMX metadata JSON is large (%d chars); truncating before enrichment-find call.",
            len(metadata_json),
        )
        metadata_json = metadata_json[:120_000] + "\n... (truncated)"

    prompt = _FIND_PROMPT.replace("{metadata_json}", metadata_json)
    logger.info("SDMX enrichment Stage 1 (find): calling Gemini model=%s", model)
    try:
        raw = _call_gemini(prompt, api_key, model)
        result = _parse_json_response(raw, "find")
        if result:
            total = _count_items_with_field(result, "enrichment_query")
            logger.info("Stage 1 complete: %d items selected for enrichment.", total)
        return result
    except Exception as e:
        logger.warning("Stage 1 (find) failed: %s", e)
        return None


def fetch_enriched_descriptions(items: dict, api_key: str, model: str) -> Optional[dict]:
    """Stage 2: ask Gemini to write enriched_description for each selected item."""
    items_json = json.dumps(items, indent=2)
    prompt = _FETCH_PROMPT.replace("{items_json}", items_json)
    logger.info("SDMX enrichment Stage 2 (fetch): calling Gemini model=%s", model)
    try:
        raw = _call_gemini(prompt, api_key, model)
        result = _parse_json_response(raw, "fetch")
        if result:
            total = _count_items_with_field(result, "enriched_description")
            logger.info("Stage 2 complete: %d enriched_description fields written.", total)
        return result
    except Exception as e:
        logger.warning("Stage 2 (fetch) failed: %s", e)
        return None


def _count_items_with_field(obj: Any, field: str) -> int:
    """Recursively count objects that have a given field."""
    count = 0
    if isinstance(obj, dict):
        if field in obj:
            count += 1
        for v in obj.values():
            count += _count_items_with_field(v, field)
    elif isinstance(obj, list):
        for item in obj:
            count += _count_items_with_field(item, field)
    return count


# ---------------------------------------------------------------------------
# Stage 3 — Merge
# ---------------------------------------------------------------------------

def merge_enrichment(base_metadata: dict, enriched_items: dict) -> dict:
    """Stage 3: merge enriched_description fields back into the full metadata."""
    import copy
    result = copy.deepcopy(base_metadata)
    merger = CollectionMerger()
    merger.merge(
        result,
        enriched_items,
        fields_to_update=["enriched_description"],
        key_field="id",
        allow_overwrite=False,
    )
    enriched_count = _count_items_with_field(result, "enriched_description")
    logger.info("Stage 3 complete: %d enriched_description fields merged into metadata.", enriched_count)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_sdmx_metadata(
    metadata: dict,
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> dict:
    """Run all three enrichment stages and return the enriched metadata dict.

    Falls back to the original metadata if any stage fails.
    """
    # Stage 1
    items_to_enrich = find_items_to_enrich(metadata, api_key, model)
    if not items_to_enrich:
        logger.warning("Enrichment Stage 1 returned nothing; skipping enrichment.")
        return metadata

    # Stage 2
    enriched_items = fetch_enriched_descriptions(items_to_enrich, api_key, model)
    if not enriched_items:
        logger.warning("Enrichment Stage 2 returned nothing; skipping enrichment.")
        return metadata

    # Stage 3
    return merge_enrichment(metadata, enriched_items)


def enrich_and_save(
    metadata_json_path: Path,
    enriched_json_path: Path,
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> dict:
    """Load metadata.json, enrich it, save to enriched_json_path, return dict."""
    metadata = json.loads(Path(metadata_json_path).read_text())
    enriched = enrich_sdmx_metadata(metadata, api_key, model)
    Path(enriched_json_path).write_text(json.dumps(enriched, indent=2))
    logger.info("Enriched SDMX metadata saved to %s", enriched_json_path)
    return enriched


__all__ = [
    "enrich_sdmx_metadata",
    "enrich_and_save",
    "CollectionMerger",
    "find_items_to_enrich",
    "fetch_enriched_descriptions",
    "merge_enrichment",
]
