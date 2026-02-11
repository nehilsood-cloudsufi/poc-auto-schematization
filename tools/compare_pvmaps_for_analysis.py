#!/usr/bin/env python3
"""Compare ground truth PVMAPs with generated PVMAPs for batch analysis."""

import csv
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

BATCH_DIR = Path("output/batch_20260211_031041")
GT_DIR = Path("ground_truth")


def read_pvmap(path: Path) -> list[dict]:
    """Read a PVMAP CSV into a list of row dicts with normalized keys."""
    rows = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return rows
            for row in reader:
                if not row or all(c.strip() == "" for c in row):
                    continue
                entry = {"key": row[0].strip() if row else ""}
                # Collect property-value pairs
                pvs = []
                i = 1
                while i + 1 < len(row):
                    prop = row[i].strip() if row[i] else ""
                    val = row[i + 1].strip() if i + 1 < len(row) and row[i + 1] else ""
                    if prop:
                        pvs.append((prop, val))
                    i += 2
                entry["pvs"] = pvs
                rows.append(entry)
    except Exception as e:
        print(f"  Warning: Could not read {path}: {e}", file=sys.stderr)
    return rows


def classify_key(row: dict) -> str:
    """Classify a PVMAP row by its role."""
    pvs = row.get("pvs", [])
    props = {p for p, v in pvs}
    if "observationDate" in props:
        return "date"
    if "observationAbout" in props:
        return "place"
    if "value" in props or "measuredProperty" in props or "variableMeasured" in props:
        return "measure"
    if any(p in props for p in ["populationType", "statType", "unit"]):
        return "dimension"
    return "other"


def extract_pvmap_structure(rows: list[dict]) -> dict:
    """Extract structural summary from PVMAP rows."""
    keys = set()
    all_props = set()
    roles = defaultdict(list)
    for row in rows:
        keys.add(row["key"])
        for p, v in row["pvs"]:
            all_props.add(p)
        role = classify_key(row)
        roles[role].append(row["key"])
    return {
        "num_rows": len(rows),
        "keys": keys,
        "properties_used": all_props,
        "roles": dict(roles),
    }


def _normalize_pv_for_comparison(prop: str, val: str) -> tuple[str, str]:
    """Normalize PV tuple for comparison.

    Strips cosmetic differences that don't affect MCF output:
    - dcid: prefix on values (processor adds it internally)
    - {Number} vs {Data} for observationDate/observationAbout
    """
    # Strip dcid: from values
    if val.startswith('dcid:'):
        val = val[5:]
    # Normalize placeholders for observationDate/observationAbout
    if prop in ('observationDate', 'observationAbout'):
        val = val.replace('{Number}', '{Data}')
    return prop, val


def compare_pvmaps(gt_rows: list[dict], gen_rows: list[dict]) -> dict:
    """Compare GT and generated PVMAP rows."""
    gt_keys = {r["key"] for r in gt_rows}
    gen_keys = {r["key"] for r in gen_rows}

    matched_keys = gt_keys & gen_keys
    gt_only_keys = gt_keys - gen_keys
    gen_only_keys = gen_keys - gt_keys

    # For matched keys, compare PVs
    gt_by_key = {r["key"]: r for r in gt_rows}
    gen_by_key = {r["key"]: r for r in gen_rows}

    pv_matches = 0
    pv_gt_only = 0
    pv_gen_only = 0
    pv_value_diffs = []

    for key in matched_keys:
        gt_pvs = set(_normalize_pv_for_comparison(p, v) for p, v in gt_by_key[key]["pvs"])
        gen_pvs = set(_normalize_pv_for_comparison(p, v) for p, v in gen_by_key[key]["pvs"])
        matched = gt_pvs & gen_pvs
        pv_matches += len(matched)
        only_gt = gt_pvs - gen_pvs
        only_gen = gen_pvs - gt_pvs

        # Check for property matches with different values
        gt_prop_map = {p: v for p, v in gt_pvs}
        gen_prop_map = {p: v for p, v in gen_pvs}
        for prop in set(gt_prop_map) & set(gen_prop_map):
            if gt_prop_map[prop] != gen_prop_map[prop]:
                pv_value_diffs.append({
                    "key": key,
                    "property": prop,
                    "gt_value": gt_prop_map[prop],
                    "gen_value": gen_prop_map[prop],
                })

        pv_gt_only += len(only_gt)
        pv_gen_only += len(only_gen)

    # Classify GT-only keys by role
    gt_structure = extract_pvmap_structure(gt_rows)
    gen_structure = extract_pvmap_structure(gen_rows)

    # Identify the mapping approach
    gen_props = gen_structure["properties_used"]
    gt_props = gt_structure["properties_used"]

    is_passthrough = (
        gen_props <= {"observationAbout", "observationDate", "variableMeasured", "value", "property", "property2", "property3"}
        and len(gen_rows) <= 5
    )

    return {
        "gt_keys": len(gt_keys),
        "gen_keys": len(gen_keys),
        "matched_keys": len(matched_keys),
        "gt_only_keys": sorted(list(gt_only_keys))[:10],  # Limit for display
        "gt_only_count": len(gt_only_keys),
        "gen_only_keys": sorted(list(gen_only_keys))[:10],
        "gen_only_count": len(gen_only_keys),
        "pv_matches": pv_matches,
        "pv_gt_only": pv_gt_only,
        "pv_gen_only": pv_gen_only,
        "pv_value_diffs": pv_value_diffs[:10],
        "gt_properties": sorted(gt_props),
        "gen_properties": sorted(gen_props),
        "gt_roles": gt_structure["roles"],
        "gen_roles": gen_structure["roles"],
        "is_passthrough": is_passthrough,
    }


def find_gt_pvmap(dataset_name: str) -> list[Path]:
    """Find ground truth PVMAP file(s) for a dataset."""
    gt_pvmap_dir = GT_DIR / dataset_name / "pvmap"
    if not gt_pvmap_dir.exists():
        return []
    return sorted(gt_pvmap_dir.glob("*.csv"))


def analyze_dataset(dataset_name: str) -> dict | None:
    """Analyze a single dataset's GT vs generated PVMAP."""
    gen_pvmap_path = BATCH_DIR / dataset_name / "generated_pvmap.csv"
    if not gen_pvmap_path.exists():
        return None

    gt_paths = find_gt_pvmap(dataset_name)
    if not gt_paths:
        return None

    gen_rows = read_pvmap(gen_pvmap_path)
    if not gen_rows:
        return None

    # Read diff_results.json if available
    diff_results = {}
    diff_path = BATCH_DIR / dataset_name / "diff_results.json"
    eval_diff_path = BATCH_DIR / dataset_name / "eval_results" / "diff_results.json"
    for p in [diff_path, eval_diff_path]:
        if p.exists():
            try:
                with open(p) as f:
                    diff_results = json.load(f)
            except Exception:
                pass
            break

    # Compare against each GT PVMAP (use the best match from eval)
    best_gt_path = None
    if diff_results.get("best_ground_truth_pvmap"):
        # Try to resolve the path
        best_gt_rel = diff_results["best_ground_truth_pvmap"]
        for gp in gt_paths:
            if gp.name in best_gt_rel or best_gt_rel.endswith(gp.name):
                best_gt_path = gp
                break

    if best_gt_path is None:
        best_gt_path = gt_paths[0]

    gt_rows = read_pvmap(best_gt_path)
    if not gt_rows:
        return None

    comparison = compare_pvmaps(gt_rows, gen_rows)
    comparison["dataset"] = dataset_name
    comparison["gt_file"] = best_gt_path.name
    comparison["gt_pvmap_count"] = len(gt_paths)
    comparison["diff_results"] = diff_results
    comparison["gen_row_count"] = len(gen_rows)
    comparison["gt_row_count"] = len(gt_rows)

    return comparison


def format_key_list(keys: list, max_show: int = 5) -> str:
    """Format a list of keys for display."""
    if not keys:
        return "_none_"
    shown = keys[:max_show]
    result = ", ".join(f"`{k}`" for k in shown)
    if len(keys) > max_show:
        result += f" ... (+{len(keys) - max_show} more)"
    return result


def categorize_mismatch(comp: dict) -> str:
    """Categorize the type of mismatch."""
    if comp["is_passthrough"]:
        return "Passthrough (generic mapping, ignores data structure)"
    if comp["matched_keys"] == 0:
        return "Complete key mismatch (zero overlap)"
    key_rate = comp["matched_keys"] / max(comp["gt_keys"], 1) * 100
    if key_rate > 80 and comp["pv_matches"] == 0:
        return "Keys match but wrong properties/values"
    if key_rate > 80 and comp["pv_matches"] > 0:
        pv_total = comp["pv_matches"] + comp["pv_gt_only"]
        if pv_total > 0 and comp["pv_matches"] / pv_total > 0.4:
            return "Good match (minor property differences)"
        return "Keys match, partial PV match"
    if comp["gen_keys"] < comp["gt_keys"] * 0.3:
        return "Under-generated (too few rows)"
    if comp["gen_keys"] > comp["gt_keys"] * 2:
        return "Over-generated (too many rows)"
    return "Partial key overlap with PV mismatches"


def generate_report(all_comparisons: list[dict]) -> str:
    """Generate the full comparison report section."""
    lines = []

    lines.append("\n---\n")
    lines.append("## Per-Dataset PVMAP Comparison: Generated vs Ground Truth\n")
    lines.append("This section provides a detailed row-level comparison of the generated PVMAP ")
    lines.append("against the best-matching ground truth PVMAP for each dataset.\n")

    # Summary table
    lines.append("### Comparison Summary\n")
    lines.append("| # | Dataset | PV Acc | Key Match | Mismatch Category | GT Rows | Gen Rows | PVs Matched | PVs Missing | PVs Extra |")
    lines.append("|---|---------|--------|-----------|-------------------|---------|----------|-------------|-------------|-----------|")

    # Sort by PV accuracy descending
    def get_pv_acc(c):
        dr = c.get("diff_results", {})
        matched = dr.get("PVs-matched", 0)
        total = matched + dr.get("pvs-deleted", 0)
        if total == 0:
            return -1
        return matched / total * 100

    sorted_comps = sorted(all_comparisons, key=get_pv_acc, reverse=True)

    for i, comp in enumerate(sorted_comps, 1):
        dr = comp.get("diff_results", {})
        matched_pvs = dr.get("PVs-matched", 0)
        deleted_pvs = dr.get("pvs-deleted", 0)
        added_pvs = dr.get("pvs-added", 0)
        total_pvs = matched_pvs + deleted_pvs
        pv_acc = f"{matched_pvs / total_pvs * 100:.1f}%" if total_pvs > 0 else "N/A"

        key_match_rate = comp["matched_keys"] / max(comp["gt_keys"], 1) * 100
        category = categorize_mismatch(comp)

        lines.append(
            f"| {i} | {comp['dataset']} | {pv_acc} | {key_match_rate:.0f}% ({comp['matched_keys']}/{comp['gt_keys']}) | "
            f"{category} | {comp['gt_row_count']} | {comp['gen_row_count']} | {matched_pvs} | {deleted_pvs} | {added_pvs} |"
        )

    # Mismatch category distribution
    lines.append("\n### Mismatch Category Distribution\n")
    categories = defaultdict(list)
    for comp in sorted_comps:
        cat = categorize_mismatch(comp)
        categories[cat].append(comp["dataset"])

    lines.append("| Category | Count | Datasets |")
    lines.append("|----------|-------|----------|")
    for cat, datasets in sorted(categories.items(), key=lambda x: -len(x[1])):
        ds_str = ", ".join(datasets[:5])
        if len(datasets) > 5:
            ds_str += f" (+{len(datasets) - 5} more)"
        lines.append(f"| {cat} | {len(datasets)} | {ds_str} |")

    # Detailed per-dataset analysis
    lines.append("\n### Detailed Per-Dataset Analysis\n")

    for comp in sorted_comps:
        ds = comp["dataset"]
        dr = comp.get("diff_results", {})
        matched_pvs = dr.get("PVs-matched", 0)
        deleted_pvs = dr.get("pvs-deleted", 0)
        added_pvs = dr.get("pvs-added", 0)
        total_pvs = matched_pvs + deleted_pvs
        pv_acc = f"{matched_pvs / total_pvs * 100:.1f}%" if total_pvs > 0 else "N/A"
        category = categorize_mismatch(comp)

        lines.append(f"#### {ds}")
        lines.append(f"**Category**: {category}  ")
        lines.append(f"**PV Accuracy**: {pv_acc} ({matched_pvs} matched / {total_pvs} total)  ")
        lines.append(f"**GT PVMAP**: `{comp['gt_file']}` ({comp['gt_row_count']} rows, {comp.get('gt_pvmap_count', 1)} GT file(s))  ")
        lines.append(f"**Generated**: {comp['gen_row_count']} rows\n")

        # Key comparison
        key_match_rate = comp["matched_keys"] / max(comp["gt_keys"], 1) * 100
        lines.append(f"**Key Overlap**: {comp['matched_keys']}/{comp['gt_keys']} GT keys matched ({key_match_rate:.0f}%), "
                      f"{comp['gen_only_count']} extra keys in generated\n")

        if comp["gt_only_count"] > 0:
            lines.append(f"- Keys in GT but missing from generated: {format_key_list(comp['gt_only_keys'])}")
        if comp["gen_only_count"] > 0:
            lines.append(f"- Keys in generated but not in GT: {format_key_list(comp['gen_only_keys'])}")

        # Property comparison
        gt_props = set(comp["gt_properties"])
        gen_props = set(comp["gen_properties"])
        missing_props = gt_props - gen_props
        extra_props = gen_props - gt_props
        if missing_props:
            lines.append(f"- Properties in GT but missing: {', '.join(f'`{p}`' for p in sorted(missing_props))}")
        if extra_props:
            lines.append(f"- Extra properties in generated: {', '.join(f'`{p}`' for p in sorted(extra_props))}")

        # Value differences
        if comp["pv_value_diffs"]:
            lines.append(f"\n**Value differences on matched keys** (showing up to {min(len(comp['pv_value_diffs']), 5)}):\n")
            lines.append("| Key | Property | GT Value | Generated Value |")
            lines.append("|-----|----------|----------|-----------------|")
            for diff in comp["pv_value_diffs"][:5]:
                lines.append(f"| `{diff['key']}` | `{diff['property']}` | `{diff['gt_value']}` | `{diff['gen_value']}` |")

        # Role comparison
        gt_roles = comp.get("gt_roles", {})
        gen_roles = comp.get("gen_roles", {})
        lines.append(f"\n**Structural roles**:")
        lines.append(f"- Date mappings: GT={len(gt_roles.get('date', []))}, Gen={len(gen_roles.get('date', []))}")
        lines.append(f"- Place mappings: GT={len(gt_roles.get('place', []))}, Gen={len(gen_roles.get('place', []))}")
        lines.append(f"- Measure mappings: GT={len(gt_roles.get('measure', []))}, Gen={len(gen_roles.get('measure', []))}")
        lines.append(f"- Dimension mappings: GT={len(gt_roles.get('dimension', []))}, Gen={len(gen_roles.get('dimension', []))}")
        lines.append(f"- Other: GT={len(gt_roles.get('other', []))}, Gen={len(gen_roles.get('other', []))}")

        lines.append("")

    # Pattern analysis across all datasets
    lines.append("### Cross-Dataset Pattern Analysis\n")

    # Passthrough detection
    passthrough_ds = [c["dataset"] for c in sorted_comps if c["is_passthrough"]]
    if passthrough_ds:
        lines.append(f"#### Passthrough Mapping Problem\n")
        lines.append(f"**{len(passthrough_ds)} datasets** used a generic passthrough mapping (observationAbout/observationDate/variableMeasured/value) ")
        lines.append(f"instead of proper dimension decomposition. These all scored 0% PV accuracy:\n")
        for ds in passthrough_ds:
            lines.append(f"- `{ds}`")
        lines.append("")

    # Key match rate distribution
    high_key = [c for c in sorted_comps if c["matched_keys"] / max(c["gt_keys"], 1) > 0.8]
    low_key = [c for c in sorted_comps if c["matched_keys"] / max(c["gt_keys"], 1) < 0.2]
    lines.append(f"#### Key Match Rate Distribution\n")
    lines.append(f"- **High key match (>80%)**: {len(high_key)} datasets — these have correct key identification but may have PV issues")
    lines.append(f"- **Low key match (<20%)**: {len(low_key)} datasets — fundamental key identification failures")
    lines.append(f"- **Middle range**: {len(sorted_comps) - len(high_key) - len(low_key)} datasets\n")

    # Property usage patterns
    lines.append("#### Common Property Mismatches\n")
    prop_missing_counts = defaultdict(int)
    prop_extra_counts = defaultdict(int)
    for comp in sorted_comps:
        gt_props = set(comp["gt_properties"])
        gen_props = set(comp["gen_properties"])
        for p in gt_props - gen_props:
            prop_missing_counts[p] += 1
        for p in gen_props - gt_props:
            prop_extra_counts[p] += 1

    if prop_missing_counts:
        lines.append("**Properties frequently missing from generated PVMAPs**:\n")
        lines.append("| Property | Missing Count | % of Datasets |")
        lines.append("|----------|---------------|---------------|")
        for prop, count in sorted(prop_missing_counts.items(), key=lambda x: -x[1])[:15]:
            pct = count / len(sorted_comps) * 100
            lines.append(f"| `{prop}` | {count} | {pct:.0f}% |")
        lines.append("")

    if prop_extra_counts:
        lines.append("**Properties in generated but not in GT**:\n")
        lines.append("| Property | Extra Count | % of Datasets |")
        lines.append("|----------|-------------|---------------|")
        for prop, count in sorted(prop_extra_counts.items(), key=lambda x: -x[1])[:10]:
            pct = count / len(sorted_comps) * 100
            lines.append(f"| `{prop}` | {count} | {pct:.0f}% |")
        lines.append("")

    # Under/over generation
    under_gen = [(c["dataset"], c["gt_row_count"], c["gen_row_count"])
                 for c in sorted_comps if c["gen_row_count"] < c["gt_row_count"] * 0.3]
    over_gen = [(c["dataset"], c["gt_row_count"], c["gen_row_count"])
                for c in sorted_comps if c["gen_row_count"] > c["gt_row_count"] * 3]

    if under_gen:
        lines.append("#### Severely Under-Generated PVMAPs\n")
        lines.append("These datasets have <30% of the GT row count — the LLM failed to decompose dimensions:\n")
        lines.append("| Dataset | GT Rows | Gen Rows | Ratio |")
        lines.append("|---------|---------|----------|-------|")
        for ds, gt, gen in sorted(under_gen, key=lambda x: x[2]/max(x[1],1)):
            lines.append(f"| `{ds}` | {gt} | {gen} | {gen/max(gt,1)*100:.0f}% |")
        lines.append("")

    if over_gen:
        lines.append("#### Over-Generated PVMAPs\n")
        lines.append("These datasets have >3x the GT row count:\n")
        lines.append("| Dataset | GT Rows | Gen Rows | Ratio |")
        lines.append("|---------|---------|----------|-------|")
        for ds, gt, gen in sorted(over_gen, key=lambda x: -x[2]/max(x[1],1)):
            lines.append(f"| `{ds}` | {gt} | {gen} | {gen/max(gt,1)*100:.0f}% |")
        lines.append("")

    return "\n".join(lines)


def main():
    # Get all datasets in the batch
    datasets = sorted([
        d.name for d in BATCH_DIR.iterdir()
        if d.is_dir() and d.name not in ("logs",) and not d.name.startswith(".")
    ])

    print(f"Found {len(datasets)} datasets in batch", file=sys.stderr)

    all_comparisons = []
    skipped = []

    for ds in datasets:
        comp = analyze_dataset(ds)
        if comp:
            all_comparisons.append(comp)
        else:
            skipped.append(ds)

    print(f"Compared {len(all_comparisons)} datasets, skipped {len(skipped)}", file=sys.stderr)
    if skipped:
        print(f"Skipped: {', '.join(skipped)}", file=sys.stderr)

    report = generate_report(all_comparisons)
    print(report)


if __name__ == "__main__":
    main()
