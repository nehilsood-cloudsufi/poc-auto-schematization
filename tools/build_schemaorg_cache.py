#!/usr/bin/env python3
"""
Build local schema.org vocabulary cache from the official JSON-LD release.

Downloads the latest schema.org JSON-LD and extracts:
- types.json: {typeName: {parent[], description, properties[]}}
- properties.json: {propName: {domain[], range[], description}}
- type_hierarchy.json: {typeName: [ancestor1, ancestor2, ...]}

Usage:
    python tools/build_schemaorg_cache.py
    python tools/build_schemaorg_cache.py --refresh
    python tools/build_schemaorg_cache.py --dry-run
"""

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
CACHE_DIR = PROJECT_ROOT / "src" / "resources" / "schema_org"

SCHEMAORG_URL = "https://schema.org/version/latest/schemaorg-current-https.jsonld"
RAW_FILE = CACHE_DIR / "schemaorg_full.jsonld"

# Output files
TYPES_FILE = CACHE_DIR / "types.json"
PROPERTIES_FILE = CACHE_DIR / "properties.json"
HIERARCHY_FILE = CACHE_DIR / "type_hierarchy.json"


def download_schema(force: bool = False) -> dict:
    """Download schema.org JSON-LD or load from cache."""
    if RAW_FILE.exists() and not force:
        print(f"Using cached file: {RAW_FILE} ({RAW_FILE.stat().st_size / 1024:.0f} KB)")
        with open(RAW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"Downloading schema.org JSON-LD from {SCHEMAORG_URL}...")
    req = urllib.request.Request(
        SCHEMAORG_URL,
        headers={"Accept": "application/ld+json", "User-Agent": "schemaorg-cache-builder/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

    print(f"Downloaded and cached: {RAW_FILE} ({RAW_FILE.stat().st_size / 1024:.0f} KB)")
    return data


def _extract_name(node: dict) -> Optional[str]:
    """Extract short name from a schema.org node."""
    node_id = node.get("@id", "")
    if node_id.startswith("schema:"):
        return node_id[len("schema:"):]
    if "://schema.org/" in node_id:
        return node_id.rsplit("/", 1)[-1]
    return None


def _extract_names(value: Any) -> List[str]:
    """Extract list of type/property names from JSON-LD value (may be str, dict, or list)."""
    if value is None:
        return []
    if isinstance(value, str):
        name = value.replace("schema:", "").rsplit("/", 1)[-1] if "schema" in value else value
        return [name] if name else []
    if isinstance(value, dict):
        return _extract_names(value.get("@id", ""))
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_extract_names(item))
        return result
    return []


def _get_description(node: dict) -> str:
    """Extract description from rdfs:comment."""
    comment = node.get("rdfs:comment", "")
    if isinstance(comment, dict):
        comment = comment.get("@value", "")
    if isinstance(comment, list):
        comment = comment[0] if comment else ""
        if isinstance(comment, dict):
            comment = comment.get("@value", "")
    # Truncate long descriptions
    if len(comment) > 200:
        comment = comment[:197] + "..."
    return comment


def parse_graph(data: dict) -> tuple:
    """Parse JSON-LD @graph into types and properties."""
    graph = data.get("@graph", [])
    print(f"Parsing {len(graph)} nodes from @graph...")

    types: Dict[str, dict] = {}
    properties: Dict[str, dict] = {}

    # First pass: classify nodes
    for node in graph:
        node_type = node.get("@type", "")
        if isinstance(node_type, list):
            node_type = node_type[0] if node_type else ""

        name = _extract_name(node)
        if not name:
            continue

        if node_type in ("rdfs:Class", "schema:Class"):
            # Schema.org type (class)
            parents = _extract_names(node.get("rdfs:subClassOf"))
            description = _get_description(node)
            types[name] = {
                "parent": parents,
                "description": description,
                "properties": [],  # Filled in second pass
            }
        elif node_type in ("rdf:Property", "schema:Property"):
            # Schema.org property
            domains = _extract_names(node.get("schema:domainIncludes"))
            ranges = _extract_names(node.get("schema:rangeIncludes"))
            description = _get_description(node)
            properties[name] = {
                "domain": domains,
                "range": ranges,
                "description": description,
            }

    # Second pass: populate type properties from property domains
    for prop_name, prop_info in properties.items():
        for domain_type in prop_info["domain"]:
            if domain_type in types:
                types[domain_type]["properties"].append(prop_name)

    # Sort properties within each type
    for type_info in types.values():
        type_info["properties"].sort()

    print(f"Found {len(types)} types and {len(properties)} properties")
    return types, properties


def build_hierarchy(types: Dict[str, dict]) -> Dict[str, List[str]]:
    """Build ancestor chain for each type."""
    hierarchy: Dict[str, List[str]] = {}

    def _get_ancestors(type_name: str, visited: Optional[Set[str]] = None) -> List[str]:
        if visited is None:
            visited = set()
        if type_name in visited:
            return []  # Cycle protection
        visited.add(type_name)

        if type_name in hierarchy:
            return hierarchy[type_name]

        type_info = types.get(type_name)
        if not type_info:
            return []

        ancestors = []
        for parent in type_info["parent"]:
            if parent not in visited:
                ancestors.append(parent)
                ancestors.extend(_get_ancestors(parent, visited))

        # Deduplicate while preserving order
        seen = set()
        unique_ancestors = []
        for a in ancestors:
            if a not in seen:
                seen.add(a)
                unique_ancestors.append(a)

        hierarchy[type_name] = unique_ancestors
        return unique_ancestors

    for type_name in types:
        _get_ancestors(type_name)

    return hierarchy


def write_cache(
    types: Dict[str, dict],
    properties: Dict[str, dict],
    hierarchy: Dict[str, List[str]],
    dry_run: bool = False,
) -> None:
    """Write parsed data to cache files."""
    files = [
        (TYPES_FILE, types),
        (PROPERTIES_FILE, properties),
        (HIERARCHY_FILE, hierarchy),
    ]

    for filepath, data in files:
        content = json.dumps(data, indent=2, sort_keys=True)
        size_kb = len(content) / 1024

        if dry_run:
            print(f"  DRY RUN: Would write {filepath.name} ({size_kb:.1f} KB, {len(data)} entries)")
        else:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  Wrote {filepath.name} ({size_kb:.1f} KB, {len(data)} entries)")


def main():
    parser = argparse.ArgumentParser(description="Build local schema.org vocabulary cache")
    parser.add_argument("--refresh", action="store_true", help="Re-download schema.org JSON-LD")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    print("Building schema.org cache...")
    print(f"Cache directory: {CACHE_DIR}")
    print()

    # Download or load
    data = download_schema(force=args.refresh)

    # Parse
    types, properties = parse_graph(data)
    hierarchy = build_hierarchy(types)

    # Write
    print()
    write_cache(types, properties, hierarchy, dry_run=args.dry_run)

    # Summary
    print()
    print("=" * 60)
    print(f"Types:      {len(types)}")
    print(f"Properties: {len(properties)}")
    print(f"Hierarchy:  {len(hierarchy)} entries")

    # Spot check
    if "Person" in types:
        person = types["Person"]
        print(f"\nSpot check — Person:")
        print(f"  Parents: {person['parent']}")
        print(f"  Properties: {len(person['properties'])} (first 5: {person['properties'][:5]})")

    if "Observation" in types:
        obs = types["Observation"]
        print(f"\nSpot check — Observation:")
        print(f"  Parents: {obs['parent']}")
        print(f"  Properties: {len(obs['properties'])} (first 5: {obs['properties'][:5]})")


if __name__ == "__main__":
    main()
