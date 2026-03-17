#!/usr/bin/env bash
# =============================================================================
# NotebookLM Pipeline — Complete Cloudtop Setup & Run
# =============================================================================
#
# One script to set up everything on Cloudtop and run the PVMAP pipeline
# with NotebookLM enrichment. Handles all failures with clear instructions.
#
# Usage:
#   bash notebooklm/setup_and_run_cloudtop.sh
#   bash notebooklm/setup_and_run_cloudtop.sh --dataset=census_v2_sahie
#   bash notebooklm/setup_and_run_cloudtop.sh --all
#   bash notebooklm/setup_and_run_cloudtop.sh --fresh          # Force reinstall
#   bash notebooklm/setup_and_run_cloudtop.sh --no-nlm         # Skip NotebookLM
#   bash notebooklm/setup_and_run_cloudtop.sh --check-only     # Just verify setup
#
# Run from Cloudtop desktop (Chrome Remote Desktop via go/crd), NOT SSH.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_URL="https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git"
REPO_BRANCH="feature/nehil/notebooklm-agentb"
REPO_DIR="$HOME/work/poc-auto-schematization"
VENV_DIR="$REPO_DIR/.cloudtop_venv"
STORAGE_DIR="$HOME/.notebooklm"
STORAGE_STATE="$STORAGE_DIR/storage_state.json"
CDP_PORT=9222
PROFILE_DIR="/tmp/chrome-nlm-debug"
DEFAULT_NOTEBOOK="3d07c6fa-9e36-43e8-91cd-bbc690f32e58"

# Parse arguments
FRESH=false
CHECK_ONLY=false
ENABLE_NLM=true
DATASET=""
RUN_ALL=false
NOTEBOOK_ID="$DEFAULT_NOTEBOOK"
EXTRA_ARGS=""

for arg in "$@"; do
    case $arg in
        --fresh)             FRESH=true ;;
        --check-only)        CHECK_ONLY=true ;;
        --no-nlm)            ENABLE_NLM=false ;;
        --all)               RUN_ALL=true ;;
        --dataset=*)         DATASET="${arg#*=}" ;;
        --notebook-id=*)     NOTEBOOK_ID="${arg#*=}" ;;
        *)                   EXTRA_ARGS="$EXTRA_ARGS $arg" ;;
    esac
done

SAMPLE_DATASETS=(
    "bis_bis_central_bank_policy_rate"
    "brfss_nchs_asthma_prevalence"
    "census_v2_sahie"
    "ccd_enrollment"
    "oecd_regional_education"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
die()   { fail "$*"; exit 1; }

step_num=0
step() {
    step_num=$((step_num + 1))
    echo ""
    echo "================================================================"
    echo -e "${BLUE} Step $step_num: $*${NC}"
    echo "================================================================"
}

fix_hint() {
    echo ""
    echo -e "${YELLOW}  FIX:${NC} $*"
    echo ""
}

# ---------------------------------------------------------------------------
# Step 1: Check prerequisites
# ---------------------------------------------------------------------------

step "Checking prerequisites"

# Python 3.10+
if ! command -v python3 &>/dev/null; then
    fail "python3 not found"
    fix_hint "sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip"
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    die "Python 3.10+ required (found $PY_VERSION)"
fi
ok "Python $PY_VERSION"

# uv (optional but preferred)
HAS_UV=false
if command -v uv &>/dev/null; then
    HAS_UV=true
    ok "uv found"
else
    info "uv not found — will use pip instead"
    info "  (Install uv for faster deps: curl -LsSf https://astral.sh/uv/install.sh | sh)"
fi

# DISPLAY (needed for Chrome)
if [ -z "${DISPLAY:-}" ]; then
    fail "DISPLAY not set"
    fix_hint "Connect via Chrome Remote Desktop (go/crd), NOT SSH.
  If you're in CRD and DISPLAY is still empty, try:
    export DISPLAY=:20.0
  or check:
    echo \$DISPLAY"
    exit 1
fi
ok "DISPLAY=$DISPLAY"

# git
if ! command -v git &>/dev/null; then
    fail "git not found"
    fix_hint "sudo apt-get update && sudo apt-get install -y git"
    exit 1
fi
ok "git installed"

# curl (for CDP checks)
if ! command -v curl &>/dev/null; then
    fail "curl not found"
    fix_hint "sudo apt-get install -y curl"
    exit 1
fi
ok "curl installed"

# ---------------------------------------------------------------------------
# Step 2: Clone or update repo
# ---------------------------------------------------------------------------

step "Setting up repository"

if [ -d "$REPO_DIR/.git" ]; then
    info "Updating existing repo..."
    cd "$REPO_DIR"
    GIT_TERMINAL_PROMPT=0 git fetch origin "$REPO_BRANCH" 2>/dev/null || {
        warn "git fetch failed — maybe SSH keys? Trying HTTPS..."
        git remote set-url origin "$REPO_URL" 2>/dev/null || true
        GIT_TERMINAL_PROMPT=0 git fetch origin "$REPO_BRANCH" 2>/dev/null || {
            warn "Fetch failed. Continuing with current code."
        }
    }
    git checkout "$REPO_BRANCH" 2>/dev/null || true
    GIT_TERMINAL_PROMPT=0 git pull origin "$REPO_BRANCH" 2>/dev/null || {
        warn "Pull failed (maybe local changes). Continuing with current code."
    }
    ok "Repo updated at $REPO_DIR"
else
    info "Cloning repo..."
    mkdir -p "$(dirname "$REPO_DIR")"
    if ! GIT_TERMINAL_PROMPT=0 git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR" 2>/dev/null; then
        fail "git clone failed"
        fix_hint "Check your SSH key or gcert:
    gcert
    ssh -T git@github.com
  Or clone manually:
    git clone $REPO_URL $REPO_DIR
    cd $REPO_DIR && git checkout $REPO_BRANCH"
        exit 1
    fi
    cd "$REPO_DIR"
    ok "Repo cloned to $REPO_DIR"
fi

cd "$REPO_DIR"

# ---------------------------------------------------------------------------
# Step 3: Create venv and install deps
# ---------------------------------------------------------------------------

step "Setting up Python environment"

NEEDS_INSTALL=false

if [ "$FRESH" = true ]; then
    info "Fresh install requested — removing old venv..."
    rm -rf "$VENV_DIR"
    NEEDS_INSTALL=true
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    NEEDS_INSTALL=true
    rm -rf "$VENV_DIR" 2>/dev/null || true

    info "Creating virtual environment at $VENV_DIR..."
    if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
        warn "python3-venv not installed. Installing..."
        sudo apt-get update -qq && sudo apt-get install -y -qq "python${PY_VERSION}-venv" 2>/dev/null || \
            sudo apt-get install -y -qq python3-venv 2>/dev/null || {
            fail "Could not install python3-venv"
            fix_hint "sudo apt-get update && sudo apt-get install -y python${PY_VERSION}-venv"
            exit 1
        }
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR"
    fi
    ok "Venv created"
else
    ok "Venv exists at $VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Check if deps are installed
if [ "$NEEDS_INSTALL" = false ]; then
    if python3 -c "import pandas; import google.adk; import google.genai" 2>/dev/null; then
        ok "Pipeline dependencies already installed"
    else
        NEEDS_INSTALL=true
    fi
fi

if [ "$NEEDS_INSTALL" = true ]; then
    info "Installing pipeline dependencies (this may take a few minutes)..."

    # Install pip first if using venv pip
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip 2>/dev/null || true

    # Try uv first (much faster), fall back to pip
    if [ "$HAS_UV" = true ]; then
        info "Using uv for fast install..."
        if uv pip install -e ".[dev]" --python "$VENV_DIR/bin/python" 2>/dev/null; then
            ok "Dependencies installed via uv"
        else
            warn "uv install failed. Falling back to pip..."
            "$VENV_DIR/bin/pip" install -e ".[dev]" 2>/dev/null || {
                warn "Standard pip failed. Trying PyPI direct..."
                "$VENV_DIR/bin/pip" install --index-url https://pypi.org/simple/ -e ".[dev]" || {
                    fail "Dependency installation failed"
                    fix_hint "Try manually:
    source $VENV_DIR/bin/activate
    pip install -e '.[dev]'
  If behind corp proxy, try:
    pip install --index-url https://pypi.org/simple/ -e '.[dev]'"
                    exit 1
                }
            }
        fi
    else
        if "$VENV_DIR/bin/pip" install -e ".[dev]" 2>/dev/null; then
            ok "Dependencies installed via pip"
        else
            warn "Standard pip failed. Trying PyPI direct..."
            "$VENV_DIR/bin/pip" install --index-url https://pypi.org/simple/ -e ".[dev]" || {
                fail "Dependency installation failed"
                fix_hint "Try manually:
    source $VENV_DIR/bin/activate
    pip install -e '.[dev]'"
                exit 1
            }
        fi
    fi

    # Install notebooklm-py separately (not in pyproject.toml)
    if [ "$ENABLE_NLM" = true ]; then
        info "Installing notebooklm-py..."
        "$VENV_DIR/bin/pip" install --quiet "notebooklm-py[browser]" nest-asyncio 2>/dev/null || {
            warn "notebooklm-py install failed. Trying PyPI direct..."
            "$VENV_DIR/bin/pip" install --index-url https://pypi.org/simple/ --quiet "notebooklm-py[browser]" nest-asyncio || {
                warn "Could not install notebooklm-py — disabling NLM enrichment"
                ENABLE_NLM=false
            }
        }
        if [ "$ENABLE_NLM" = true ]; then
            ok "notebooklm-py installed"
        fi
    fi
fi

# Set up .env if it doesn't exist
if [ ! -f "$REPO_DIR/.env" ]; then
    info "No .env file found. Creating template..."
    cat > "$REPO_DIR/.env" << 'ENVEOF'
# Gemini API key (REQUIRED for pipeline)
# Get one at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your-key-here

# Anthropic API key (optional, for Claude Code integration)
# ANTHROPIC_API_KEY=your-key-here
ENVEOF
    warn ".env created at $REPO_DIR/.env"
    warn "Edit it to add your GEMINI_API_KEY before running the pipeline!"
fi

# ---------------------------------------------------------------------------
# Step 4: Start Chrome with CDP (for NotebookLM)
# ---------------------------------------------------------------------------

if [ "$ENABLE_NLM" = true ]; then

    step "Starting Chrome with CDP (port $CDP_PORT)"

    if curl -s --max-time 2 "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
        BROWSER=$(curl -s "http://localhost:$CDP_PORT/json/version" | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('Browser','Chrome'))" 2>/dev/null || echo "Chrome")
        ok "Chrome already running with CDP ($BROWSER)"
    else
        info "Starting Chrome with remote debugging..."

        # Kill existing Chrome (NOT Chrome Remote Desktop)
        pkill -9 -f "google-chrome" 2>/dev/null || true
        pkill -9 -f "chromium-browser" 2>/dev/null || true
        pkill -9 -f "chromium " 2>/dev/null || true
        sleep 2

        # Check port is free
        if ss -tlnp 2>/dev/null | grep -q ":$CDP_PORT "; then
            info "Port $CDP_PORT still busy, waiting 3s..."
            sleep 3
            if ss -tlnp 2>/dev/null | grep -q ":$CDP_PORT "; then
                fail "Port $CDP_PORT is blocked"
                fix_hint "Find what's using it:
    ss -tlnp | grep $CDP_PORT
  Kill it:
    fuser -k $CDP_PORT/tcp"
                exit 1
            fi
        fi

        # Find Chrome
        CHROME_BIN=""
        for candidate in google-chrome google-chrome-stable chromium-browser chromium; do
            if command -v "$candidate" &>/dev/null; then
                CHROME_BIN="$candidate"
                break
            fi
        done
        if [ -z "$CHROME_BIN" ]; then
            fail "No Chrome/Chromium found"
            fix_hint "Install Chrome:
    sudo apt-get install -y google-chrome-stable
  Or chromium:
    sudo apt-get install -y chromium-browser"
            exit 1
        fi

        info "Using: $CHROME_BIN"
        "$CHROME_BIN" \
            --remote-debugging-port="$CDP_PORT" \
            --user-data-dir="$PROFILE_DIR" \
            --no-first-run \
            --no-default-browser-check \
            "https://notebooklm.google.com/" &>/dev/null &

        # Wait for CDP
        CHROME_OK=false
        for i in $(seq 1 15); do
            if curl -s --max-time 2 "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
                CHROME_OK=true
                ok "Chrome started (took ${i}s)"
                break
            fi
            sleep 1
        done

        if [ "$CHROME_OK" = false ]; then
            warn "Chrome didn't start in 15s. Retrying with --disable-gpu..."
            "$CHROME_BIN" \
                --remote-debugging-port="$CDP_PORT" \
                --user-data-dir="$PROFILE_DIR" \
                --no-first-run \
                --no-default-browser-check \
                --disable-gpu \
                "https://notebooklm.google.com/" &>/dev/null &
            sleep 5

            if ! curl -s --max-time 2 "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
                fail "Chrome failed to start with remote debugging"
                fix_hint "Try manually:
    $CHROME_BIN --remote-debugging-port=$CDP_PORT --user-data-dir=$PROFILE_DIR https://notebooklm.google.com/
  Check for errors:
    $CHROME_BIN --remote-debugging-port=$CDP_PORT --user-data-dir=$PROFILE_DIR 2>&1 | head -20"
                exit 1
            fi
            ok "Chrome started with --disable-gpu"
        fi
    fi

    # -----------------------------------------------------------------------
    # Step 5: Authenticate / refresh cookies
    # -----------------------------------------------------------------------

    step "Checking NotebookLM authentication"

    NEED_SIGNIN=false
    if [ "$FRESH" = true ]; then
        NEED_SIGNIN=true
    elif [ ! -f "$STORAGE_STATE" ]; then
        NEED_SIGNIN=true
        info "No stored cookies found"
    else
        info "Refreshing cookies from Chrome..."
        if python3 "$REPO_DIR/notebooklm/refresh_cookies.py" 2>/dev/null; then
            if python3 -c "
import json
state = json.load(open('$STORAGE_STATE'))
names = {c['name'] for c in state.get('cookies', [])}
exit(0 if 'SID' in names else 1)
" 2>/dev/null; then
                ok "Valid auth cookies found"
            else
                NEED_SIGNIN=true
                warn "Cookies found but missing SID — need fresh sign-in"
            fi
        else
            NEED_SIGNIN=true
            warn "Cookie refresh failed"
        fi
    fi

    if [ "$NEED_SIGNIN" = true ]; then
        echo ""
        echo "  =============================================="
        echo "  ACTION REQUIRED: Sign in to NotebookLM"
        echo "  =============================================="
        echo ""
        echo "  A Chrome window should be open on the Cloudtop desktop."
        echo "    1. Sign in with your @google.com account"
        echo "    2. Tap your security key when prompted"
        echo "    3. Wait until NotebookLM loads fully"
        echo ""
        echo "  If security key fails ('Error: 512'):"
        echo "    bash notebooklm/fix_gnubby.sh"
        echo "    Then come back and sign in."
        echo ""
        read -rp "  Press ENTER after you've signed in... "
        echo ""

        info "Extracting cookies from Chrome..."
        if ! python3 "$REPO_DIR/notebooklm/refresh_cookies.py"; then
            fail "Cookie extraction failed"
            fix_hint "Make sure you're signed into notebooklm.google.com in Chrome.
  Check Chrome is on the right page:
    curl -s http://localhost:$CDP_PORT/json | python3 -c 'import sys,json; [print(t[\"url\"]) for t in json.load(sys.stdin)]'"
            exit 1
        fi
        ok "Authentication successful"
    fi

    # -----------------------------------------------------------------------
    # Step 5b: Test NotebookLM connection
    # -----------------------------------------------------------------------

    info "Testing NotebookLM connection..."
    export PYTHONPATH="$REPO_DIR:$REPO_DIR/src"

    NLM_TEST_OK=false
    if python3 -c "
import asyncio, sys
sys.path.insert(0, '$REPO_DIR')
from notebooklm.tools import ask_question, shutdown_client

async def test():
    result = await ask_question('$NOTEBOOK_ID', 'What is Data Commons?')
    await shutdown_client()
    if result['success']:
        print(f'Got {len(result[\"data\"].get(\"answer\", \"\"))} char response')
        return True
    else:
        print(f'Error: {result[\"error\"]}')
        return False

ok = asyncio.run(test())
sys.exit(0 if ok else 1)
" 2>/dev/null; then
        ok "NotebookLM connection verified"
        NLM_TEST_OK=true
    else
        warn "NotebookLM test query failed."
        warn "Continuing without NLM enrichment (pipeline will still work)."
        ENABLE_NLM=false
    fi

fi  # end ENABLE_NLM block

# ---------------------------------------------------------------------------
# Step 6: Check .env has a real Gemini API key
# ---------------------------------------------------------------------------

step "Checking Gemini API key"

if [ -f "$REPO_DIR/.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

if [ -z "${GEMINI_API_KEY:-}" ] || [ "$GEMINI_API_KEY" = "your-key-here" ]; then
    fail "GEMINI_API_KEY not set or still has placeholder value"
    fix_hint "Edit $REPO_DIR/.env and set your Gemini API key:
    nano $REPO_DIR/.env
  Get a key at: https://aistudio.google.com/app/apikey"
    exit 1
fi
ok "GEMINI_API_KEY is set (${#GEMINI_API_KEY} chars)"

# ---------------------------------------------------------------------------
# Check-only mode: stop here
# ---------------------------------------------------------------------------

if [ "$CHECK_ONLY" = true ]; then
    echo ""
    echo "================================================================"
    echo -e "${GREEN} All checks passed! Setup is ready.${NC}"
    echo "================================================================"
    echo ""
    echo "  Python:      $(python3 --version)"
    echo "  Venv:        $VENV_DIR"
    echo "  Repo:        $REPO_DIR"
    echo "  Branch:      $(git branch --show-current)"
    echo "  NLM:         $([ "$ENABLE_NLM" = true ] && echo "enabled" || echo "disabled")"
    echo "  Notebook:    $NOTEBOOK_ID"
    echo ""
    echo "  To run the pipeline:"
    echo "    bash notebooklm/setup_and_run_cloudtop.sh --dataset=bis_bis_central_bank_policy_rate"
    echo ""
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 7: Run the pipeline
# ---------------------------------------------------------------------------

step "Running PVMAP pipeline"

export PYTHONPATH="$REPO_DIR:$REPO_DIR/src"

# Determine datasets
if [ "$RUN_ALL" = true ]; then
    DATASETS=("${SAMPLE_DATASETS[@]}")
elif [ -n "$DATASET" ]; then
    DATASETS=("$DATASET")
else
    DATASETS=("bis_bis_central_bank_policy_rate")
fi

# Build NLM flags
NLM_FLAGS=""
if [ "$ENABLE_NLM" = true ]; then
    NLM_FLAGS="--enable-notebooklm --notebooklm-notebook-id=$NOTEBOOK_ID"
fi

INPUT_DIR="$REPO_DIR/notebooklm/sample_data/input"
GT_DIR="$REPO_DIR/notebooklm/sample_data/ground_truth"
OUTPUT_DIR="$REPO_DIR/output"

mkdir -p "$OUTPUT_DIR"

echo ""
echo "  Datasets:     ${DATASETS[*]}"
echo "  Input dir:    $INPUT_DIR"
echo "  GT dir:       $GT_DIR"
echo "  Output dir:   $OUTPUT_DIR"
echo "  NLM:          $([ "$ENABLE_NLM" = true ] && echo "ENABLED (notebook: $NOTEBOOK_ID)" || echo "DISABLED")"
echo ""

declare -A RESULTS
declare -A TIMINGS

for ds in "${DATASETS[@]}"; do
    echo ""
    echo "------------------------------------------------------------"
    echo ">>> Processing: $ds"
    echo "------------------------------------------------------------"
    echo ""

    START_TIME=$(date +%s)

    if python3 "$REPO_DIR/src/run_pipeline.py" \
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
            RESULTS[$ds]="ERROR (exit $exit_code)"
        fi
    fi

    END_TIME=$(date +%s)
    TIMINGS[$ds]=$(( END_TIME - START_TIME ))
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "================================================================"
echo -e "${BLUE} RESULTS SUMMARY${NC}"
echo "================================================================"
printf "%-42s %-18s %s\n" "DATASET" "STATUS" "TIME"
printf "%-42s %-18s %s\n" "-------" "------" "----"
for ds in "${DATASETS[@]}"; do
    STATUS="${RESULTS[$ds]:-UNKNOWN}"
    TIME="${TIMINGS[$ds]:-?}s"
    if [ "$STATUS" = "PASS" ]; then
        COLOR="$GREEN"
    else
        COLOR="$RED"
    fi
    printf "%-42s ${COLOR}%-18s${NC} %s\n" "$ds" "$STATUS" "$TIME"
done
echo "================================================================"
echo ""
echo "Output artifacts: $OUTPUT_DIR/<dataset_name>/"
echo ""

# Check if any failed
ANY_FAIL=false
for ds in "${DATASETS[@]}"; do
    if [ "${RESULTS[$ds]:-}" != "PASS" ]; then
        ANY_FAIL=true
    fi
done

if [ "$ANY_FAIL" = true ]; then
    echo -e "${YELLOW}Some datasets failed. Check logs:${NC}"
    echo "  tail -100 $OUTPUT_DIR/logs/*.log"
    echo "  cat $OUTPUT_DIR/<dataset>/generation_notes.md"
    exit 2
fi

echo -e "${GREEN}All datasets passed!${NC}"
