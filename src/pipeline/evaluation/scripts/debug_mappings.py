#!/usr/bin/env python3
"""Debug script to check dataset name mappings."""

import sys
sys.path.insert(0, '.')

from generate_benchmark_comparison import extract_benchmark_data, extract_new_iteration_data, fuzzy_match_dataset_names

# Extract data
benchmark_data = extract_benchmark_data('/Users/nehilsood/Downloads/Auto_Schematization_Evaluation_Benchmark.docx')
new_data = extract_new_iteration_data('analysis/Auto_Schematization_Evaluation_Analysis.md')

print(f"Benchmark datasets: {len(benchmark_data)}")
print(f"New iteration datasets: {len(new_data)}")
print()

# Get mappings
name_mapping = fuzzy_match_dataset_names(new_data.keys(), benchmark_data.keys())

print(f"Matched datasets: {len(name_mapping)}")
print()

# Show matched
print("MATCHED PAIRS:")
print("="*80)
for new_name in sorted(name_mapping.keys()):
    bench_name = name_mapping[new_name]
    if new_name == bench_name:
        print(f"  {new_name}")
    else:
        print(f"  {new_name:50s} -> {bench_name}")
print()

# Show unmatched from new iteration
new_unmatched = set(new_data.keys()) - set(name_mapping.keys())
print(f"NEW ITERATION DATASETS NOT MATCHED ({len(new_unmatched)}):")
print("="*80)
for ds in sorted(new_unmatched):
    print(f"  {ds}")
print()

# Show unmatched from benchmark
bench_matched = set(name_mapping.values())
bench_unmatched = set(benchmark_data.keys()) - bench_matched
print(f"BENCHMARK DATASETS NOT MATCHED ({len(bench_unmatched)}):")
print("="*80)
for ds in sorted(bench_unmatched):
    # Try to find similar names in new iteration
    similar = []
    for new_ds in new_data.keys():
        if ds.lower() in new_ds.lower() or new_ds.lower() in ds.lower():
            similar.append(new_ds)

    if similar:
        print(f"  {ds:40s} (similar: {', '.join(similar)})")
    else:
        print(f"  {ds}")
