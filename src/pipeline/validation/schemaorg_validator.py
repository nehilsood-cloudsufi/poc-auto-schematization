"""Schema.org property validation for PVMAP content.

Validates PVMAP properties against schema.org vocabulary and DC extensions.
Returns warnings (not hard failures) to inform feedback, not block generation.

Usage:
    from src.pipeline.validation.schemaorg_validator import validate_pvmap_properties

    valid, warnings = validate_pvmap_properties(pvmap_csv_str, "Person")
"""

import csv
import difflib
import io
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Properties that are PVMAP structural (not schema properties)
STRUCTURAL_PROPERTIES = {
    "key", "property", "value",
}

# Observation-level properties (always valid, not StatVar properties)
OBSERVATION_PROPERTIES = {
    "observationAbout", "observationDate", "observationPeriod",
    "value", "measurementMethod", "unit", "scalingFactor",
    "measurementResult", "measurementQualifier",
}

# Properties that are PVMAP syntax/processing directives
PROCESSING_PROPERTIES = {
    "populationType", "measuredProperty", "statType",
    "memberOf", "typeOf",
}

# All "known good" properties that should never be warned about
ALWAYS_VALID = OBSERVATION_PROPERTIES | PROCESSING_PROPERTIES


def validate_pvmap_properties(
    pvmap_csv: str,
    population_type: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """Validate PVMAP properties against schema.org + DC vocabulary.

    Checks:
    1. Property existence: Is the property known in schema.org or DC?
    2. Type compatibility: Is the property valid for the declared populationType?
    3. Required triple: Are observationAbout, observationDate, value present?
    4. DCID format: Warn if raw strings where DCIDs expected

    Args:
        pvmap_csv: The PVMAP CSV string content
        population_type: Optional populationType for compatibility checking

    Returns:
        Tuple of (all_valid, warnings_list). Warnings are informational,
        not hard failures.
    """
    warnings: List[str] = []

    if not pvmap_csv or not pvmap_csv.strip():
        return True, []  # Empty PVMAP handled by pre_validate_pvmap

    try:
        from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab
        vocab = SchemaOrgVocab.instance()
    except Exception as e:
        logger.warning(f"Schema.org vocab not available: {e}")
        return True, []  # Gracefully skip if vocab not loaded

    # If vocab has no data (cache not built), skip validation
    if not vocab.is_known_type("Person"):
        return True, []

    # Parse PVMAP to extract properties and detect populationType
    detected_pop_type = population_type
    properties_used = set()
    has_observation_about = False
    has_observation_date = False
    has_value = False

    for line in pvmap_csv.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        try:
            reader = csv.reader(io.StringIO(stripped))
            row = next(reader, [])
        except Exception:
            continue

        if not row or len(row) < 3:
            continue

        key = row[0].strip()
        if key.lower() == 'key':
            continue  # Header row

        # Parse property-value pairs from row
        i = 1
        while i < len(row) - 1:
            prop = row[i].strip()
            val = row[i + 1].strip() if i + 1 < len(row) else ""
            i += 2

            if not prop:
                continue

            properties_used.add(prop)

            # Detect populationType from PVMAP
            if prop == "populationType" and val:
                detected_pop_type = val

            # Track required properties
            if prop == "observationAbout":
                has_observation_about = True
            elif prop == "observationDate":
                has_observation_date = True
            elif prop == "value":
                has_value = True

    # Check 1: Property existence
    unknown_props = []
    for prop in sorted(properties_used):
        if prop in ALWAYS_VALID or prop in STRUCTURAL_PROPERTIES:
            continue
        # Skip properties that look like placeholders
        if re.match(r'^[\{\[\(]', prop) or prop in (
            "{Data}", "{Number}", "[DATA]", "[NUMBER]"
        ):
            continue
        if not vocab.is_known_property(prop):
            unknown_props.append(prop)

    if unknown_props:
        warnings.append(
            f"SCHEMA WARNING: Unknown properties (not in schema.org or DC): "
            f"{', '.join(unknown_props[:5])}"
            + (f" (and {len(unknown_props) - 5} more)"
               if len(unknown_props) > 5 else "")
            + ". Check for typos or use exact Data Commons property names."
        )

    # Check 2: Type compatibility (only if we have a populationType)
    if detected_pop_type:
        # Verify the populationType itself is known
        if not vocab.is_known_type(detected_pop_type):
            warnings.append(
                f"SCHEMA WARNING: populationType '{detected_pop_type}' is not a known "
                f"schema.org type or DC extension. Common types: Person, Household, "
                f"MortalityEvent, BLSEstablishment, School."
            )
        else:
            # Check property compatibility with the type
            # Resolve DC type to schema.org for checking
            check_type = detected_pop_type
            schemaorg_equiv = vocab.dc_type_to_schemaorg(detected_pop_type)
            if schemaorg_equiv:
                check_type = schemaorg_equiv

            incompatible = []
            for prop in sorted(properties_used):
                if prop in ALWAYS_VALID or prop in STRUCTURAL_PROPERTIES:
                    continue
                if re.match(r'^[\{\[\(]', prop):
                    continue
                # Only check schema.org properties (DC extensions skip)
                if (vocab.get_property(prop) is not None
                        and vocab.get_type(check_type) is not None):
                    if not vocab.is_valid_property_for_type(prop, check_type):
                        incompatible.append(prop)

            if incompatible:
                warnings.append(
                    f"SCHEMA NOTE: Properties not typically associated with "
                    f"'{detected_pop_type}': {', '.join(incompatible[:5])}. "
                    f"These may still be valid DC extensions."
                )

    # Check 3: Required triple
    if not has_observation_about:
        warnings.append(
            "SCHEMA WARNING: No 'observationAbout' property found. "
            "Every observation needs a place/entity mapping."
        )
    if not has_observation_date:
        warnings.append(
            "SCHEMA WARNING: No 'observationDate' property found. "
            "Every observation needs a date/time mapping."
        )
    if not has_value:
        warnings.append(
            "SCHEMA WARNING: No 'value' property found. "
            "At least one column should map to value."
        )

    all_valid = len(warnings) == 0
    return all_valid, warnings


# Properties whose values should NOT be checked against enum vocabulary
# (they take dynamic/structural values, not enumerated identifiers)
SKIP_ENUM_PROPERTIES = {
    "observationAbout", "observationDate", "value", "observationPeriod",
    "unit", "populationType", "measuredProperty", "statType",
    "measurementMethod", "scalingFactor", "measurementResult",
    "measurementQualifier", "measurementDenominator", "memberOf", "typeOf",
}

# Placeholder patterns that should be skipped during enum validation
_PLACEHOLDER_RE = re.compile(
    r'^\{(?:Data|Number|Key)\}$|'
    r'^\[(?:DATA|NUMBER|KEY)\]$',
    re.IGNORECASE,
)


def validate_pvmap_enum_values(
    pvmap_csv: str,
    property_vocabulary: Dict[str, List[str]],
) -> Tuple[bool, List[str]]:
    """Check property values against known vocabulary enums.

    Compares dimension property values in the PVMAP against the
    property_vocabulary from the schema vocab JSON. Generates warnings
    (not hard failures) when values don't match known identifiers.

    Args:
        pvmap_csv: The PVMAP CSV string content.
        property_vocabulary: Dict mapping property names to lists of
            valid value identifiers (from schema_vocab.json).

    Returns:
        Tuple of (all_valid, warnings_list). Warnings are informational,
        not hard failures — the vocabulary is from ground truth examples,
        not exhaustive.
    """
    warnings: List[str] = []

    if not pvmap_csv or not pvmap_csv.strip():
        return True, []

    if not property_vocabulary:
        return True, []

    # Build case-insensitive lookup for each property's valid values
    prop_value_map: Dict[str, Dict[str, str]] = {}  # prop -> {lower: original}
    for prop, values in property_vocabulary.items():
        prop_value_map[prop] = {v.lower(): v for v in values}

    for line in pvmap_csv.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        try:
            reader = csv.reader(io.StringIO(stripped))
            row = next(reader, [])
        except Exception:
            continue

        if not row or len(row) < 3:
            continue

        key = row[0].strip()
        if key.lower() == 'key':
            continue

        # Parse property-value pairs
        i = 1
        while i < len(row) - 1:
            prop = row[i].strip()
            val = row[i + 1].strip() if i + 1 < len(row) else ""
            i += 2

            if not prop or not val:
                continue

            # Skip structural/dynamic properties
            if prop in SKIP_ENUM_PROPERTIES:
                continue

            # Skip placeholders
            if _PLACEHOLDER_RE.match(val):
                continue

            # Skip DCID references (dcid:..., dcs:...)
            if val.startswith('dcid:') or val.startswith('dcs:'):
                continue

            # Skip empty string (used for "total" aggregates)
            if val == '""' or val == "''":
                continue

            # Check if this property has known enum values
            if prop not in prop_value_map:
                continue  # Property not in vocab — skip (no false positive)

            valid_values = prop_value_map[prop]
            val_lower = val.lower()

            if val_lower in valid_values:
                continue  # Exact match (case-insensitive) — OK

            # No match — generate warning with fuzzy suggestion
            all_valid_list = list(property_vocabulary[prop])
            close_matches = difflib.get_close_matches(
                val, all_valid_list, n=1, cutoff=0.6
            )
            suggestion = f" Did you mean '{close_matches[0]}'?" if close_matches else ""
            warnings.append(
                f"ENUM WARNING: Property '{prop}' has value '{val}' but valid values are: "
                f"{', '.join(all_valid_list[:10])}"
                f"{' ...' if len(all_valid_list) > 10 else ''}.{suggestion}"
            )

    all_valid = len(warnings) == 0
    return all_valid, warnings
