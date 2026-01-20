#!/usr/bin/env python3
"""
Evaluation benchmark using diff-based comparison (from PR #1688).
Compares LLM-generated pv_maps with human-created ground truth using mcf_diff.

Usage:
    python evaluate_pvmap_diff.py --dataset_path=<path_to_dataset_folder>

Example:
    python evaluate_pvmap_diff.py --dataset_path=../statvar_imports/bis/bis_central_bank_policy_rate
"""

import os
import sys
import csv
import json

# Add paths for imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.append(os.path.join(_DATA_DIR, 'tools', 'statvar_importer'))
sys.path.append(os.path.join(_DATA_DIR, 'tools', 'statvar_importer', 'schema'))
sys.path.append(os.path.join(_DATA_DIR, 'util'))

from absl import app
from absl import flags

_FLAGS = flags.FLAGS
flags.DEFINE_string('dataset_path', '', 'Path to the dataset folder')
flags.DEFINE_string('output_dir', '', 'Output directory for results')
flags.DEFINE_string('auto_pvmap', '', 'Path to existing auto-generated pvmap (skips LLM step)')


def load_env():
    """Load environment variables from .env file."""
    env_file = os.path.join(_DATA_DIR, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value
        print(f"Loaded environment from: {env_file}")


def find_test_data(dataset_path):
    """Find input file (CSV or Excel) in test_data folder."""
    # Try different naming conventions for test data folder
    test_data_dir = None
    for folder_name in ['test_data', 'testdata', 'test-data']:
        candidate = os.path.join(dataset_path, folder_name)
        if os.path.exists(candidate):
            test_data_dir = candidate
            break

    if not test_data_dir:
        raise FileNotFoundError(f"test_data folder not found in {dataset_path}")

    # Search locations: test_data/ and various input subfolders (recursively)
    search_dirs = [test_data_dir]
    for subfolder in ['sample_input', 'input_file', 'input_files', 'input']:
        subdir = os.path.join(test_data_dir, subfolder)
        if os.path.exists(subdir):
            search_dirs.append(subdir)
            # Also add immediate subdirectories for nested structures
            for nested in os.listdir(subdir):
                nested_path = os.path.join(subdir, nested)
                if os.path.isdir(nested_path):
                    search_dirs.append(nested_path)

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        files = os.listdir(search_dir)

        # Priority 1: Look for explicit input files (*_input.csv, *_data.csv)
        for f in files:
            if f.endswith('_input.csv') or f.endswith('_data.csv'):
                return os.path.join(search_dir, f)

        # Priority 2: Look for Excel inputs
        for f in files:
            if f.endswith('_input.xlsx') or f.endswith('_input.xls') or f.endswith('_data.xlsx'):
                return os.path.join(search_dir, f)

        # Priority 3: Any CSV that's not an output file
        for f in files:
            if f.endswith('.csv') and '_output' not in f.lower() and not f.endswith('.tmcf'):
                return os.path.join(search_dir, f)

    raise FileNotFoundError(f"No input file (CSV/Excel) found in {test_data_dir}")


def find_ground_truth_pvmap(dataset_path, input_file=None):
    """Find the ground truth pv_map CSV matching the input file."""
    # Extract base name from input file to match pvmap
    input_base = None
    if input_file:
        input_base = os.path.basename(input_file).replace('_input.csv', '').replace('_input.xlsx', '').replace('_input.xls', '').replace('_data.csv', '').replace('_data.xlsx', '')

    # Search locations: dataset root, config_files/, pv_map/
    search_dirs = [dataset_path]
    for subdir in ['config_files', 'pv_map']:
        subdir_path = os.path.join(dataset_path, subdir)
        if os.path.exists(subdir_path):
            search_dirs.append(subdir_path)

    def is_pvmap_file(filename):
        """Check if file is a pvmap file."""
        f_lower = filename.lower()
        return f_lower.endswith('.csv') and ('pvmap' in f_lower or 'pv_map' in f_lower)

    # First try to find pvmap matching input file name
    if input_base:
        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            for f in os.listdir(search_dir):
                if is_pvmap_file(f):
                    # Extract base name by removing pvmap suffix variations
                    pvmap_base = f.lower().replace('_pvmap.csv', '').replace('_pv_map.csv', '').replace('pvmap.csv', '').replace('pv_map.csv', '')
                    input_base_lower = input_base.lower()
                    if pvmap_base == input_base_lower or input_base_lower.startswith(pvmap_base) or pvmap_base.startswith(input_base_lower):
                        return os.path.join(search_dir, f)

    # Fallback: find any pvmap
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for f in os.listdir(search_dir):
            if is_pvmap_file(f):
                return os.path.join(search_dir, f)

    raise FileNotFoundError(f"No pvmap.csv found in {dataset_path}")


def extract_unique_keys(input_path, max_rows=50):
    """Extract unique column headers and cell values from input file (CSV or Excel)."""
    import pandas as pd
    keys = set()

    # Read file based on extension
    if input_path.endswith('.xlsx') or input_path.endswith('.xls'):
        df = pd.read_excel(input_path, nrows=max_rows)
    else:
        df = pd.read_csv(input_path, nrows=max_rows, encoding='utf-8', on_bad_lines='skip')

    # Add column headers
    for h in df.columns:
        h = str(h).strip()
        if h and len(h) < 80:
            keys.add(h)

    # Add unique cell values
    for col in df.columns:
        for val in df[col].dropna().unique():
            val_str = str(val).strip()
            if val_str and len(val_str) < 80:
                # Skip numeric values
                if not val_str.replace('.', '').replace('-', '').replace(',', '').isdigit():
                    keys.add(val_str)

    return list(keys)


def convert_to_csv_if_needed(file_path, output_dir):
    """Convert Excel file to CSV if needed. Returns path to CSV file."""
    import pandas as pd

    if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
        # Convert Excel to CSV
        csv_path = os.path.join(output_dir, os.path.basename(file_path).replace('.xlsx', '.csv').replace('.xls', '.csv'))
        df = pd.read_excel(file_path)
        df.to_csv(csv_path, index=False)
        print(f"  Converted Excel to CSV: {os.path.basename(csv_path)}")
        return csv_path
    return file_path


def run_auto_schematization(input_keys, sample_data_path, output_path, output_dir):
    """Run LLM-based auto-schematization."""
    load_env()

    api_key = os.environ.get('GOOGLE_API_KEY', '')
    if not api_key or api_key == 'your_gemini_api_key_here':
        raise ValueError("GOOGLE_API_KEY not set in .env file")

    # Convert Excel to CSV if needed (LLM expects CSV)
    sample_data_csv = convert_to_csv_if_needed(sample_data_path, output_dir)

    from config_map import ConfigMap
    from counters import Counters
    import llm_pvmap_generator

    input_pvmap = {key: {} for key in input_keys}

    schema_dir = os.path.join(_DATA_DIR, 'tools', 'statvar_importer', 'schema')
    config = ConfigMap({
        'google_api_key': api_key,
        'llm_model': 'gemini-flash-latest',
        'sample_data': sample_data_csv,
        'sample_pvmap': os.path.join(schema_dir, 'sample_pvmap.csv'),
        'sample_statvars': os.path.join(schema_dir, 'sample_statvars.mcf'),
        'llm_pvmap_prompt': os.path.join(schema_dir, 'llm_pvmap_prompt.txt'),
    })

    print(f"  Calling LLM with {len(input_keys)} keys...")
    output_pvmap = llm_pvmap_generator.llm_generate_pvmap(
        input_pvmap, output_path, config, Counters()
    )
    print(f"  Generated {len(output_pvmap)} mappings")
    return output_pvmap


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


def compare_pvmaps_diff(auto_pvmap_path, gt_pvmap_path, output_dir):
    """Compare pv_maps using diff-based method from mcf_diff."""
    from counters import Counters
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
    print(f"\n  Comparing {len(gt_pvmap)} ground truth nodes with {len(auto_pvmap)} auto nodes...")
    diff_str = diff_mcf_nodes(gt_pvmap, auto_pvmap, config, counters)

    # Save diff output
    diff_file = os.path.join(output_dir, "diff.txt")
    with open(diff_file, 'w') as f:
        f.write(diff_str)

    # Get counter results
    counter_dict = counters.get_counters()

    # Save diff_results.json with raw counters (needed for metrics aggregation)
    results_file = os.path.join(output_dir, "diff_results.json")
    with open(results_file, 'w') as f:
        json.dump(counter_dict, f, indent=2, default=str)

    return counter_dict, diff_str


def print_diff_report(counters, name):
    """Print evaluation report from diff counters."""
    print("\n" + "=" * 60)
    print(f"DIFF REPORT: {name}")
    print("=" * 60)

    # Node-level metrics
    print("\nNODE-LEVEL METRICS:")
    print(f"  Ground truth nodes: {counters.get('nodes-ground-truth', 0)}")
    print(f"  Auto-generated nodes: {counters.get('nodes-auto-generated', 0)}")
    print(f"  Nodes matched: {counters.get('nodes-matched', 0)}")
    print(f"  Nodes with diff: {counters.get('nodes-with-diff', 0)}")
    print(f"  Nodes missing in auto: {counters.get('nodes-missing-in-mcf2', 0)}")
    print(f"  Nodes missing in ground truth: {counters.get('nodes-missing-in-mcf1', 0)}")

    # Property-value level metrics
    print("\nPROPERTY-VALUE METRICS:")
    print(f"  PVs matched: {counters.get('PVs-matched', 0)}")
    print(f"  PVs modified: {counters.get('pvs-modified', 0)}")
    print(f"  PVs added: {counters.get('pvs-added', 0)}")
    print(f"  PVs deleted: {counters.get('pvs-deleted', 0)}")

    # Calculate accuracy
    total_gt = counters.get('nodes-ground-truth', 0)
    matched = counters.get('nodes-matched', 0)
    if total_gt > 0:
        accuracy = round(matched / total_gt * 100, 1)
        print(f"\nACCURACY: {accuracy}% ({matched}/{total_gt} nodes exact match)")

    # PV-level accuracy
    pvs_matched = counters.get('PVs-matched', 0)
    pvs_total = pvs_matched + counters.get('pvs-modified', 0) + counters.get('pvs-deleted', 0)
    if pvs_total > 0:
        pv_accuracy = round(pvs_matched / pvs_total * 100, 1)
        print(f"PV ACCURACY: {pv_accuracy}% ({pvs_matched}/{pvs_total} PVs matched)")

    # Show modified properties breakdown
    print("\nMODIFIED PROPERTIES BREAKDOWN:")
    for key, value in sorted(counters.items()):
        if key.startswith('pvs-modified-') or key.startswith('pvs-added-') or key.startswith('pvs-deleted-'):
            prop_name = key.split('-', 2)[2]
            change_type = key.split('-')[1]
            print(f"  [{change_type}] {prop_name}: {value}")

    print("=" * 60)


def main(_):
    if not _FLAGS.dataset_path:
        print("Usage: python evaluate_pvmap_diff.py --dataset_path=<path>")
        return

    dataset_path = os.path.abspath(_FLAGS.dataset_path)
    dataset_name = os.path.basename(dataset_path)
    base_output_dir = _FLAGS.output_dir or os.path.join(_SCRIPT_DIR, 'results')
    output_dir = os.path.join(base_output_dir, dataset_name)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nEvaluating (diff-based): {dataset_name}")

    # Step 1: Find files
    print("\n[1] Finding files...")
    input_csv = find_test_data(dataset_path)
    gt_path = find_ground_truth_pvmap(dataset_path, input_csv)
    print(f"  Input: {os.path.basename(input_csv)}")
    print(f"  Ground truth: {os.path.basename(gt_path)}")

    # Step 2: Extract keys
    print("\n[2] Extracting keys...")
    keys = extract_unique_keys(input_csv)
    print(f"  Found {len(keys)} unique keys")

    # Step 3: Run auto-schematization (or use existing)
    if _FLAGS.auto_pvmap and os.path.exists(_FLAGS.auto_pvmap):
        print("\n[3] Using existing auto-generated pvmap...")
        auto_path = _FLAGS.auto_pvmap
        print(f"  Using: {auto_path}")
    else:
        print("\n[3] Running auto-schematization...")
        auto_path = os.path.join(output_dir, "auto_pvmap.csv")
        try:
            run_auto_schematization(keys, input_csv, auto_path, output_dir)
        except Exception as e:
            print(f"  Error: {e}")
            return

    # Step 4: Compare using diff method
    print("\n[4] Comparing (diff-based)...")
    counters, diff_str = compare_pvmaps_diff(auto_path, gt_path, output_dir)

    # Step 5: Report
    print_diff_report(counters, dataset_name)

    # Save results
    results_file = os.path.join(output_dir, "diff_results.json")
    with open(results_file, 'w') as f:
        json.dump(counters, f, indent=2, default=str)
    print(f"\nResults saved to: {results_file}")
    print(f"Diff output saved to: {os.path.join(output_dir, 'diff.txt')}")


if __name__ == '__main__':
    app.run(main)
