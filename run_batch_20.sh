#!/bin/bash
# Batch run 20 randomly selected datasets (excluding already processed) with gemini-3-pro-preview
# Generated: 2026-01-19

cd /Users/nehilsood/work/poc-auto-schematization
source venv/bin/activate

# List of 20 randomly selected datasets (excluding already processed in gemini_output)
DATASETS=(
    "brazil_sidra_ibge"
    "brazil_visdata_brazil_rural_development_program"
    "brfss_nchs_asthma_prevalence"
    "census_v2_saipe"
    "child_birth"
    "gdp_by_county_metro_and_other_areas"
    "google_sustainability_financial_incentives"
    "ipeds"
    "ireland_census"
    "mexico_subnational_population_statistics_mexico_census_aa2"
    "ncses_median_annual_salary"
    "opendataforafrica_ethiopia_statistics"
    "opendataforafrica_kenya_census"
    "school_retention"
    "southkorea_statistics_health"
    "us_bls_cpi_category"
    "us_census"
    "us_federal_reserve_h15_interest_rates"
    "us_steam_degrees_data"
    "usa_dol"
)

LOG_FILE="logs/batch_run_$(date +%Y%m%d_%H%M%S).log"
echo "Starting batch run of ${#DATASETS[@]} datasets" | tee "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Start time: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

SUCCESSFUL=0
FAILED=0

for i in "${!DATASETS[@]}"; do
    DATASET="${DATASETS[$i]}"
    NUM=$((i + 1))
    echo "" | tee -a "$LOG_FILE"
    echo "[$NUM/${#DATASETS[@]}] Processing: $DATASET" | tee -a "$LOG_FILE"
    echo "Time: $(date)" | tee -a "$LOG_FILE"

    python run_pvmap_pipeline.py \
        --dataset="$DATASET" \
        --output-dir=output/gemini_output \
        --input-dir=input_new \
        --model=gemini-3-pro-preview 2>&1 | tee -a "$LOG_FILE"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "[$NUM] SUCCESS: $DATASET" | tee -a "$LOG_FILE"
        ((SUCCESSFUL++))
    else
        echo "[$NUM] FAILED: $DATASET" | tee -a "$LOG_FILE"
        ((FAILED++))
    fi
done

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Batch run complete!" | tee -a "$LOG_FILE"
echo "End time: $(date)" | tee -a "$LOG_FILE"
echo "Total: ${#DATASETS[@]}" | tee -a "$LOG_FILE"
echo "Successful: $SUCCESSFUL" | tee -a "$LOG_FILE"
echo "Failed: $FAILED" | tee -a "$LOG_FILE"
