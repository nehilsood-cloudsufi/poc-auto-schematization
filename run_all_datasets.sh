#!/bin/bash

# Script to run PVMAP pipeline on all datasets in input_benchmark
# Output goes to output_benchmark/claude_cli_output
# 30 second cooldown between each run

INPUT_DIR="input_benchmark"
OUTPUT_DIR="output_benchmark/claude_cli_output"
PYTHON="./venv/bin/python3"
SCRIPT="run_pvmap_pipeline.py"
COOLDOWN=30

# List of all datasets
DATASETS=(
    "bis_bis_central_bank_policy_rate"
    "brazil_sidra_ibge"
    "brazil_visdata_FoodBasketDistribution"
    "brazil_visdata_brazil_rural_development_program"
    "brfss_nchs_asthma_prevalence"
    "ccd_enrollment"
    "cdc_social_vulnerability_index"
    "census_v2_sahie"
    "census_v2_saipe"
    "commerce_eda"
    "crdc_import_crdc_harassment_or_bullying"
    "database_on_indian_economy_india_rbi_state_statistics"
    "doctoratedegreeemployment"
    "fao_currency_and_exchange_rate"
    "fbi_fbigovcrime"
    "india_ndap"
    "india_ndap_india_nss_health_ailments"
    "india_nfhs"
    "inpe_fire"
    "ncses_median_annual_salary"
    "ncses_ncses_demographics_seh_import"
    "oecd_regional_education"
    "oecd_wastewater_treatment"
    "opendataforafrica_ethiopia_statistics"
    "opendataforafrica_kenya_census"
    "southkorea_statistics_education"
    "southkorea_statistics_employment"
    "southkorea_statistics_health"
    "undata"
    "us_bls_bls_ces"
    "us_bls_bls_ces_state"
    "us_bls_cpi_category"
    "us_bls_us_cpi"
    "us_cdc_single_race"
    "us_census"
    "us_census_us_monthly_retail_sales"
    "us_crash_fars_crashdata"
    "us_steam_degrees_data"
    "us_urban_school_teachers"
    "usa_dol_minimum_wage"
    "world_bank_commodity_market"
    "zurich_bev_3240_wiki"
    "zurich_bev_3903_age10_wiki"
    "zurich_bev_3903_hel_wiki"
    "zurich_bev_3903_sex_wiki"
    "zurich_bev_4031_hel_wiki"
    "zurich_bev_4031_sex_wiki"
    "zurich_bev_4031_wiki"
    "zurich_wir_2552_wiki"
)

TOTAL=${#DATASETS[@]}
CURRENT=0
SUCCESSFUL=0
FAILED=0

echo "=========================================="
echo "PVMAP Pipeline Batch Runner"
echo "=========================================="
echo "Total datasets: $TOTAL"
echo "Output directory: $OUTPUT_DIR"
echo "Cooldown between runs: ${COOLDOWN}s"
echo "=========================================="
echo ""

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Create logs directory
LOGS_DIR="logs"
mkdir -p "$LOGS_DIR"

# Track failed datasets
FAILED_DATASETS=()

for dataset in "${DATASETS[@]}"; do
    CURRENT=$((CURRENT + 1))
    echo ""
    echo "=========================================="
    echo "[$CURRENT/$TOTAL] Processing: $dataset"
    echo "=========================================="
    echo "Start time: $(date)"
    echo ""

    # Create timestamped log file for this dataset
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOG_FILE="$LOGS_DIR/${dataset}_${TIMESTAMP}.log"

    # Run the pipeline and capture output to log file
    $PYTHON $SCRIPT --dataset="$dataset" --input-dir="$INPUT_DIR" --output-dir="$OUTPUT_DIR" 2>&1 | tee "$LOG_FILE"
    EXIT_CODE=${PIPESTATUS[0]}

    if [ $EXIT_CODE -eq 0 ]; then
        echo ""
        echo "SUCCESS: $dataset completed successfully"
        SUCCESSFUL=$((SUCCESSFUL + 1))
    else
        echo ""
        echo "FAILED: $dataset failed with exit code $EXIT_CODE"
        FAILED=$((FAILED + 1))
        FAILED_DATASETS+=("$dataset")
    fi

    echo "End time: $(date)"

    # Cooldown if not the last dataset
    if [ $CURRENT -lt $TOTAL ]; then
        echo ""
        echo "Cooling down for ${COOLDOWN} seconds..."
        sleep $COOLDOWN
    fi
done

echo ""
echo "=========================================="
echo "BATCH RUN COMPLETE"
echo "=========================================="
echo "Total: $TOTAL"
echo "Successful: $SUCCESSFUL"
echo "Failed: $FAILED"
echo ""

if [ ${#FAILED_DATASETS[@]} -gt 0 ]; then
    echo "Failed datasets:"
    for failed in "${FAILED_DATASETS[@]}"; do
        echo "  - $failed"
    done
fi

echo ""
echo "Results saved to: $OUTPUT_DIR"
echo "=========================================="
