#!/bin/bash
# Small batch run of 5 datasets with gemini-3-pro-preview
# Generated: 2026-01-20

cd /Users/nehilsood/work/poc-auto-schematization
source venv/bin/activate

# List of 5 randomly selected datasets
DATASETS=(
    "brazil_sidra_ibge"
    "brfss_nchs_asthma_prevalence"
    "child_birth"
    "ireland_census"
    "us_bls_cpi_category"
)

LOG_FILE="logs/batch_run_5_$(date +%Y%m%d_%H%M%S).log"
echo "Starting small batch run of ${#DATASETS[@]} datasets" | tee "$LOG_FILE"
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
