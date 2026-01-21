#!/bin/bash
# Run all datasets with 30s cooldown, timeout handling using Gemini 3 Pro Preview

INPUT_DIR="/Users/nehilsood/work/poc-auto-schematization/input_benchmark"
OUTPUT_DIR="/Users/nehilsood/work/poc-auto-schematization/output_benchmark/gemini_3_pro_output"
GT_REPO="/Users/nehilsood/work/datacommonsorg-data/ground_truth"
VENV="/Users/nehilsood/work/poc-auto-schematization/venv/bin/activate"
SCRIPT="/Users/nehilsood/work/poc-auto-schematization/run_pvmap_pipeline.py"
LOG_FILE="/Users/nehilsood/work/poc-auto-schematization/logs/batch_run_$(date +%Y%m%d_%H%M%S).log"
MODEL="gemini-3-pro-preview"

# Timeout configuration
TIMEOUT_1=660   # 11 minutes for first attempt
TIMEOUT_2=900   # 15 minutes for retry attempt

cd /Users/nehilsood/work/poc-auto-schematization
source "$VENV"

# Count total datasets
total=$(ls -d "$INPUT_DIR"/*/ | wc -l | tr -d ' ')

echo "Starting batch run at $(date)" | tee -a "$LOG_FILE"
echo "Model: $MODEL" | tee -a "$LOG_FILE"
echo "Total datasets: $total" | tee -a "$LOG_FILE"
echo "Timeout: ${TIMEOUT_1}s first attempt, ${TIMEOUT_2}s retry" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

processed=0
skipped=0
failed=0
timeout_skipped=0
current=0

for dataset_path in "$INPUT_DIR"/*/; do
    dataset=$(basename "$dataset_path")
    ((current++))

    # Skip if already processed (check for generated_pvmap.csv)
    if [ -f "$OUTPUT_DIR/$dataset/generated_pvmap.csv" ]; then
        echo "[$current/$total] [$dataset] SKIPPED - already processed" | tee -a "$LOG_FILE"
        ((skipped++))
        continue
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "[$current/$total] [$dataset] Starting at $(date)" | tee -a "$LOG_FILE"

    # First attempt with 11 minute timeout
    echo "[$current/$total] [$dataset] Attempt 1/2 (timeout: ${TIMEOUT_1}s)" | tee -a "$LOG_FILE"
    gtimeout $TIMEOUT_1 python3 "$SCRIPT" \
        --input-dir=input_benchmark \
        --output-dir=output_benchmark/gemini_3_pro_output \
        --dataset="$dataset" \
        --ground-truth-repo="$GT_REPO" \
        --model="$MODEL" \
        2>&1 | tee -a "$LOG_FILE"

    exit_code=${PIPESTATUS[0]}

    if [ $exit_code -eq 0 ]; then
        echo "[$current/$total] [$dataset] SUCCESS" | tee -a "$LOG_FILE"
        ((processed++))
    elif [ $exit_code -eq 124 ]; then
        # Timeout occurred - clean partial output and retry
        echo "[$current/$total] [$dataset] TIMEOUT after ${TIMEOUT_1}s - cleaning and retrying..." | tee -a "$LOG_FILE"
        rm -rf "$OUTPUT_DIR/$dataset"

        # Retry with 15 minute timeout
        echo "[$current/$total] [$dataset] Attempt 2/2 (timeout: ${TIMEOUT_2}s)" | tee -a "$LOG_FILE"
        gtimeout $TIMEOUT_2 python3 "$SCRIPT" \
            --input-dir=input_benchmark \
            --output-dir=output_benchmark/gemini_3_pro_output \
            --dataset="$dataset" \
            --ground-truth-repo="$GT_REPO" \
            --model="$MODEL" \
            2>&1 | tee -a "$LOG_FILE"

        retry_exit_code=${PIPESTATUS[0]}

        if [ $retry_exit_code -eq 0 ]; then
            echo "[$current/$total] [$dataset] SUCCESS (on retry)" | tee -a "$LOG_FILE"
            ((processed++))
        elif [ $retry_exit_code -eq 124 ]; then
            echo "[$current/$total] [$dataset] TIMEOUT_SKIPPED - took too long, skipping" | tee -a "$LOG_FILE"
            rm -rf "$OUTPUT_DIR/$dataset"
            ((timeout_skipped++))
        else
            echo "[$current/$total] [$dataset] FAILED on retry (exit code: $retry_exit_code)" | tee -a "$LOG_FILE"
            ((failed++))
        fi
    else
        echo "[$current/$total] [$dataset] FAILED (exit code: $exit_code)" | tee -a "$LOG_FILE"
        ((failed++))
    fi

    echo "[$current/$total] Cooling down for 30 seconds..." | tee -a "$LOG_FILE"
    sleep 30
done

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "BATCH COMPLETE at $(date)" | tee -a "$LOG_FILE"
echo "Processed: $processed | Skipped: $skipped | Failed: $failed | Timeout-Skipped: $timeout_skipped | Total: $total" | tee -a "$LOG_FILE"
