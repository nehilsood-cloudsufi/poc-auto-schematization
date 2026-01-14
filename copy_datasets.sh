#!/bin/bash

# Script to copy datasets from statvar_imports to input folder
# Target structure: input/{dataset_name}/test_data/{input_file}.csv + input/{dataset_name}/{metadata_file}.csv
# Only copies datasets that have BOTH input file(s) AND metadata file(s)

SOURCE_DIR="/Users/nehilsood/work/datacommonsorg-data/statvar_imports"
DEST_DIR="/Users/nehilsood/work/poc-auto-schematization/input"

# Find all unique dataset directories that contain test_data with input files
echo "Finding all datasets with input files..."

# Get unique dataset directories (parent of test_data folders containing input files)
dataset_dirs=$(find "$SOURCE_DIR" -path "*/test_data/*" -name "*input*.csv" 2>/dev/null | while read -r input_file; do
    dirname "$(dirname "$input_file")"
done | sort -u)

total_datasets=0
skipped_datasets=0
total_input_files=0
total_metadata_files=0

for dataset_dir in $dataset_dirs; do
    # Get the dataset name (last component of path)
    dataset_name=$(basename "$dataset_dir")
    test_data_dir="$dataset_dir/test_data"

    # Check if input files exist in test_data
    input_files=$(find "$test_data_dir" -maxdepth 1 -name "*input*.csv" 2>/dev/null)
    if [[ -z "$input_files" ]]; then
        echo "Skipping $dataset_name: No input files found"
        skipped_datasets=$((skipped_datasets + 1))
        continue
    fi

    # Check if metadata files exist in dataset directory
    metadata_files=$(find "$dataset_dir" -maxdepth 1 -name "*metadata*.csv" 2>/dev/null)
    if [[ -z "$metadata_files" ]]; then
        echo "Skipping $dataset_name: No metadata files found"
        skipped_datasets=$((skipped_datasets + 1))
        continue
    fi

    echo "Processing dataset: $dataset_name"
    echo "  Source: $dataset_dir"

    # Create destination directories
    dest_dataset_dir="$DEST_DIR/$dataset_name"
    dest_test_data_dir="$dest_dataset_dir/test_data"

    mkdir -p "$dest_test_data_dir"

    # Copy all input files from test_data
    input_count=0
    for src_input in "$test_data_dir"/*input*.csv; do
        if [[ -f "$src_input" ]]; then
            cp "$src_input" "$dest_test_data_dir/"
            echo "  Copied input: $(basename "$src_input")"
            input_count=$((input_count + 1))
        fi
    done

    # Copy all metadata files from dataset directory
    metadata_count=0
    for src_metadata in "$dataset_dir"/*metadata*.csv; do
        if [[ -f "$src_metadata" ]]; then
            cp "$src_metadata" "$dest_dataset_dir/"
            echo "  Copied metadata: $(basename "$src_metadata")"
            metadata_count=$((metadata_count + 1))
        fi
    done

    echo "  -> $input_count input file(s), $metadata_count metadata file(s)"
    echo ""

    total_datasets=$((total_datasets + 1))
    total_input_files=$((total_input_files + input_count))
    total_metadata_files=$((total_metadata_files + metadata_count))
done

echo "=== Copy Complete ==="
echo "Total datasets copied: $total_datasets"
echo "Skipped datasets (missing input or metadata): $skipped_datasets"
echo ""
echo "Destination folder contents:"
ls -la "$DEST_DIR" | head -30
echo ""
echo "Total input files copied: $(find "$DEST_DIR" -name "*input*.csv" 2>/dev/null | wc -l)"
echo "Total metadata files copied: $(find "$DEST_DIR" -name "*metadata*.csv" 2>/dev/null | wc -l)"