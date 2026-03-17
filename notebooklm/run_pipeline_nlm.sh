#!/usr/bin/env bash
# run_pipeline_nlm.sh — Run the PVMAP pipeline with NotebookLM enrichment.
#
# Uses sample datasets from notebooklm/sample_data/ by default.
#
# Usage:
#   bash notebooklm/run_pipeline_nlm.sh                                    # Default dataset (bis)
#   bash notebooklm/run_pipeline_nlm.sh --dataset=census_v2_sahie          # Specific dataset
#   bash notebooklm/run_pipeline_nlm.sh --all                              # All 5 sample datasets
#   bash notebooklm/run_pipeline_nlm.sh --notebook-id=<ID>                 # Custom notebook
#   bash notebooklm/run_pipeline_nlm.sh --no-nlm                           # Run without NLM (baseline)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
NOTEBOOK_ID="3d07c6fa-9e36-43e8-91cd-bbc690f32e58"
DATASET=""
RUN_ALL=false
ENABLE_NLM=true
EXTRA_ARGS=""

# Sample datasets
SAMPLE_DATASETS=(
    "bis_bis_central_bank_policy_rate"
    "brfss_nchs_asthma_prevalence"
    "census_v2_sahie"
    "ccd_enrollment"
    "oecd_regional_education"
)

# Parse arguments
for arg in "$@"; do
    case $arg in
        --notebook-id=*)
            NOTEBOOK_ID="${arg#*=}"
            ;;
        --dataset=*)
            DATASET="${arg#*=}"
            ;;
        --all)
            RUN_ALL=true
            ;;
        --no-nlm)
            ENABLE_NLM=false
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $arg"
            ;;
    esac
done

# Auto-detect venv
if [ -d "$PROJECT_ROOT/.cloudtop_venv" ]; then
    VENV="$PROJECT_ROOT/.cloudtop_venv"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    VENV="$PROJECT_ROOT/.venv"
else
    echo "ERROR: No virtual environment found (.cloudtop_venv or .venv)"
    exit 1
fi

# Activate environment
source "$VENV/bin/activate"
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"

# Load .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Paths
INPUT_DIR="$SCRIPT_DIR/sample_data/input"
GT_DIR="$SCRIPT_DIR/sample_data/ground_truth"
OUTPUT_DIR="$PROJECT_ROOT/output"

echo "============================================================"
echo "PVMAP Pipeline with NotebookLM Enrichment"
echo "============================================================"
echo "Input dir:   $INPUT_DIR"
echo "GT dir:      $GT_DIR"
echo "Output dir:  $OUTPUT_DIR"
echo "NLM enabled: $ENABLE_NLM"
if [ "$ENABLE_NLM" = true ]; then
    echo "Notebook ID: $NOTEBOOK_ID"
fi
echo ""

# Verify Chrome CDP if NLM enabled
if [ "$ENABLE_NLM" = true ]; then
    if ! curl -s --max-time 2 http://localhost:9222/json/version > /dev/null 2>&1; then
        echo "WARNING: Chrome CDP not running on port 9222."
        echo "Run 'bash notebooklm/check_nlm.sh' first to set up the connection."
        echo "Continuing without NotebookLM..."
        ENABLE_NLM=false
    fi
fi

# Build datasets to process
if [ "$RUN_ALL" = true ]; then
    DATASETS=("${SAMPLE_DATASETS[@]}")
elif [ -n "$DATASET" ]; then
    DATASETS=("$DATASET")
else
    DATASETS=("bis_bis_central_bank_policy_rate")
fi

# Build common flags
NLM_FLAGS=""
if [ "$ENABLE_NLM" = true ]; then
    NLM_FLAGS="--enable-notebooklm --notebooklm-notebook-id=$NOTEBOOK_ID"
fi

# Results tracking
declare -A RESULTS

echo "Datasets to process: ${DATASETS[*]}"
echo "------------------------------------------------------------"

for ds in "${DATASETS[@]}"; do
    echo ""
    echo ">>> Processing: $ds"
    echo ""

    if python "$PROJECT_ROOT/src/run_pipeline.py" \
        --dataset="$ds" \
        --input-dir="$INPUT_DIR" \
        --output-dir="$OUTPUT_DIR" \
        --ground-truth-dir="$GT_DIR" \
        $NLM_FLAGS \
        $EXTRA_ARGS; then
        RESULTS[$ds]="PASS"
    else
        exit_code=$?
        if [ $exit_code -eq 2 ]; then
            RESULTS[$ds]="VALIDATION_FAIL"
        else
            RESULTS[$ds]="ERROR"
        fi
    fi
done

# Print summary
echo ""
echo "============================================================"
echo "RESULTS SUMMARY"
echo "============================================================"
printf "%-45s %s\n" "DATASET" "STATUS"
printf "%-45s %s\n" "-------" "------"
for ds in "${DATASETS[@]}"; do
    printf "%-45s %s\n" "$ds" "${RESULTS[$ds]:-UNKNOWN}"
done
echo "============================================================"
