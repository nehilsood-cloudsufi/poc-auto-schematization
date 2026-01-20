#!/bin/bash

# Rerun failed datasets with enhanced error feedback
# The datasets that failed validation in the previous batch run

FAILED_DATASETS=(
    "census_v2_sahie"
    "database_on_indian_economy_india_rbi_state_statistics"
    "ncses_ncses_demographics_seh_import"
    "opendataforafrica_kenya_census"
    "us_bls_bls_ces"
    "us_bls_us_cpi"
    "us_cdc_single_race"
    "us_census"
    "us_census_us_monthly_retail_sales"
    "us_crash_fars_crashdata"
    "us_steam_degrees_data"
    "world_bank_commodity_market"
)

OUTPUT_DIR="output_benchmark/rerun_enhanced"
COOLDOWN=10

TOTAL=${#FAILED_DATASETS[@]}
CURRENT=0
SUCCESSFUL=0
FAILED=0

echo "==========================================="
echo "Rerunning Failed Datasets"
echo "==========================================="
echo "Total datasets: $TOTAL"
echo "Output directory: $OUTPUT_DIR"
echo "==========================================="

mkdir -p "$OUTPUT_DIR"

FAILED_LIST=()
SUCCESS_LIST=()

for dataset in "${FAILED_DATASETS[@]}"; do
    CURRENT=$((CURRENT + 1))
    echo ""
    echo "==========================================="
    echo "[$CURRENT/$TOTAL] Processing: $dataset"
    echo "==========================================="

    ./venv/bin/python3 run_pvmap_pipeline.py \
        --dataset="$dataset" \
        --input-dir=input_benchmark \
        --output-dir="$OUTPUT_DIR" \
        2>&1

    # Check if processed.csv has data
    PROCESSED_FILE="$OUTPUT_DIR/$dataset/processed.csv"
    if [ -f "$PROCESSED_FILE" ]; then
        LINES=$(wc -l < "$PROCESSED_FILE")
        if [ "$LINES" -gt 1 ]; then
            echo "SUCCESS: $dataset ($((LINES-1)) data rows)"
            SUCCESSFUL=$((SUCCESSFUL + 1))
            SUCCESS_LIST+=("$dataset")
        else
            echo "FAILED: $dataset (empty output)"
            FAILED=$((FAILED + 1))
            FAILED_LIST+=("$dataset")
        fi
    else
        echo "FAILED: $dataset (no processed.csv)"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("$dataset")
    fi

    if [ $CURRENT -lt $TOTAL ]; then
        echo "Cooling down for ${COOLDOWN}s..."
        sleep $COOLDOWN
    fi
done

echo ""
echo "==========================================="
echo "RERUN COMPLETE"
echo "==========================================="
echo "Successful: $SUCCESSFUL / $TOTAL"
echo "Failed: $FAILED / $TOTAL"
echo ""
echo "Successful: ${SUCCESS_LIST[*]}"
echo "Failed: ${FAILED_LIST[*]}"
