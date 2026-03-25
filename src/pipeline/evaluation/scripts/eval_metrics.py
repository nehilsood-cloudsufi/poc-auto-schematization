#!/usr/bin/env python3
"""
Evaluation metrics for PV Map comparison.

Based on the Auto_Schematization_Evaluation_Benchmark.docx formulas.
"""
import csv
import sys


def load_pvmap(filepath):
    """Load pvmap CSV into dict: key -> {prop: value, ...}"""
    pvmap = {}
    with open(filepath) as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or not row[0]:
                continue
            key = row[0]
            props = {}
            # Parse property-value pairs from remaining columns
            for i in range(1, len(row) - 1, 2):
                if i + 1 < len(row) and row[i] and row[i + 1]:
                    props[row[i]] = row[i + 1]
            pvmap[key] = props
    return pvmap


def evaluate_pvmap(ground_truth_path, generated_path):
    """
    Compare generated PV map against ground truth.

    Returns dict with:
    - Node-level metrics: nodes_ground_truth, nodes_auto_generated,
      nodes_matched, nodes_with_diff, nodes_missing_in_mcf2, nodes_missing_in_mcf1
    - PV-level metrics: pvs_matched, pvs_modified, pvs_added, pvs_deleted
    - Accuracy metrics: node_accuracy, node_coverage, pv_accuracy, precision, recall
    """
    gt = load_pvmap(ground_truth_path)
    gen = load_pvmap(generated_path)

    gt_keys = set(gt.keys())
    gen_keys = set(gen.keys())

    # Node-level metrics
    nodes_ground_truth = len(gt_keys)
    nodes_auto_generated = len(gen_keys)

    common_keys = gt_keys & gen_keys
    nodes_matched = sum(1 for k in common_keys if gt[k] == gen[k])
    nodes_with_diff = len(common_keys) - nodes_matched
    nodes_missing_in_mcf2 = len(gt_keys - gen_keys)  # LLM missed these
    nodes_missing_in_mcf1 = len(gen_keys - gt_keys)  # Extra keys from LLM

    # PV-level metrics
    pvs_matched = pvs_modified = pvs_added = pvs_deleted = 0

    for key in common_keys:
        gt_props = gt[key]
        gen_props = gen[key]

        gt_prop_names = set(gt_props.keys())
        gen_prop_names = set(gen_props.keys())

        # Properties in both
        common_props = gt_prop_names & gen_prop_names
        for prop in common_props:
            if gt_props[prop] == gen_props[prop]:
                pvs_matched += 1
            else:
                pvs_modified += 1

        # Properties only in generated (added)
        pvs_added += len(gen_prop_names - gt_prop_names)

        # Properties only in ground truth (deleted/missing)
        pvs_deleted += len(gt_prop_names - gen_prop_names)

    # Also count PVs from keys that are completely missing
    for key in (gt_keys - gen_keys):
        pvs_deleted += len(gt[key])

    for key in (gen_keys - gt_keys):
        pvs_added += len(gen[key])

    # Calculate accuracy metrics
    node_accuracy = (nodes_matched / nodes_ground_truth * 100) if nodes_ground_truth else 0
    node_coverage = ((nodes_matched + nodes_with_diff) / nodes_ground_truth * 100) if nodes_ground_truth else 0

    denom = pvs_matched + pvs_modified + pvs_deleted
    pv_accuracy = (pvs_matched / denom * 100) if denom else 0
    recall = pv_accuracy  # Same formula

    prec_denom = pvs_matched + pvs_modified + pvs_added
    precision = ((pvs_matched + pvs_modified) / prec_denom * 100) if prec_denom else 0

    return {
        # Node-level
        'nodes_ground_truth': nodes_ground_truth,
        'nodes_auto_generated': nodes_auto_generated,
        'nodes_matched': nodes_matched,
        'nodes_with_diff': nodes_with_diff,
        'nodes_missing_in_mcf2': nodes_missing_in_mcf2,
        'nodes_missing_in_mcf1': nodes_missing_in_mcf1,
        # PV-level
        'pvs_matched': pvs_matched,
        'pvs_modified': pvs_modified,
        'pvs_added': pvs_added,
        'pvs_deleted': pvs_deleted,
        # Accuracy metrics
        'node_accuracy': round(node_accuracy, 1),
        'node_coverage': round(node_coverage, 1),
        'pv_accuracy': round(pv_accuracy, 1),
        'precision': round(precision, 1),
        'recall': round(recall, 1)
    }


def print_results(results):
    """Print evaluation results in a formatted way."""
    print("\n" + "=" * 50)
    print("PV MAP EVALUATION RESULTS")
    print("=" * 50)

    print("\n--- Node-Level Metrics ---")
    print(f"  Nodes in Ground Truth:    {results['nodes_ground_truth']}")
    print(f"  Nodes Auto-Generated:     {results['nodes_auto_generated']}")
    print(f"  Nodes Matched (exact):    {results['nodes_matched']}")
    print(f"  Nodes with Differences:   {results['nodes_with_diff']}")
    print(f"  Nodes Missing (LLM missed): {results['nodes_missing_in_mcf2']}")
    print(f"  Extra Nodes (LLM added):  {results['nodes_missing_in_mcf1']}")

    print("\n--- PV-Level Metrics ---")
    print(f"  PVs Matched:    {results['pvs_matched']}")
    print(f"  PVs Modified:   {results['pvs_modified']}")
    print(f"  PVs Added:      {results['pvs_added']}")
    print(f"  PVs Deleted:    {results['pvs_deleted']}")

    print("\n--- Accuracy Metrics ---")
    print(f"  Node Accuracy:  {results['node_accuracy']}%")
    print(f"  Node Coverage:  {results['node_coverage']}%")
    print(f"  PV Accuracy:    {results['pv_accuracy']}%")
    print(f"  Precision:      {results['precision']}%")
    print(f"  Recall:         {results['recall']}%")

    print("\n--- BIS Gemini Baseline (to beat) ---")
    print("  Node Accuracy:  0.0%")
    print("  Node Coverage:  100.0%")
    print("  PV Accuracy:    0.0%")
    print("  Precision:      11.9%")
    print("  Recall:         0.0%")
    print("=" * 50 + "\n")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python eval_metrics.py <ground_truth_pvmap.csv> <generated_pvmap.csv>")
        sys.exit(1)

    results = evaluate_pvmap(sys.argv[1], sys.argv[2])
    print_results(results)
