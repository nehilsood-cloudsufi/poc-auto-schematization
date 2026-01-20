#!/usr/bin/env python3
"""
Generate evaluation metrics for Gemini PVMAP outputs.

Runs diff-based comparison between Gemini generated pvmaps and ground truth
to produce metrics in the same format as Claude's all_metrics.json.

Usage:
    python generate_gemini_metrics.py
"""

import os
import sys
import json
import glob
from datetime import datetime
from collections import defaultdict

# Add paths for imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_SCRIPT_DIR, 'tools'))
sys.path.append(os.path.join(_SCRIPT_DIR, 'util'))

from counters import Counters


def find_gemini_datasets(gemini_output_dir):
    """Find all Gemini datasets with generated_pvmap.csv."""
    datasets = {}
    for dataset_dir in glob.glob(os.path.join(gemini_output_dir, '*')):
        if not os.path.isdir(dataset_dir):
            continue
        dataset_name = os.path.basename(dataset_dir)
        pvmap_file = os.path.join(dataset_dir, 'generated_pvmap.csv')
        if os.path.exists(pvmap_file):
            datasets[dataset_name] = {
                'pvmap_file': pvmap_file,
                'dir': dataset_dir
            }
    return datasets


def find_ground_truth_pvmap(dataset_name, statvar_imports_dir):
    """Find the ground truth pv_map CSV for a dataset.

    The ground truth pvmaps are in the datacommonsorg-data/statvar_imports folder.
    Dataset names have patterns like:
    - bis_bis_central_bank_policy_rate -> bis/bis_central_bank_policy_rate
    - us_bls_bls_ces -> us_bls/bls_ces
    - fao_currency_and_exchange_rate -> fao/currency_and_exchange_rate
    """
    def is_pvmap_file(filename):
        """Check if file is a pvmap file."""
        f_lower = filename.lower()
        return f_lower.endswith('.csv') and ('pvmap' in f_lower or 'pv_map' in f_lower)

    def search_for_pvmap(base_path):
        """Search for pvmap file in a directory and its subdirs."""
        if not os.path.exists(base_path):
            return None

        # Search in base_path, config_files/, pv_map/ subdirs
        search_dirs = [base_path]
        for subdir in ['config_files', 'pv_map']:
            subdir_path = os.path.join(base_path, subdir)
            if os.path.exists(subdir_path):
                search_dirs.append(subdir_path)

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            for f in os.listdir(search_dir):
                if is_pvmap_file(f):
                    return os.path.join(search_dir, f)
        return None

    # Try different folder patterns
    patterns_to_try = []

    # Pattern 1: Split at first underscore (prefix/rest)
    # e.g., bis_bis_central_bank_policy_rate -> bis/bis_central_bank_policy_rate
    if '_' in dataset_name:
        parts = dataset_name.split('_', 1)
        patterns_to_try.append(os.path.join(statvar_imports_dir, parts[0], parts[1]))

    # Pattern 2: Common multi-part prefixes
    common_prefixes = ['us_bls', 'us_cdc', 'us_census', 'us_crash', 'us_federal_reserve',
                       'southkorea_statistics', 'brazil_visdata', 'statistics_new_zealand',
                       'opendataforafrica', 'ncses', 'brazil_sidra', 'census_v2',
                       'cdc', 'crdc', 'school', 'oecd', 'fao', 'google_sustainability',
                       'india_ndap', 'india_rbi', 'us_education']
    for prefix in common_prefixes:
        if dataset_name.startswith(prefix + '_'):
            rest = dataset_name[len(prefix) + 1:]
            patterns_to_try.append(os.path.join(statvar_imports_dir, prefix, rest))

    # Pattern 3: Direct dataset_name as subfolder (unlikely but try)
    patterns_to_try.append(os.path.join(statvar_imports_dir, dataset_name))

    # Search each pattern
    for base_path in patterns_to_try:
        result = search_for_pvmap(base_path)
        if result:
            return result

    return None


def load_pvmap_for_diff(pvmap_path, drop_ignored_props=True):
    """Load pv_map CSV into dict format for diff comparison."""
    from property_value_mapper import load_pv_map

    pvmap = load_pv_map(pvmap_path)
    output_pvmap = {}

    for key, pvs in pvmap.items():
        if drop_ignored_props and key.startswith('#'):
            continue
        if not pvs:
            continue
        output_pvs = {}
        for p, v in pvs.items():
            if drop_ignored_props and p in ['#Column', 'DataType']:
                continue
            if drop_ignored_props and p.startswith('#'):
                if not (p.startswith('#Eval') or p.startswith('#Regex') or
                        p.startswith('#Filter') or p.startswith('#Multiply') or
                        p.startswith('#ignore') or p.startswith('#Format')):
                    continue
            output_pvs[p] = v
        if output_pvs:
            output_pvs['dcid'] = key
            output_pvmap[key] = output_pvs

    return output_pvmap


def run_diff_comparison(auto_pvmap_path, gt_pvmap_path):
    """Compare pv_maps using diff-based method from mcf_diff."""
    from mcf_diff import diff_mcf_nodes

    counters = Counters()

    # Load pvmaps
    gt_pvmap = load_pvmap_for_diff(gt_pvmap_path)
    auto_pvmap = load_pvmap_for_diff(auto_pvmap_path)

    counters.add_counter('nodes-ground-truth', len(gt_pvmap))
    counters.add_counter('nodes-auto-generated', len(auto_pvmap))

    # Config for diff
    config = {
        'ignore_property': ['dcid', 'Node'],
        'show_diff_nodes_only': False,
    }

    # Run diff
    diff_str = diff_mcf_nodes(gt_pvmap, auto_pvmap, config, counters)

    # Get counter results
    counter_dict = counters.get_counters()

    return counter_dict, diff_str


def calculate_metrics(raw_counters):
    """Calculate derived metrics from raw counters."""
    nodes_gt = raw_counters.get('nodes-ground-truth', 0)
    nodes_matched = raw_counters.get('nodes-matched', 0)
    nodes_with_diff = raw_counters.get('nodes-with-diff', 0)

    pvs_matched = raw_counters.get('PVs-matched', 0)
    pvs_modified = raw_counters.get('pvs-modified', 0)
    pvs_added = raw_counters.get('pvs-added', 0)
    pvs_deleted = raw_counters.get('pvs-deleted', 0)

    # Node accuracy (capped at 100% - nodes_matched can exceed nodes_gt due to diff algorithm)
    node_accuracy = (min(nodes_matched, nodes_gt) / nodes_gt * 100) if nodes_gt > 0 else 0
    node_coverage = (min(nodes_matched + nodes_with_diff, nodes_gt) / nodes_gt * 100) if nodes_gt > 0 else 0

    # PV accuracy
    pv_denom = pvs_matched + pvs_modified + pvs_deleted
    pv_accuracy = (pvs_matched / pv_denom * 100) if pv_denom > 0 else 0

    # Precision
    prec_denom = pvs_matched + pvs_modified + pvs_added
    precision = ((pvs_matched + pvs_modified) / prec_denom * 100) if prec_denom > 0 else 0

    # Recall is same as PV accuracy
    recall = pv_accuracy

    # Rating
    def get_rating(pv_acc):
        if pv_acc >= 80:
            return "Excellent"
        elif pv_acc >= 50:
            return "Good"
        elif pv_acc >= 20:
            return "Needs Work"
        else:
            return "Poor"

    return {
        'node_accuracy': round(node_accuracy, 1),
        'node_coverage': round(node_coverage, 1),
        'pv_accuracy': round(pv_accuracy, 1),
        'precision': round(precision, 1),
        'recall': round(recall, 1),
        'node_rating': get_rating(node_accuracy),
        'pv_rating': get_rating(pv_accuracy)
    }


def extract_prop_counts(raw_counters, prefix):
    """Extract property-specific counts from counters."""
    props = {}
    for key, value in raw_counters.items():
        if key.startswith(f'{prefix}-') and key.count('-') > 1:
            prop_name = key.split('-', 2)[2]
            props[prop_name] = value
    return props


def main():
    """Main execution."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Paths
    gemini_output_dir = os.path.join(script_dir, 'output', 'gemini_output')
    # Ground truth pvmaps are in datacommonsorg-data/statvar_imports
    statvar_imports_dir = os.path.join(os.path.dirname(script_dir), 'datacommonsorg-data', 'statvar_imports')
    output_dir = os.path.join(script_dir, 'analysis', 'gemini')
    output_file = os.path.join(output_dir, 'all_metrics.json')

    print("=" * 60)
    print("Generating Gemini Evaluation Metrics")
    print("=" * 60)

    print(f"\nStatvar imports dir: {statvar_imports_dir}")
    if not os.path.exists(statvar_imports_dir):
        print(f"  WARNING: statvar_imports directory not found!")
        print(f"  Expected at: {statvar_imports_dir}")

    print(f"\nFinding Gemini datasets with generated_pvmap.csv...")
    gemini_datasets = find_gemini_datasets(gemini_output_dir)
    print(f"  Found {len(gemini_datasets)} Gemini datasets")

    # Process each dataset
    all_metrics = {}
    success_count = 0
    skip_count = 0
    error_count = 0

    for dataset_name, dataset_info in sorted(gemini_datasets.items()):
        print(f"\nProcessing: {dataset_name}")

        # Find ground truth
        gt_path = find_ground_truth_pvmap(dataset_name, statvar_imports_dir)
        if not gt_path:
            print(f"  WARNING: No ground truth pvmap found, skipping")
            skip_count += 1
            continue

        print(f"  Ground truth: {os.path.basename(gt_path)}")
        print(f"  Generated: {os.path.basename(dataset_info['pvmap_file'])}")

        try:
            # Run diff comparison
            raw_counters, diff_str = run_diff_comparison(
                dataset_info['pvmap_file'],
                gt_path
            )

            # Calculate metrics
            calculated = calculate_metrics(raw_counters)

            # Extract property-specific counts
            added_props = extract_prop_counts(raw_counters, 'pvs-added')
            deleted_props = extract_prop_counts(raw_counters, 'pvs-deleted')
            modified_props = extract_prop_counts(raw_counters, 'pvs-modified')

            # Store results
            all_metrics[dataset_name] = {
                'raw': raw_counters,
                'calculated': calculated,
                'added_props': added_props,
                'deleted_props': deleted_props,
                'modified_props': modified_props,
                'status': 'complete',
                'ground_truth_path': gt_path,
                'generated_path': dataset_info['pvmap_file']
            }

            # Also save individual diff_results.json
            eval_results_dir = os.path.join(dataset_info['dir'], 'eval_results')
            os.makedirs(eval_results_dir, exist_ok=True)
            results_file = os.path.join(eval_results_dir, 'diff_results.json')
            with open(results_file, 'w') as f:
                json.dump(raw_counters, f, indent=2)

            # Save diff.txt if not exists
            diff_file = os.path.join(eval_results_dir, 'diff.txt')
            if not os.path.exists(diff_file):
                with open(diff_file, 'w') as f:
                    f.write(diff_str)

            print(f"  Nodes: GT={raw_counters.get('nodes-ground-truth', 0)}, "
                  f"Gen={raw_counters.get('nodes-auto-generated', 0)}, "
                  f"Matched={raw_counters.get('nodes-matched', 0)}")
            print(f"  PV Accuracy: {calculated['pv_accuracy']}%")
            print(f"  Node Accuracy: {calculated['node_accuracy']}%")

            success_count += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            error_count += 1
            continue

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Write aggregated metrics
    print(f"\n{'=' * 60}")
    print(f"Writing aggregated metrics to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(all_metrics, f, indent=2)

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total Gemini datasets: {len(gemini_datasets)}")
    print(f"  Successfully processed: {success_count}")
    print(f"  Skipped (no ground truth): {skip_count}")
    print(f"  Errors: {error_count}")

    if all_metrics:
        # Calculate averages
        avg_node_acc = sum(m['calculated']['node_accuracy'] for m in all_metrics.values()) / len(all_metrics)
        avg_node_cov = sum(m['calculated']['node_coverage'] for m in all_metrics.values()) / len(all_metrics)
        avg_pv_acc = sum(m['calculated']['pv_accuracy'] for m in all_metrics.values()) / len(all_metrics)
        avg_precision = sum(m['calculated']['precision'] for m in all_metrics.values()) / len(all_metrics)

        print(f"\nAverage Metrics ({len(all_metrics)} datasets):")
        print(f"  Node Accuracy: {avg_node_acc:.1f}%")
        print(f"  Node Coverage: {avg_node_cov:.1f}%")
        print(f"  PV Accuracy: {avg_pv_acc:.1f}%")
        print(f"  Precision: {avg_precision:.1f}%")

    print(f"\nOutput saved to: {output_file}")
    print("Done!")


if __name__ == '__main__':
    main()
