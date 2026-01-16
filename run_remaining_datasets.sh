#!/bin/bash
# Script to process all remaining datasets from input_new folder
# Author: Claude Code
# Date: 2026-01-16
# Purpose: Run PVMAP pipeline for all unprocessed datasets with proper logging and delays

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INPUT_DIR="input_new"
SLEEP_DURATION=60  # seconds between runs
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="${SCRIPT_DIR}/batch_run_logs"
MAIN_LOG="${LOG_DIR}/batch_run_${TIMESTAMP}.log"
SUMMARY_LOG="${LOG_DIR}/batch_summary_${TIMESTAMP}.txt"

# Create log directory
mkdir -p "${LOG_DIR}"

# Datasets to process (37 remaining datasets)
DATASETS=(
    "brazil_visdata_FoodBasketDistribution"
    "brazil_visdata_brazil_rural_development_program"
    "crdc_import_crdc_harassment_or_bullying"
    "crdc_instructional_wifi_devices"
    "database_on_indian_economy_india_rbi_state_statistics"
    "fema"
    "gdp_by_county_metro_and_other_areas"
    "google_sustainability_financial_incentives"
    "ipeds"
    "ireland_census"
    "mexico_subnational_population_statistics_mexico_census_aa2"
    "ncses_median_annual_salary"
    "ncses_research_doctorate_recipients"
    "ntia_internet_use_survey"
    "nyu_diabetes_tennessee"
    "oecd_quarterly_gdp"
    "oecd_regional_education"
    "opendataforafrica_ethiopia_statistics"
    "opendataforafrica_kenya_census"
    "opendataforafrica_rwanda_census"
    "school_finance"
    "school_retention"
    "singapore_census"
    "southkorea_statistics_demographics"
    "southkorea_statistics_education"
    "southkorea_statistics_employment"
    "southkorea_statistics_health"
    "statistics_new_zealand_new_zealand_census"
    "uae_bayanat"
    "us_bachelors_degree_data"
    "us_bls_cpi_category"
    "us_bls_us_cpi"
    "us_census"
    "us_federal_reserve_h15_interest_rates"
    "us_hbcu_data"
    "us_steam_degrees_data"
    "usa_dol"
)

# Initialize counters
TOTAL_DATASETS=${#DATASETS[@]}
SUCCESS_COUNT=0
FAILURE_COUNT=0
SKIPPED_COUNT=0

# Function to log with timestamp
log() {
    local message="$1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ${message}" | tee -a "${MAIN_LOG}"
}

# Function to log section separator
log_separator() {
    local sep="================================================================"
    echo "${sep}" | tee -a "${MAIN_LOG}"
}

# Start of script
log_separator
log "BATCH RUN STARTED"
log "Total datasets to process: ${TOTAL_DATASETS}"
log "Input directory: ${INPUT_DIR}"
log "Sleep duration between runs: ${SLEEP_DURATION} seconds"
log "Main log file: ${MAIN_LOG}"
log "Summary log file: ${SUMMARY_LOG}"
log_separator

# Process each dataset
for i in "${!DATASETS[@]}"; do
    DATASET="${DATASETS[$i]}"
    DATASET_NUM=$((i + 1))

    log_separator
    log "Processing dataset ${DATASET_NUM}/${TOTAL_DATASETS}: ${DATASET}"
    log_separator

    # Check if dataset exists in input directory
    if [ ! -d "${SCRIPT_DIR}/${INPUT_DIR}/${DATASET}" ]; then
        log "WARNING: Dataset directory not found: ${INPUT_DIR}/${DATASET}"
        log "Skipping..."
        ((SKIPPED_COUNT++))
        continue
    fi

    # Create per-dataset log file
    DATASET_LOG="${LOG_DIR}/dataset_${DATASET}_${TIMESTAMP}.log"

    # Run the pipeline
    log "Running pipeline for ${DATASET}..."
    log "Dataset log: ${DATASET_LOG}"

    START_TIME=$(date +%s)

    # Run pipeline and capture output to both dataset log and main log
    if python3 run_pvmap_pipeline.py \
        --dataset="${DATASET}" \
        --input-dir="${INPUT_DIR}" \
        2>&1 | tee -a "${DATASET_LOG}" | tee -a "${MAIN_LOG}"; then

        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        log "✅ SUCCESS: ${DATASET} completed in ${DURATION} seconds"
        ((SUCCESS_COUNT++))
    else
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        log "❌ FAILED: ${DATASET} failed after ${DURATION} seconds"
        log "Check dataset log for details: ${DATASET_LOG}"
        ((FAILURE_COUNT++))
    fi

    # Sleep between datasets (except after the last one)
    if [ ${DATASET_NUM} -lt ${TOTAL_DATASETS} ]; then
        log "Sleeping for ${SLEEP_DURATION} seconds before next dataset..."
        sleep ${SLEEP_DURATION}
    fi
done

# Final summary
log_separator
log "BATCH RUN COMPLETED"
log_separator
log "Total datasets: ${TOTAL_DATASETS}"
log "Successful: ${SUCCESS_COUNT}"
log "Failed: ${FAILURE_COUNT}"
log "Skipped: ${SKIPPED_COUNT}"
log_separator

# Calculate success rate
if [ ${TOTAL_DATASETS} -gt 0 ]; then
    SUCCESS_RATE=$((SUCCESS_COUNT * 100 / TOTAL_DATASETS))
    log "Success rate: ${SUCCESS_RATE}%"
fi

# Write summary to separate file
cat > "${SUMMARY_LOG}" <<EOF
PVMAP Pipeline Batch Run Summary
Generated: $(date)
=================================

Configuration:
  - Input Directory: ${INPUT_DIR}
  - Total Datasets: ${TOTAL_DATASETS}
  - Sleep Duration: ${SLEEP_DURATION} seconds
  - Start Time: $(date -r $(stat -f %B "${MAIN_LOG}") 2>/dev/null || echo "N/A")
  - End Time: $(date)

Results:
  - Successful: ${SUCCESS_COUNT}
  - Failed: ${FAILURE_COUNT}
  - Skipped: ${SKIPPED_COUNT}
  - Success Rate: ${SUCCESS_RATE}%

Datasets Processed:
EOF

# Add dataset list to summary
for DATASET in "${DATASETS[@]}"; do
    echo "  - ${DATASET}" >> "${SUMMARY_LOG}"
done

cat >> "${SUMMARY_LOG}" <<EOF

Logs:
  - Main Log: ${MAIN_LOG}
  - Summary: ${SUMMARY_LOG}
  - Individual Dataset Logs: ${LOG_DIR}/dataset_*_${TIMESTAMP}.log

To review results:
  - View main log: cat ${MAIN_LOG}
  - View summary: cat ${SUMMARY_LOG}
  - Search for failures: grep "FAILED" ${MAIN_LOG}
  - Search for successes: grep "SUCCESS" ${MAIN_LOG}
EOF

log "Summary written to: ${SUMMARY_LOG}"
log_separator

# Exit with appropriate code
if [ ${FAILURE_COUNT} -gt 0 ]; then
    exit 1
else
    exit 0
fi
