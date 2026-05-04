#!/usr/bin/env python3
"""
Build compressed schema vocabulary JSON files from .txt schema examples.

Parses each .txt file in src/resources/schema_examples/{Category}/ and produces
a compact JSON vocab that groups properties by populationType (StatVar skeletons),
extracts unique property→value sets, and selects diverse representative examples.

Usage:
    python tools/build_schema_vocab.py
    python tools/build_schema_vocab.py --category=Health
    python tools/build_schema_vocab.py --dry-run
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Project root
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SCHEMA_BASE_DIR = PROJECT_ROOT / "src" / "resources" / "schema_examples"

# Add project root for SchemaOrgVocab import
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Categories with .txt files (School has no .txt)
CATEGORIES = ["Demographics", "Economy", "Education", "Employment", "Energy", "Health"]

# Category to primary schema.org type mapping
CATEGORY_SCHEMAORG_TYPES = {
    "Demographics": "Person",
    "Economy": "Organization",
    "Education": "EducationalOrganization",
    "Employment": "Person",
    "Energy": "Place",
    "Health": "Person",
}

# WHO opaque IDs to filter out — these are magic numbers the LLM can't reason about
WHO_OPAQUE_PATTERN = re.compile(r"^who/[A-Z0-9_]+$")
SDG_OPAQUE_PATTERN = re.compile(r"^SDG_[A-Z0-9_]+$")
WORLD_BANK_PATTERN = re.compile(r"^worldBank/[A-Z0-9_]+$")


def is_opaque_id(value: str) -> bool:
    """Check if a value is an opaque identifier that LLMs can't reason about."""
    return bool(
        WHO_OPAQUE_PATTERN.match(value)
        or SDG_OPAQUE_PATTERN.match(value)
        or WORLD_BANK_PATTERN.match(value)
    )


def parse_schema_line(line: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """
    Parse a single schema example line.

    Format: "Human Readable Name --> property1:value1, property2:value2"
    Also handles "->" delimiter.

    Returns:
        Tuple of (label, {property: value}) or None if line is invalid/empty.
    """
    line = line.strip()
    if not line:
        return None

    # Try --> first, then ->
    if " --> " in line:
        parts = line.split(" --> ", 1)
    elif " -> " in line:
        parts = line.split(" -> ", 1)
    else:
        return None

    label = parts[0].strip()
    rhs = parts[1].strip() if len(parts) > 1 else ""

    if not label:
        return None

    # Skip empty RHS (these are section headers or incomplete entries)
    if not rhs:
        return None

    # Skip displayRank metadata lines
    if rhs.startswith("displayRank:"):
        return None

    # Parse property:value pairs
    props = {}
    for pair in rhs.split(", "):
        pair = pair.strip()
        if ":" in pair:
            key, value = pair.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                props[key] = value

    if not props:
        return None

    return label, props


def build_vocab_for_category(category: str) -> Optional[dict]:
    """
    Build compressed vocabulary JSON for a single category.

    Returns:
        Vocab dict or None if .txt file not found.
    """
    txt_file = (
        SCHEMA_BASE_DIR
        / category
        / f"scripts_statvar_llm_config_schema_examples_dc_topic_{category}.txt"
    )

    if not txt_file.exists():
        print(f"  WARNING: No .txt file for {category}: {txt_file}")
        return None

    # Parse all lines
    entries = []
    with open(txt_file, "r", encoding="utf-8") as f:
        for line in f:
            parsed = parse_schema_line(line)
            if parsed:
                entries.append(parsed)

    if not entries:
        print(f"  WARNING: No valid entries parsed from {category}")
        return None

    print(f"  Parsed {len(entries)} entries from {txt_file.name}")

    # Build StatVar skeletons: group property sets by populationType
    skeletons: Dict[str, Set[str]] = defaultdict(set)
    # Build property vocabulary: property -> set of unique values
    property_vocab: Dict[str, Set[str]] = defaultdict(set)
    # Track entries by skeleton for example selection
    entries_by_skeleton: Dict[str, List[Tuple[str, Dict[str, str]]]] = defaultdict(list)

    for label, props in entries:
        pop_type = props.get("populationType", "Person")
        # Collect all non-populationType properties for this skeleton
        prop_keys = set()
        for key, value in props.items():
            if key == "populationType":
                continue
            prop_keys.add(key)
            # Filter opaque IDs from vocabulary values
            if not is_opaque_id(value):
                property_vocab[key].add(value)

        skeletons[pop_type].update(prop_keys)
        entries_by_skeleton[pop_type].append((label, props))

    # Convert skeletons to sorted lists
    stat_var_skeletons = {}
    for pop_type, props in sorted(skeletons.items()):
        stat_var_skeletons[pop_type] = sorted(props)

    # Convert property vocab to sorted lists, limit to 15 values per property
    property_vocabulary = {}
    for prop, values in sorted(property_vocab.items()):
        sorted_vals = sorted(values)
        if len(sorted_vals) > 15:
            # Keep first 12 + last 3 to show range
            sorted_vals = sorted_vals[:12] + sorted_vals[-3:]
        property_vocabulary[prop] = sorted_vals

    # Select diverse examples: one per skeleton pattern, preferring shorter/clearer ones
    examples = _select_diverse_examples(entries_by_skeleton, max_examples=10)

    vocab = {
        "category": category,
        "stat_var_skeletons": stat_var_skeletons,
        "property_vocabulary": property_vocabulary,
        "examples": examples,
    }

    return vocab


def _select_diverse_examples(
    entries_by_skeleton: Dict[str, List[Tuple[str, Dict[str, str]]]],
    max_examples: int = 10,
) -> List[dict]:
    """
    Select diverse examples covering different StatVar skeletons and property patterns.

    Strategy:
    - Distribute examples across skeletons proportionally
    - Within each skeleton, pick entries with different property combinations
    - Prefer shorter labels (clearer)
    - Prefer entries WITHOUT opaque IDs
    """
    examples = []
    used_prop_sets = set()

    # Sort skeletons by frequency (most common first) for representative coverage
    skeleton_order = sorted(
        entries_by_skeleton.keys(),
        key=lambda k: len(entries_by_skeleton[k]),
        reverse=True,
    )

    # Calculate examples per skeleton (at least 1, distribute proportionally)
    total_entries = sum(len(v) for v in entries_by_skeleton.values())
    examples_budget = {}
    remaining = max_examples
    for pop_type in skeleton_order:
        share = max(1, round(max_examples * len(entries_by_skeleton[pop_type]) / total_entries))
        examples_budget[pop_type] = min(share, remaining)
        remaining -= examples_budget[pop_type]
        if remaining <= 0:
            break

    for pop_type in skeleton_order:
        budget = examples_budget.get(pop_type, 0)
        if budget <= 0 or len(examples) >= max_examples:
            break

        candidates = entries_by_skeleton[pop_type]

        # Filter out entries with opaque IDs
        clean_candidates = [
            (label, props)
            for label, props in candidates
            if not any(is_opaque_id(v) for v in props.values())
        ]

        # Fallback to all candidates if no clean ones
        if not clean_candidates:
            clean_candidates = candidates[:5]

        # Sort by label length (prefer shorter, clearer examples)
        clean_candidates.sort(key=lambda x: len(x[0]))

        picked = 0
        for label, props in clean_candidates:
            if picked >= budget or len(examples) >= max_examples:
                break

            # Create a property signature to avoid duplicate patterns
            prop_sig = frozenset(
                k for k in props.keys() if k != "populationType"
            )
            if prop_sig in used_prop_sets:
                continue

            used_prop_sets.add(prop_sig)

            # Format as compact mapping string
            mapping_parts = []
            for k, v in sorted(props.items()):
                mapping_parts.append(f"{k}:{v}")

            examples.append(
                {
                    "label": label,
                    "mapping": ", ".join(mapping_parts),
                }
            )
            picked += 1

    return examples


def enrich_with_schemaorg(vocab: dict) -> dict:
    """Add schema_org section to vocab dict.

    Adds schema.org context: primary type, hierarchy, relevant properties,
    and DC-only extensions. Keeps the section under 2KB.
    """
    category = vocab.get("category", "")
    primary_type = CATEGORY_SCHEMAORG_TYPES.get(category)
    if not primary_type:
        return vocab

    try:
        from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab
        sov = SchemaOrgVocab.instance()

        hierarchy = sov.get_type_hierarchy(primary_type) or []

        # Get schema.org properties for this type (with inheritance)
        all_props = sov.get_properties_for_type(primary_type, inherited=True) or []

        # Filter to relevant properties (properties that are also in the vocab's skeletons)
        skeleton_props = set()
        for pop_type_props in vocab.get("stat_var_skeletons", {}).values():
            skeleton_props.update(pop_type_props)

        # Schema.org properties that appear in the vocab
        relevant_schemaorg_props = {}
        for prop_name in all_props:
            if prop_name.lower() in {p.lower() for p in skeleton_props}:
                prop_info = sov.get_property(prop_name)
                if prop_info:
                    relevant_schemaorg_props[prop_name] = {
                        "range": prop_info.get("range", [])[:3],  # Limit range entries
                        "desc": prop_info.get("description", "")[:100],
                    }

        # DC-only properties (in vocab but not in schema.org)
        dc_only = []
        for prop_name in sorted(skeleton_props):
            if not sov.get_property(prop_name) and sov.is_known_dc_property(prop_name):
                dc_only.append(prop_name)

        schema_org_section = {
            "primary_type": primary_type,
            "type_hierarchy": [primary_type] + hierarchy[:3],  # Limit depth
            "schemaorg_properties": relevant_schemaorg_props,
            "dc_only_properties": dc_only,
        }

        vocab["schema_org"] = schema_org_section

    except Exception as e:
        print(f"  WARNING: Could not enrich with schema.org: {e}")

    return vocab


def enrich_with_statvar_examples(vocab, category_statvars, max_examples=15):
    """Add real StatVar decomposition examples to vocab."""
    seen_pop_types = {}
    selected = []
    for sv in category_statvars:
        pop = sv.get("populationType", "")
        if seen_pop_types.get(pop, 0) >= 5:
            continue
        seen_pop_types[pop] = seen_pop_types.get(pop, 0) + 1
        example = {k: v for k, v in sv.items() if k != "statType"}
        selected.append(example)
        if len(selected) >= max_examples:
            break
    vocab["statvar_examples"] = selected
    return vocab


def write_vocab_file(category: str, vocab: dict, dry_run: bool = False) -> Path:
    """Write vocab JSON to schema_vocab.json in the category directory."""
    output_path = SCHEMA_BASE_DIR / category / "schema_vocab.json"

    if dry_run:
        size_kb = len(json.dumps(vocab, indent=2)) / 1024
        print(f"  DRY RUN: Would write {output_path.name} ({size_kb:.1f} KB)")
        return output_path

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, indent=2)

    size_kb = output_path.stat().st_size / 1024
    print(f"  Wrote {output_path.name} ({size_kb:.1f} KB)")
    return output_path


def main():
    """Build schema vocab files for all categories."""
    import argparse

    parser = argparse.ArgumentParser(description="Build compressed schema vocabulary JSON files")
    parser.add_argument("--category", type=str, default=None,
                        help="Build vocab for a specific category only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without writing files")
    args = parser.parse_args()

    categories = [args.category] if args.category else CATEGORIES

    print(f"Building schema vocab files...")
    print(f"Schema base dir: {SCHEMA_BASE_DIR}")
    print()

    mcf_path = Path("src/resources/schema_org/sample_statvars.mcf")
    statvar_groups = {}
    if mcf_path.exists():
        from tools.parse_statvar_mcf import parse_mcf_file, group_by_category
        all_statvars = parse_mcf_file(mcf_path)
        statvar_groups = group_by_category(all_statvars)
        print(f"Parsed {len(all_statvars)} StatVars into {len(statvar_groups)} categories")
    print()

    results = {}
    for category in categories:
        print(f"Processing {category}...")
        vocab = build_vocab_for_category(category)
        if vocab:
            vocab = enrich_with_schemaorg(vocab)
            if category in statvar_groups:
                vocab = enrich_with_statvar_examples(vocab, statvar_groups[category])
                print(f"  Added {len(vocab.get('statvar_examples', []))} StatVar examples")
            output_path = write_vocab_file(category, vocab, dry_run=args.dry_run)
            results[category] = {
                "skeletons": len(vocab["stat_var_skeletons"]),
                "properties": len(vocab["property_vocabulary"]),
                "examples": len(vocab["examples"]),
                "path": str(output_path),
            }
        else:
            results[category] = None
        print()

    # Summary
    print("=" * 60)
    print("Summary:")
    for category, info in results.items():
        if info:
            print(
                f"  {category}: {info['skeletons']} skeletons, "
                f"{info['properties']} properties, "
                f"{info['examples']} examples"
            )
        else:
            print(f"  {category}: SKIPPED (no .txt file or no entries)")


if __name__ == "__main__":
    main()
