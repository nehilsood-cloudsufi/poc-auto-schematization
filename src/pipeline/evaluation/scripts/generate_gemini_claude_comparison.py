#!/usr/bin/env python3
"""
Generate comprehensive Gemini vs Claude comparison report with proper metrics.

Compares Gemini and Claude auto-schematization outputs using proper evaluation
metrics (Node Accuracy, PV Accuracy, Precision, Recall) from all_metrics.json files.

Usage:
    python generate_gemini_claude_comparison.py
"""

import os
import json
from datetime import datetime


def load_metrics_file(metrics_path):
    """Load metrics from all_metrics.json file."""
    if os.path.exists(metrics_path):
        with open(metrics_path, 'r') as f:
            return json.load(f)
    return {}


def generate_report(gemini_metrics, claude_metrics, common_datasets):
    """Generate the comparison markdown report using proper metrics."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Calculate summary statistics
    gemini_wins = 0
    claude_wins = 0
    ties = 0

    comparison_rows = []

    for dataset in sorted(common_datasets):
        gemini = gemini_metrics.get(dataset, {})
        claude = claude_metrics.get(dataset, {})

        gemini_calc = gemini.get('calculated', {})
        claude_calc = claude.get('calculated', {})

        gemini_raw = gemini.get('raw', {})
        claude_raw = claude.get('raw', {})

        # Get metrics (cap node accuracy/coverage at 100% - can exceed due to diff algorithm bug)
        gemini_node_acc = min(gemini_calc.get('node_accuracy', 0), 100.0)
        gemini_node_cov = min(gemini_calc.get('node_coverage', 0), 100.0)
        gemini_pv_acc = gemini_calc.get('pv_accuracy', 0)
        gemini_precision = gemini_calc.get('precision', 0)

        claude_node_acc = min(claude_calc.get('node_accuracy', 0), 100.0)
        claude_node_cov = min(claude_calc.get('node_coverage', 0), 100.0)
        claude_pv_acc = claude_calc.get('pv_accuracy', 0)
        claude_precision = claude_calc.get('precision', 0)

        # Get raw counts for additional context
        gemini_gt_nodes = gemini_raw.get('nodes-ground-truth', 0)
        claude_gt_nodes = claude_raw.get('nodes-ground-truth', 0)

        # Determine winner based on PV Accuracy (primary metric)
        if gemini_pv_acc > claude_pv_acc + 0.1:  # Small epsilon for tie detection
            winner = 'Gemini'
            gemini_wins += 1
        elif claude_pv_acc > gemini_pv_acc + 0.1:
            winner = 'Claude'
            claude_wins += 1
        else:
            winner = 'Tie'
            ties += 1

        comparison_rows.append({
            'dataset': dataset,
            'gemini_node_acc': gemini_node_acc,
            'gemini_node_cov': gemini_node_cov,
            'gemini_pv_acc': gemini_pv_acc,
            'gemini_precision': gemini_precision,
            'claude_node_acc': claude_node_acc,
            'claude_node_cov': claude_node_cov,
            'claude_pv_acc': claude_pv_acc,
            'claude_precision': claude_precision,
            'winner': winner,
            'pv_diff': gemini_pv_acc - claude_pv_acc,
            'gemini_gt_nodes': gemini_gt_nodes,
            'claude_gt_nodes': claude_gt_nodes,
        })

    # Calculate averages
    def avg(values):
        return sum(values) / len(values) if values else 0

    avg_gemini_node_acc = avg([r['gemini_node_acc'] for r in comparison_rows])
    avg_gemini_node_cov = avg([r['gemini_node_cov'] for r in comparison_rows])
    avg_gemini_pv_acc = avg([r['gemini_pv_acc'] for r in comparison_rows])
    avg_gemini_precision = avg([r['gemini_precision'] for r in comparison_rows])

    avg_claude_node_acc = avg([r['claude_node_acc'] for r in comparison_rows])
    avg_claude_node_cov = avg([r['claude_node_cov'] for r in comparison_rows])
    avg_claude_pv_acc = avg([r['claude_pv_acc'] for r in comparison_rows])
    avg_claude_precision = avg([r['claude_precision'] for r in comparison_rows])

    # Build report
    report = f"""# Gemini vs Claude Auto-Schematization Comparison

**Generated**: {timestamp}

This report compares the auto-generated PVMAP outputs from **Gemini** and **Claude** models for datasets where both have evaluation results with proper metrics.

---

## Executive Summary

### Dataset Coverage

| Metric | Gemini | Claude | Common |
|--------|--------|--------|--------|
| Total Datasets with Metrics | {len(gemini_metrics)} | {len(claude_metrics)} | - |
| Datasets Compared | - | - | **{len(common_datasets)}** |

### Winner Analysis (Based on PV Accuracy)

| Winner | Count | Percentage |
|--------|-------|------------|
| **Gemini** | {gemini_wins} | {gemini_wins/len(common_datasets)*100:.1f}% |
| **Claude** | {claude_wins} | {claude_wins/len(common_datasets)*100:.1f}% |
| **Tie** | {ties} | {ties/len(common_datasets)*100:.1f}% |

*Winner determined by PV Accuracy. Higher accuracy = better.*

### Average Performance Metrics

| Metric | Gemini Avg | Claude Avg | Difference |
|--------|------------|------------|------------|
| **Node Accuracy %** | {avg_gemini_node_acc:.1f} | {avg_claude_node_acc:.1f} | {avg_gemini_node_acc - avg_claude_node_acc:+.1f} |
| **Node Coverage %** | {avg_gemini_node_cov:.1f} | {avg_claude_node_cov:.1f} | {avg_gemini_node_cov - avg_claude_node_cov:+.1f} |
| **PV Accuracy %** | {avg_gemini_pv_acc:.1f} | {avg_claude_pv_acc:.1f} | {avg_gemini_pv_acc - avg_claude_pv_acc:+.1f} |
| **Precision %** | {avg_gemini_precision:.1f} | {avg_claude_precision:.1f} | {avg_gemini_precision - avg_claude_precision:+.1f} |

---

## Detailed Comparison Table

| Dataset | Gemini Node % | Claude Node % | Gemini PV % | Claude PV % | Gemini Prec % | Claude Prec % | Winner |
|---------|--------------|---------------|-------------|-------------|---------------|---------------|--------|
"""

    for row in comparison_rows:
        winner_emoji = '🟢' if row['winner'] == 'Claude' else ('🔵' if row['winner'] == 'Gemini' else '⚪')
        report += f"| {row['dataset']} | {row['gemini_node_acc']} | {row['claude_node_acc']} | {row['gemini_pv_acc']} | {row['claude_pv_acc']} | {row['gemini_precision']} | {row['claude_precision']} | {winner_emoji} {row['winner']} |\n"

    # Top performers
    report += """
---

## Performance Analysis

### Datasets Where Gemini Outperforms Claude (by PV Accuracy)

"""
    gemini_better = sorted([r for r in comparison_rows if r['winner'] == 'Gemini'],
                          key=lambda x: x['pv_diff'], reverse=True)[:10]

    if gemini_better:
        report += "| Dataset | Gemini PV % | Claude PV % | Difference |\n"
        report += "|---------|-------------|-------------|-----------|\n"
        for row in gemini_better:
            report += f"| {row['dataset']} | {row['gemini_pv_acc']} | {row['claude_pv_acc']} | **+{row['pv_diff']:.1f}** |\n"
    else:
        report += "*No datasets where Gemini clearly outperforms Claude*\n"

    report += """
### Datasets Where Claude Outperforms Gemini (by PV Accuracy)

"""
    claude_better = sorted([r for r in comparison_rows if r['winner'] == 'Claude'],
                          key=lambda x: -x['pv_diff'], reverse=True)[:10]

    if claude_better:
        report += "| Dataset | Gemini PV % | Claude PV % | Difference |\n"
        report += "|---------|-------------|-------------|-----------|\n"
        for row in claude_better:
            report += f"| {row['dataset']} | {row['gemini_pv_acc']} | {row['claude_pv_acc']} | **{row['pv_diff']:.1f}** |\n"
    else:
        report += "*No datasets where Claude clearly outperforms Gemini*\n"

    # Datasets with ties (similar performance)
    report += """
### Datasets With Similar Performance (Ties)

"""
    similar = [r for r in comparison_rows if r['winner'] == 'Tie']

    if similar:
        report += "| Dataset | Gemini PV % | Claude PV % |\n"
        report += "|---------|-------------|-------------|\n"
        for row in similar:
            report += f"| {row['dataset']} | {row['gemini_pv_acc']} | {row['claude_pv_acc']} |\n"
    else:
        report += "*No datasets with identical performance*\n"

    # Best performers overall
    report += """
---

## Best Performing Datasets (by PV Accuracy)

### Top 10 Gemini Results

"""
    top_gemini = sorted(comparison_rows, key=lambda x: x['gemini_pv_acc'], reverse=True)[:10]
    report += "| Dataset | PV Accuracy % | Node Accuracy % | Precision % |\n"
    report += "|---------|---------------|-----------------|-------------|\n"
    for row in top_gemini:
        report += f"| {row['dataset']} | {row['gemini_pv_acc']} | {row['gemini_node_acc']} | {row['gemini_precision']} |\n"

    report += """
### Top 10 Claude Results

"""
    top_claude = sorted(comparison_rows, key=lambda x: x['claude_pv_acc'], reverse=True)[:10]
    report += "| Dataset | PV Accuracy % | Node Accuracy % | Precision % |\n"
    report += "|---------|---------------|-----------------|-------------|\n"
    for row in top_claude:
        report += f"| {row['dataset']} | {row['claude_pv_acc']} | {row['claude_node_acc']} | {row['claude_precision']} |\n"

    # Summary
    report += f"""
---

## Key Insights

### Model Comparison Summary

1. **Overall Performance**: {"Gemini" if avg_gemini_pv_acc > avg_claude_pv_acc else "Claude"} has higher average PV Accuracy ({max(avg_gemini_pv_acc, avg_claude_pv_acc):.1f}% vs {min(avg_gemini_pv_acc, avg_claude_pv_acc):.1f}%)

2. **Win Rate**: Gemini wins on {gemini_wins}/{len(common_datasets)} datasets ({gemini_wins/len(common_datasets)*100:.1f}%), Claude wins on {claude_wins}/{len(common_datasets)} ({claude_wins/len(common_datasets)*100:.1f}%)

3. **Node Coverage**: {"Gemini" if avg_gemini_node_cov > avg_claude_node_cov else "Claude"} has better node coverage ({max(avg_gemini_node_cov, avg_claude_node_cov):.1f}% vs {min(avg_gemini_node_cov, avg_claude_node_cov):.1f}%)

4. **Precision**: {"Gemini" if avg_gemini_precision > avg_claude_precision else "Claude"} has higher precision ({max(avg_gemini_precision, avg_claude_precision):.1f}% vs {min(avg_gemini_precision, avg_claude_precision):.1f}%)

### Recommendations

- For datasets requiring **high accuracy**: Choose the model that performs best on similar dataset types
- Both models struggle with large, complex schemas (BLS, CPI datasets)
- Both models perform better on simpler financial/census datasets

---

*Report generated on {timestamp}*
*Comparison based on {len(common_datasets)} datasets with evaluation metrics in both Gemini and Claude outputs*
"""

    return report


def main():
    """Main execution."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Paths to metrics files
    gemini_metrics_file = os.path.join(script_dir, 'analysis', 'gemini', 'all_metrics.json')
    claude_metrics_file = os.path.join(script_dir, 'analysis', 'claude_cli_sys_1', 'raw_data', 'all_metrics.json')
    output_file = os.path.join(script_dir, 'analysis', 'Gemini_vs_Claude_Comparison.md')

    print("=" * 60)
    print("Generating Gemini vs Claude Comparison Report")
    print("=" * 60)

    print(f"\nLoading Gemini metrics from {gemini_metrics_file}...")
    gemini_metrics = load_metrics_file(gemini_metrics_file)
    print(f"  Loaded {len(gemini_metrics)} Gemini datasets")

    print(f"\nLoading Claude metrics from {claude_metrics_file}...")
    claude_metrics = load_metrics_file(claude_metrics_file)
    print(f"  Loaded {len(claude_metrics)} Claude datasets")

    print("\nFinding common datasets...")
    common_datasets = set(gemini_metrics.keys()) & set(claude_metrics.keys())
    print(f"  Found {len(common_datasets)} common datasets")

    if not common_datasets:
        print("\nERROR: No common datasets found!")
        print("Gemini datasets:", list(gemini_metrics.keys())[:5], "...")
        print("Claude datasets:", list(claude_metrics.keys())[:5], "...")
        return

    print("\nCommon datasets:")
    for ds in sorted(common_datasets):
        print(f"  - {ds}")

    print("\nGenerating comparison report...")
    report = generate_report(gemini_metrics, claude_metrics, common_datasets)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    print(f"\nWriting report to {output_file}...")
    with open(output_file, 'w') as f:
        f.write(report)

    print("\nDone! Report generated successfully.")


if __name__ == '__main__':
    main()
