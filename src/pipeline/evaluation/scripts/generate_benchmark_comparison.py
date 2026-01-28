#!/usr/bin/env python3
"""
Generate comprehensive benchmark comparison report.
Compares benchmark results with new iteration results across all 5 metrics.

Usage:
    python generate_benchmark_comparison.py
"""

import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from docx import Document


def extract_benchmark_data(docx_path):
    """Extract all 49 datasets with 5 metrics from benchmark docx table."""
    doc = Document(docx_path)

    # Find the largest table (likely the dataset results)
    largest_table = max(doc.tables, key=lambda t: len(t.rows))

    benchmark_data = {}

    # Skip header row, iterate through data rows
    for row in largest_table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        if len(cells) >= 6:
            dataset = cells[0]
            node_acc = float(cells[1]) if cells[1] else 0.0
            node_cov = float(cells[2]) if cells[2] else 0.0
            pv_acc = float(cells[3]) if cells[3] else 0.0
            precision = float(cells[4]) if cells[4] else 0.0
            recall = float(cells[5]) if cells[5] else 0.0

            benchmark_data[dataset] = {
                'node_acc': node_acc,
                'node_cov': node_cov,
                'pv_acc': pv_acc,
                'precision': precision,
                'recall': recall
            }

    return benchmark_data


def extract_new_iteration_data(analysis_md_path):
    """Parse table from Auto_Schematization_Evaluation_Analysis.md."""
    new_data = {}

    with open(analysis_md_path, 'r') as f:
        content = f.read()

    # Find the Complete Results Table section
    table_match = re.search(r'## Complete Results Table\n\n(.+?)\n\n---', content, re.DOTALL)
    if not table_match:
        raise ValueError("Could not find Complete Results Table in analysis markdown")

    table_text = table_match.group(1)
    lines = table_text.strip().split('\n')

    # Skip header and separator rows
    for line in lines[2:]:
        if not line.strip() or line.startswith('|---'):
            continue

        # Parse table row
        parts = [p.strip().replace('*', '') for p in line.split('|')]  # Remove asterisks
        if len(parts) >= 7:
            dataset = parts[1]
            node_acc = float(parts[2]) if parts[2] and parts[2] != '-' else 0.0
            node_cov = float(parts[3]) if parts[3] and parts[3] != '-' else 0.0
            pv_acc = float(parts[4]) if parts[4] and parts[4] != '-' else 0.0
            precision = float(parts[5]) if parts[5] and parts[5] != '-' else 0.0
            recall = float(parts[6]) if parts[6] and parts[6] != '-' else 0.0

            dataset = dataset.strip()

            new_data[dataset] = {
                'node_acc': node_acc,
                'node_cov': node_cov,
                'pv_acc': pv_acc,
                'precision': precision,
                'recall': recall
            }

    return new_data


def fuzzy_match_dataset_names(new_names, benchmark_names, threshold=0.6):
    """Auto-detect dataset name mappings using fuzzy string matching."""
    # Manual overrides for known matches
    manual_overrides = {
        'india_ndap_india_nss_health_ailments': 'IndiaNSS_HealthAilments',
        'ccd_enrollment': 'enrollment',
        'census_v2_sahie': 'sahie',
        'us_education_new_york_education': 'education',
        'us_urban_school_teachers': 'teachers',
        'ncses_ncses_demographics_seh_import': 'demographics',
        'india_ndap': 'ndap',
    }

    # Datasets to exclude from fuzzy matching (will be in "not in benchmark" section)
    exclude_from_matching = {
        'finland_census',  # Not in benchmark (different from kenya_census)
        'bis',  # Not in benchmark (bis_central_bank_policy_rate is different)
        'nyu_diabetes_texas',  # Not in benchmark
        'school_algebra1',  # Not in benchmark
        'us_newyork_ny_diabetes',  # Not in benchmark
        'us_urban_school_covid_directional_indicators',  # Not in benchmark
        'us_urban_school_maths_and_science_enrollment',  # Not in benchmark
    }

    mapping = {}

    for new_name in new_names:
        # Skip excluded datasets
        if new_name in exclude_from_matching:
            continue

        # Check manual overrides first
        if new_name in manual_overrides:
            override = manual_overrides[new_name]
            if override in benchmark_names:
                mapping[new_name] = override
                continue

        best_match = None
        best_score = 0

        # Clean names for comparison
        new_clean = new_name.lower().replace('_', '').replace('-', '')

        for bench_name in benchmark_names:
            bench_clean = bench_name.lower().replace('_', '').replace('-', '')

            # Try exact substring match first
            if bench_clean in new_clean or new_clean in bench_clean:
                # Extra check: if length difference is too large, reduce score
                len_ratio = min(len(bench_clean), len(new_clean)) / max(len(bench_clean), len(new_clean))
                if len_ratio < 0.5:
                    score = 0.5  # Reduce score for very different lengths
                else:
                    score = 0.9
            else:
                score = SequenceMatcher(None, new_clean, bench_clean).ratio()

            if score > best_score:
                best_score = score
                best_match = bench_name

        # Additional validation: check if the match makes sense
        # Reject if threshold is met but the match seems wrong
        if best_score >= threshold:
            # Check for common acronym mismatches (e.g., ndap vs nfhs)
            new_words = set(new_name.lower().split('_'))
            bench_words = set(best_match.lower().split('_'))

            # If no common words and high reliance on fuzzy match, increase threshold
            common_words = new_words & bench_words
            if not common_words and best_score < 0.75:
                continue  # Skip this match

            mapping[new_name] = best_match

    return mapping


def calculate_summary_stats(benchmark_data, new_data, name_mapping):
    """Calculate summary statistics across all metrics."""
    stats = {
        'datasets_compared': 0,
        'node_acc_improved': 0,
        'node_acc_declined': 0,
        'pv_acc_improved': 0,
        'pv_acc_declined': 0,
        'precision_improved': 0,
        'precision_declined': 0,
        'recall_improved': 0,
        'recall_declined': 0,
        'node_cov_improved': 0,
        'node_cov_declined': 0,
        'avg_node_acc_change': 0,
        'avg_node_cov_change': 0,
        'avg_pv_acc_change': 0,
        'avg_precision_change': 0,
        'avg_recall_change': 0,
        'best_pv_improvement': ('', 0),
        'best_node_improvement': ('', 0),
        'best_precision_improvement': ('', 0),
        'best_recall_improvement': ('', 0),
        'worst_pv_decline': ('', 0),
        'worst_node_decline': ('', 0),
        'worst_precision_decline': ('', 0),
        'worst_recall_decline': ('', 0),
    }

    total_node_change = total_cov_change = total_pv_change = 0
    total_precision_change = total_recall_change = 0

    for new_name, bench_name in name_mapping.items():
        if new_name not in new_data or bench_name not in benchmark_data:
            continue

        stats['datasets_compared'] += 1
        new = new_data[new_name]
        bench = benchmark_data[bench_name]

        # Calculate deltas
        node_delta = new['node_acc'] - bench['node_acc']
        cov_delta = new['node_cov'] - bench['node_cov']
        pv_delta = new['pv_acc'] - bench['pv_acc']
        precision_delta = new['precision'] - bench['precision']
        recall_delta = new['recall'] - bench['recall']

        # Count improvements/declines
        if node_delta > 0.1:
            stats['node_acc_improved'] += 1
        elif node_delta < -0.1:
            stats['node_acc_declined'] += 1

        if cov_delta > 0.1:
            stats['node_cov_improved'] += 1
        elif cov_delta < -0.1:
            stats['node_cov_declined'] += 1

        if pv_delta > 0.1:
            stats['pv_acc_improved'] += 1
        elif pv_delta < -0.1:
            stats['pv_acc_declined'] += 1

        if precision_delta > 0.1:
            stats['precision_improved'] += 1
        elif precision_delta < -0.1:
            stats['precision_declined'] += 1

        if recall_delta > 0.1:
            stats['recall_improved'] += 1
        elif recall_delta < -0.1:
            stats['recall_declined'] += 1

        # Track best/worst
        if pv_delta > stats['best_pv_improvement'][1]:
            stats['best_pv_improvement'] = (new_name, pv_delta)
        if pv_delta < stats['worst_pv_decline'][1]:
            stats['worst_pv_decline'] = (new_name, pv_delta)

        if node_delta > stats['best_node_improvement'][1]:
            stats['best_node_improvement'] = (new_name, node_delta)
        if node_delta < stats['worst_node_decline'][1]:
            stats['worst_node_decline'] = (new_name, node_delta)

        if precision_delta > stats['best_precision_improvement'][1]:
            stats['best_precision_improvement'] = (new_name, precision_delta)
        if precision_delta < stats['worst_precision_decline'][1]:
            stats['worst_precision_decline'] = (new_name, precision_delta)

        if recall_delta > stats['best_recall_improvement'][1]:
            stats['best_recall_improvement'] = (new_name, recall_delta)
        if recall_delta < stats['worst_recall_decline'][1]:
            stats['worst_recall_decline'] = (new_name, recall_delta)

        # Sum for averages
        total_node_change += node_delta
        total_cov_change += cov_delta
        total_pv_change += pv_delta
        total_precision_change += precision_delta
        total_recall_change += recall_delta

    # Calculate averages
    if stats['datasets_compared'] > 0:
        stats['avg_node_acc_change'] = total_node_change / stats['datasets_compared']
        stats['avg_node_cov_change'] = total_cov_change / stats['datasets_compared']
        stats['avg_pv_acc_change'] = total_pv_change / stats['datasets_compared']
        stats['avg_precision_change'] = total_precision_change / stats['datasets_compared']
        stats['avg_recall_change'] = total_recall_change / stats['datasets_compared']

    return stats


def generate_comparison_report(benchmark_data, new_data, name_mapping):
    """Generate complete markdown report with all sections."""
    stats = calculate_summary_stats(benchmark_data, new_data, name_mapping)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Calculate average values for benchmark and new iteration
    avg_bench_node_acc = sum(benchmark_data[name_mapping[n]]['node_acc'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0
    avg_new_node_acc = sum(new_data[n]['node_acc'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0

    avg_bench_node_cov = sum(benchmark_data[name_mapping[n]]['node_cov'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0
    avg_new_node_cov = sum(new_data[n]['node_cov'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0

    avg_bench_pv_acc = sum(benchmark_data[name_mapping[n]]['pv_acc'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0
    avg_new_pv_acc = sum(new_data[n]['pv_acc'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0

    avg_bench_precision = sum(benchmark_data[name_mapping[n]]['precision'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0
    avg_new_precision = sum(new_data[n]['precision'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0

    avg_bench_recall = sum(benchmark_data[name_mapping[n]]['recall'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0
    avg_new_recall = sum(new_data[n]['recall'] for n in name_mapping if n in new_data) / stats['datasets_compared'] if stats['datasets_compared'] > 0 else 0

    # Total dataset counts
    total_benchmark_datasets = len(benchmark_data)
    total_new_datasets = len(new_data)

    report = f"""# Evaluation Benchmark Comparison

**Generated**: {timestamp}

This report compares our auto-generated PVMAP evaluation results against the benchmark results from the reference document.

---

## Executive Summary

### Final Statistics

**Dataset Coverage:**
- **Total Benchmark Datasets:** {total_benchmark_datasets}
- **Total New Iteration Datasets:** {total_new_datasets}
- **Datasets Compared:** {stats['datasets_compared']} (overlap between both evaluations)
- **Benchmark Datasets Not in New Iteration:** {total_benchmark_datasets - stats['datasets_compared']}
- **New Datasets Not in Benchmark:** {total_new_datasets - stats['datasets_compared']}

**Performance Summary:**
- **PV Accuracy Improved:** {stats['pv_acc_improved']} datasets ({stats['pv_acc_improved']/stats['datasets_compared']*100:.1f}%)
- **Average PV Accuracy:** {avg_bench_pv_acc:.1f}% (benchmark) → {avg_new_pv_acc:.1f}% (new iteration)
- **Average Precision:** {avg_bench_precision:.1f}% (benchmark) → {avg_new_precision:.1f}% (new iteration)
- **Average Recall:** {avg_bench_recall:.1f}% (benchmark) → {avg_new_recall:.1f}% (new iteration)

### Dataset Coverage

| Metric | Benchmark | New Iteration |
|--------|-----------|---------------|
| **Total Datasets** | {total_benchmark_datasets} | {total_new_datasets} |
| **Datasets Compared** | {stats['datasets_compared']} | {stats['datasets_compared']} |
| **Not in Other Set** | {total_benchmark_datasets - stats['datasets_compared']} | {total_new_datasets - stats['datasets_compared']} |

### Average Performance Metrics

| Metric | Benchmark Avg | New Iteration Avg |
|--------|---------------|-------------------|
| **Node Accuracy %** | {avg_bench_node_acc:.1f} | {avg_new_node_acc:.1f} |
| **Node Coverage %** | {avg_bench_node_cov:.1f} | {avg_new_node_cov:.1f} |
| **PV Accuracy %** | {avg_bench_pv_acc:.1f} | {avg_new_pv_acc:.1f} |
| **Precision %** | {avg_bench_precision:.1f} | {avg_new_precision:.1f} |
| **Recall %** | {avg_bench_recall:.1f} | {avg_new_recall:.1f} |

### Improvement Statistics

| Metric | Improved | Declined | No Change |
|--------|----------|----------|-----------|
| **Node Accuracy** | {stats['node_acc_improved']} ({stats['node_acc_improved']/stats['datasets_compared']*100:.1f}%) | {stats['node_acc_declined']} ({stats['node_acc_declined']/stats['datasets_compared']*100:.1f}%) | {stats['datasets_compared']-stats['node_acc_improved']-stats['node_acc_declined']} |
| **Node Coverage** | {stats['node_cov_improved']} ({stats['node_cov_improved']/stats['datasets_compared']*100:.1f}%) | {stats['node_cov_declined']} ({stats['node_cov_declined']/stats['datasets_compared']*100:.1f}%) | {stats['datasets_compared']-stats['node_cov_improved']-stats['node_cov_declined']} |
| **PV Accuracy** | {stats['pv_acc_improved']} ({stats['pv_acc_improved']/stats['datasets_compared']*100:.1f}%) | {stats['pv_acc_declined']} ({stats['pv_acc_declined']/stats['datasets_compared']*100:.1f}%) | {stats['datasets_compared']-stats['pv_acc_improved']-stats['pv_acc_declined']} |
| **Precision** | {stats['precision_improved']} ({stats['precision_improved']/stats['datasets_compared']*100:.1f}%) | {stats['precision_declined']} ({stats['precision_declined']/stats['datasets_compared']*100:.1f}%) | {stats['datasets_compared']-stats['precision_improved']-stats['precision_declined']} |
| **Recall** | {stats['recall_improved']} ({stats['recall_improved']/stats['datasets_compared']*100:.1f}%) | {stats['recall_declined']} ({stats['recall_declined']/stats['datasets_compared']*100:.1f}%) | {stats['datasets_compared']-stats['recall_improved']-stats['recall_declined']} |

### Best Improvements

- **Node Accuracy**: {stats['best_node_improvement'][0]} ({stats['best_node_improvement'][1]:+.1f}%)
- **PV Accuracy**: {stats['best_pv_improvement'][0]} ({stats['best_pv_improvement'][1]:+.1f}%)
- **Precision**: {stats['best_precision_improvement'][0]} ({stats['best_precision_improvement'][1]:+.1f}%)
- **Recall**: {stats['best_recall_improvement'][0]} ({stats['best_recall_improvement'][1]:+.1f}%)

### Largest Declines

- **Node Accuracy**: {stats['worst_node_decline'][0]} ({stats['worst_node_decline'][1]:.1f}%)
- **PV Accuracy**: {stats['worst_pv_decline'][0]} ({stats['worst_pv_decline'][1]:.1f}%)
- **Precision**: {stats['worst_precision_decline'][0]} ({stats['worst_precision_decline'][1]:.1f}%)
- **Recall**: {stats['worst_recall_decline'][0]} ({stats['worst_recall_decline'][1]:.1f}%)

---

## Detailed Comparison Table

| Dataset | Benchmark Node Acc % | New Node Acc % | Benchmark Node Cov % | New Node Cov % | Benchmark PV % | New PV % | Benchmark Precision % | New Precision % | Benchmark Recall % | New Recall % |
|---------|---------------------|----------------|---------------------|---------------|---------------|---------|----------------------|----------------|-------------------|--------------|
"""

    # Sort by PV accuracy improvement
    sorted_datasets = []
    for new_name, bench_name in name_mapping.items():
        if new_name in new_data and bench_name in benchmark_data:
            new = new_data[new_name]
            bench = benchmark_data[bench_name]
            pv_delta = new['pv_acc'] - bench['pv_acc']
            sorted_datasets.append((new_name, bench_name, pv_delta))

    sorted_datasets.sort(key=lambda x: x[2], reverse=True)

    for new_name, bench_name, _ in sorted_datasets:
        new = new_data[new_name]
        bench = benchmark_data[bench_name]

        report += f"| {new_name} | {bench['node_acc']:.1f} | {new['node_acc']:.1f} | {bench['node_cov']:.1f} | {new['node_cov']:.1f} | {bench['pv_acc']:.1f} | {new['pv_acc']:.1f} | {bench['precision']:.1f} | {new['precision']:.1f} | {bench['recall']:.1f} | {new['recall']:.1f} |\n"

    # Add sections for improved datasets
    report += "\n---\n\n## Improved Datasets by Metric\n\n"

    # PV Accuracy improvements
    pv_improved = [(n, b, new_data[n]['pv_acc'] - benchmark_data[b]['pv_acc'])
                   for n, b, _ in sorted_datasets
                   if new_data[n]['pv_acc'] > benchmark_data[b]['pv_acc']]

    report += f"### PV Accuracy Improvements ({len(pv_improved)} datasets)\n\n"
    report += "| Dataset | Benchmark PV % | New PV % | Improvement |\n"
    report += "|---------|----------------|----------|-------------|\n"
    for new_name, bench_name, delta in pv_improved[:15]:  # Top 15
        bench_val = benchmark_data[bench_name]['pv_acc']
        new_val = new_data[new_name]['pv_acc']
        report += f"| {new_name} | {bench_val:.1f} | {new_val:.1f} | +{delta:.1f} |\n"

    # Node Accuracy improvements
    node_improved = [(n, b, new_data[n]['node_acc'] - benchmark_data[b]['node_acc'])
                     for n, b, _ in sorted_datasets
                     if new_data[n]['node_acc'] > benchmark_data[b]['node_acc']]

    report += f"\n### Node Accuracy Improvements ({len(node_improved)} datasets)\n\n"
    report += "| Dataset | Benchmark Node % | New Node % | Improvement |\n"
    report += "|---------|-----------------|------------|-------------|\n"
    for new_name, bench_name, delta in sorted(node_improved, key=lambda x: x[2], reverse=True)[:15]:
        bench_val = benchmark_data[bench_name]['node_acc']
        new_val = new_data[new_name]['node_acc']
        report += f"| {new_name} | {bench_val:.1f} | {new_val:.1f} | +{delta:.1f} |\n"

    # Declined datasets
    pv_declined = [(n, b, new_data[n]['pv_acc'] - benchmark_data[b]['pv_acc'])
                   for n, b, _ in sorted_datasets
                   if new_data[n]['pv_acc'] < benchmark_data[b]['pv_acc']]

    report += f"\n---\n\n## Declined Datasets by Metric\n\n"
    report += f"### PV Accuracy Declines ({len(pv_declined)} datasets)\n\n"
    report += "| Dataset | Benchmark PV % | New PV % | Decline |\n"
    report += "|---------|----------------|----------|---------|\n"
    for new_name, bench_name, delta in sorted(pv_declined, key=lambda x: x[2]):
        bench_val = benchmark_data[bench_name]['pv_acc']
        new_val = new_data[new_name]['pv_acc']
        report += f"| {new_name} | {bench_val:.1f} | {new_val:.1f} | {delta:.1f} |\n"

    # Dataset name mappings
    report += "\n---\n\n## Dataset Name Mappings\n\n"
    report += "| New Iteration Name | Benchmark Name |\n"
    report += "|--------------------|----------------|\n"
    for new_name, bench_name in sorted(name_mapping.items()):
        if new_name != bench_name:
            report += f"| {new_name} | {bench_name} |\n"

    # Datasets not in benchmark
    new_only = set(new_data.keys()) - set(name_mapping.keys())
    if new_only:
        report += "\n---\n\n## Datasets Not in Benchmark\n\n"
        report += "The following datasets in our evaluation were not found in the benchmark document:\n\n"
        for dataset in sorted(new_only):
            report += f"- {dataset}: {new_data[dataset]['pv_acc']:.1f}% PV Accuracy\n"

    # Datasets not in new iteration
    bench_only = set(benchmark_data.keys()) - set(name_mapping.values())
    if bench_only:
        report += "\n---\n\n## Benchmark Datasets Not in Our Evaluation\n\n"
        report += "The following datasets from the benchmark were not found in our evaluation:\n\n"
        for dataset in sorted(bench_only):
            report += f"- {dataset}: {benchmark_data[dataset]['pv_acc']:.1f}% PV Accuracy (benchmark)\n"

    report += f"\n---\n\n*Comparison generated on {timestamp}*\n"

    return report


def main():
    """Main execution: read inputs, compare, write output."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Input paths
    benchmark_docx = '/Users/nehilsood/Downloads/Auto_Schematization_Evaluation_Benchmark.docx'
    analysis_md = os.path.join(script_dir, 'analysis', 'Auto_Schematization_Evaluation_Analysis.md')
    output_md = os.path.join(script_dir, 'analysis', 'Benchmark_Comparison.md')

    print("Extracting benchmark data from docx...")
    benchmark_data = extract_benchmark_data(benchmark_docx)
    print(f"  Found {len(benchmark_data)} datasets in benchmark")

    print("\nExtracting new iteration data from markdown...")
    new_data = extract_new_iteration_data(analysis_md)
    print(f"  Found {len(new_data)} datasets in new iteration")

    print("\nFuzzy matching dataset names...")
    name_mapping = fuzzy_match_dataset_names(new_data.keys(), benchmark_data.keys())
    print(f"  Matched {len(name_mapping)} datasets")

    print("\nGenerating comparison report...")
    report = generate_comparison_report(benchmark_data, new_data, name_mapping)

    print(f"\nWriting report to {output_md}...")
    with open(output_md, 'w') as f:
        f.write(report)

    print("✓ Benchmark comparison report generated successfully!")


if __name__ == '__main__':
    main()
