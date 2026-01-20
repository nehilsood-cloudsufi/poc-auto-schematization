#!/bin/bash
# Batch run of 12 datasets (2 retry + 10 new) with gemini-3-pro-preview
# Generated: 2026-01-20

cd /Users/nehilsood/work/poc-auto-schematization
source venv/bin/activate

# 2 failed datasets to retry + 10 new datasets
DATASETS=(
    "brazil_sidra_ibge"
    "ireland_census"
    "us_bachelors_degree_data"
    "opendataforafrica_ethiopia_statistics"
    "oecd_quarterly_gdp"
    "ncses_research_doctorate_recipients"
    "fema"
    "southkorea_statistics_employment"
    "opendataforafrica_rwanda_census"
    "fao_currency_and_exchange_rate"
    "ntia_internet_use_survey"
    "southkorea_statistics_education"
)

LOG_FILE="logs/batch_run_12_$(date +%Y%m%d_%H%M%S).log"
echo "Starting batch run of ${#DATASETS[@]} datasets with gemini-3-pro-preview" | tee "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Start time: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

SUCCESSFUL=0
FAILED=0

for i in "${!DATASETS[@]}"; do
    DATASET="${DATASETS[$i]}"
    NUM=$((i + 1))
    
    # Delete existing output folder for retry datasets
    if [ -d "output/gemini_output/$DATASET" ]; then
        echo "[$NUM] Removing existing output for retry: $DATASET" | tee -a "$LOG_FILE"
        rm -rf "output/gemini_output/$DATASET"
    fi
    
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
