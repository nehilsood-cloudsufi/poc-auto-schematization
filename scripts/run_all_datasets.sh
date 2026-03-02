#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Batch runner for all datasets in input/
#
# Starts MCP server once, runs run_pipeline.py for each dataset with:
#   --enable-mcp --force-resample --force-schema-selection
#
# Usage:
#   scripts/run_all_datasets.sh                # Full run (smoke + remaining)
#   scripts/run_all_datasets.sh --smoke-only   # Only 2 smoke-test datasets
#   scripts/run_all_datasets.sh --skip-smoke   # Skip smoke, run remaining only
#   scripts/run_all_datasets.sh --datasets "bis_bis_central_bank_policy_rate brfss_nchs_asthma_prevalence"
#
# Environment variables:
#   MCP_PORT   - MCP server port (default: 3000)
#   MODEL      - Gemini model name (default: gemini-3.1-pro-preview)
#   OUTPUT_DIR - Override output directory (default: output/batch_<timestamp>)
# =============================================================================

# --- Config ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INPUT_DIR="${PROJECT_ROOT}/input"
MCP_PORT="${MCP_PORT:-3000}"
MODEL="${MODEL:-gemini-3.1-pro-preview}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BATCH_OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_ROOT}/output/batch_${TIMESTAMP}}"
RESULTS_FILE="${BATCH_OUTPUT_DIR}/batch_results.txt"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"

SMOKE_DATASETS=("bis_bis_central_bank_policy_rate" "brfss_nchs_asthma_prevalence")

# --- Parse flags ---
SMOKE_ONLY=false
SKIP_SMOKE=false
CUSTOM_DATASETS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --smoke-only)  SMOKE_ONLY=true; shift ;;
        --skip-smoke)  SKIP_SMOKE=true; shift ;;
        --datasets)    CUSTOM_DATASETS="$2"; shift 2 ;;
        --output-dir)  BATCH_OUTPUT_DIR="$2"; RESULTS_FILE="${BATCH_OUTPUT_DIR}/batch_results.txt"; shift 2 ;;
        *)             echo "Unknown flag: $1"; exit 1 ;;
    esac
done

# --- Counters ---
TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0
declare -a PASS_LIST=()
declare -a FAIL_LIST=()

# --- MCP Server Management ---
MCP_PID=""

start_mcp_server() {
    echo "=== Starting MCP server on port ${MCP_PORT} ==="

    # Check if already running
    if curl -sf "http://localhost:${MCP_PORT}/health" > /dev/null 2>&1; then
        echo "MCP server already running on port ${MCP_PORT}"
        return 0
    fi

    # Find executable
    local dc_mcp_cmd="${PROJECT_ROOT}/.venv/bin/datacommons-mcp"
    if [[ ! -x "$dc_mcp_cmd" ]]; then
        dc_mcp_cmd="datacommons-mcp"
    fi

    "$dc_mcp_cmd" serve http --port "$MCP_PORT" > /dev/null 2>&1 &
    MCP_PID=$!
    echo "MCP server PID: ${MCP_PID}"

    # Health check loop (max 30s)
    local elapsed=0
    while [[ $elapsed -lt 30 ]]; do
        if ! kill -0 "$MCP_PID" 2>/dev/null; then
            echo "ERROR: MCP server process died"
            MCP_PID=""
            return 1
        fi
        if curl -sf "http://localhost:${MCP_PORT}/health" > /dev/null 2>&1; then
            echo "MCP server healthy after ${elapsed}s"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "ERROR: MCP server failed to start within 30s"
    stop_mcp_server
    return 1
}

stop_mcp_server() {
    if [[ -n "$MCP_PID" ]] && kill -0 "$MCP_PID" 2>/dev/null; then
        echo "=== Stopping MCP server (PID ${MCP_PID}) ==="
        kill "$MCP_PID" 2>/dev/null || true
        wait "$MCP_PID" 2>/dev/null || true
        MCP_PID=""
    fi
}

trap stop_mcp_server EXIT INT TERM

# --- Pre-flight checks ---
preflight() {
    echo "=== Pre-flight checks ==="

    if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
        echo "WARNING: .env file not found — API keys must be set in environment"
    fi

    if [[ ! -x "$PYTHON" ]]; then
        echo "ERROR: Python not found at ${PYTHON}"
        echo "       Run: uv sync"
        exit 1
    fi

    if [[ ! -d "$INPUT_DIR" ]]; then
        echo "ERROR: Input directory not found: ${INPUT_DIR}"
        exit 1
    fi

    local dataset_count
    dataset_count=$(ls -d "${INPUT_DIR}"/*/ 2>/dev/null | wc -l | tr -d ' ')
    echo "Found ${dataset_count} datasets in ${INPUT_DIR}"
    echo "Output directory: ${BATCH_OUTPUT_DIR}"
    echo "Model: ${MODEL}"
    echo ""
}

# --- Run one dataset ---
run_one_dataset() {
    local dataset="$1"
    local dataset_output_dir="${BATCH_OUTPUT_DIR}/${dataset}"
    local log_file="${dataset_output_dir}/run.log"

    mkdir -p "$dataset_output_dir"

    TOTAL=$((TOTAL + 1))
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[${TOTAL}] Running: ${dataset}"
    echo "    Log: ${log_file}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local start_time
    start_time=$(date +%s)

    # Run pipeline — continue on failure
    set +e
    PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/src" "$PYTHON" \
        "${PROJECT_ROOT}/src/run_pipeline.py" \
        --dataset="$dataset" \
        --output-dir="$BATCH_OUTPUT_DIR" \
        --enable-mcp \
        --mcp-port="$MCP_PORT" \
        --force-resample \
        --force-schema-selection \
        --model="$MODEL" \
        > "$log_file" 2>&1
    local exit_code=$?
    set -e

    local end_time
    end_time=$(date +%s)
    local duration=$(( end_time - start_time ))

    local status
    if [[ $exit_code -eq 0 ]]; then
        status="PASS"
        PASSED=$((PASSED + 1))
        PASS_LIST+=("$dataset")
        echo "    Result: PASS (${duration}s)"
    elif [[ $exit_code -eq 2 ]]; then
        status="FAIL-VAL"
        FAILED=$((FAILED + 1))
        FAIL_LIST+=("$dataset")
        echo "    Result: FAIL-VALIDATION (${duration}s)"
        echo "    --- key log lines ---"
        grep -E 'Generation success|Validation passed|Pipeline failed' "$log_file" 2>/dev/null | tail -5 | sed 's/^/    /'
        echo "    ---"
    else
        status="FAIL-ERR"
        FAILED=$((FAILED + 1))
        FAIL_LIST+=("$dataset")
        echo "    Result: FAIL-CRASH (exit ${exit_code}, ${duration}s)"
        echo "    --- key log lines ---"
        grep -E 'Generation success|Validation passed|Pipeline failed' "$log_file" 2>/dev/null | tail -5 | sed 's/^/    /'
        echo "    ---"
    fi

    # Append to results file
    printf "%-60s %-8s %4ds  exit=%d\n" "$dataset" "$status" "$duration" "$exit_code" >> "$RESULTS_FILE"
}

# --- Print summary table ---
print_summary() {
    echo ""
    echo "============================================================"
    echo "                    BATCH RUN SUMMARY"
    echo "============================================================"
    echo "Output directory: ${BATCH_OUTPUT_DIR}"
    echo "Total: ${TOTAL}  |  Passed: ${PASSED}  |  Failed: ${FAILED}  |  Skipped: ${SKIPPED}"
    echo ""

    if [[ ${#FAIL_LIST[@]} -gt 0 ]]; then
        echo "--- FAILED datasets ---"
        for d in ${FAIL_LIST[@]+"${FAIL_LIST[@]}"}; do
            echo "  - $d"
        done
        echo ""
    fi

    if [[ ${#PASS_LIST[@]} -gt 0 ]]; then
        echo "--- PASSED datasets ---"
        for d in ${PASS_LIST[@]+"${PASS_LIST[@]}"}; do
            echo "  - $d"
        done
        echo ""
    fi

    echo "Full results: ${RESULTS_FILE}"
    echo "============================================================"

    # Also append summary to results file
    {
        echo ""
        echo "============================================================"
        echo "Total: ${TOTAL}  |  Passed: ${PASSED}  |  Failed: ${FAILED}  |  Skipped: ${SKIPPED}"
        echo "============================================================"
    } >> "$RESULTS_FILE"
}

# =============================================================================
# Main
# =============================================================================

preflight

mkdir -p "$BATCH_OUTPUT_DIR"

# Write results header
{
    echo "Batch run: ${TIMESTAMP}"
    echo "Model: ${MODEL}"
    echo "Output: ${BATCH_OUTPUT_DIR}"
    echo "------------------------------------------------------------"
    printf "%-60s %-8s %5s  %s\n" "DATASET" "STATUS" "TIME" "EXIT"
    echo "------------------------------------------------------------"
} > "$RESULTS_FILE"

# Start MCP server
if ! start_mcp_server; then
    echo "FATAL: Cannot start MCP server. Aborting."
    exit 1
fi

# --- Custom dataset list ---
if [[ -n "$CUSTOM_DATASETS" ]]; then
    for dataset in $CUSTOM_DATASETS; do
        if [[ -d "${INPUT_DIR}/${dataset}" ]]; then
            run_one_dataset "$dataset"
        else
            echo "WARNING: Dataset not found: ${dataset} — skipping"
            SKIPPED=$((SKIPPED + 1))
        fi
    done
    print_summary
    exit 0
fi

# --- Phase 1: Smoke test ---
if [[ "$SKIP_SMOKE" == false ]]; then
    echo ""
    echo "============================================================"
    echo "  Phase 1: Smoke Test (${#SMOKE_DATASETS[@]} datasets)"
    echo "============================================================"

    for dataset in "${SMOKE_DATASETS[@]}"; do
        if [[ -d "${INPUT_DIR}/${dataset}" ]]; then
            run_one_dataset "$dataset"
        else
            echo "WARNING: Smoke dataset not found: ${dataset}"
            SKIPPED=$((SKIPPED + 1))
        fi
    done

    # Check smoke results — abort only on crashes (exit 1), not validation failures (exit 2)
    crash_count=0
    for d in ${FAIL_LIST[@]+"${FAIL_LIST[@]}"}; do
        smoke_log="${BATCH_OUTPUT_DIR}/${d}/run.log"
        # Check if this was a crash (exit 1) vs validation failure (exit 2)
        if grep -q "Pipeline failed" "$smoke_log" 2>/dev/null; then
            crash_count=$((crash_count + 1))
        fi
    done

    if [[ $crash_count -gt 0 ]]; then
        echo ""
        echo "FATAL: ${crash_count} smoke-test dataset(s) crashed. Aborting batch."
        echo "       Check logs in ${BATCH_OUTPUT_DIR}/"
        print_summary
        exit 1
    fi

    echo ""
    echo "Smoke test: ${PASSED} passed, ${FAILED} validation failures, ${crash_count} crashes. Continuing..."
fi

# --- Phase 2: Remaining datasets ---
if [[ "$SMOKE_ONLY" == false ]]; then
    echo ""
    echo "============================================================"
    echo "  Phase 2: Remaining Datasets"
    echo "============================================================"

    for dataset_dir in "${INPUT_DIR}"/*/; do
        dataset_name=$(basename "$dataset_dir")

        # Skip smoke-test datasets if we already ran them
        if [[ "$SKIP_SMOKE" == false ]]; then
            local_skip=false
            for s in "${SMOKE_DATASETS[@]}"; do
                if [[ "$dataset_name" == "$s" ]]; then
                    local_skip=true
                    break
                fi
            done
            if [[ "$local_skip" == true ]]; then
                continue
            fi
        fi

        run_one_dataset "$dataset_name"
    done
fi

print_summary
