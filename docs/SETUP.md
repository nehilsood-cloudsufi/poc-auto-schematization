# Setup Guide

This guide walks you through setting up the PVMAP Pipeline environment from scratch.

## Prerequisites

Before starting, ensure you have:
- **Python 3.12 or higher** installed
- **Git** installed
- A **Gemini API key** (required for LLM calls via Google ADK)
- **uv** package manager ([installation guide](https://github.com/astral-sh/uv))

**Optional:**
- **Data Commons API key** (for MCP integration)
- **Claude Code CLI** (for development assistance only — the pipeline itself uses Google ADK + Gemini)

### Verify Prerequisites

```bash
# Check Python version (should be 3.12+)
python3 --version

# Check Git
git --version

# Check uv
uv --version
```

---

## Installation Steps

### 1. Clone the Repository

```bash
# Navigate to your workspace directory
cd ~/work  # or your preferred location

# Clone this repository
git clone <repository-url> poc-auto-schematization
cd poc-auto-schematization
```

### 2. Install Python Dependencies

Dependencies are managed via `pyproject.toml` and installed with `uv`:

```bash
# Install uv package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install all dependencies (including dev extras)
uv sync --all-extras

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
.venv\Scripts\activate     # On Windows
```

**Key dependencies installed:**
- `google-adk` — Google Agent Development Kit (pipeline orchestration)
- `google-genai` — Gemini API client (LLM calls)
- `streamlit>=1.44.0` — Web UI for interactive pipeline runs
- `pandas`, `datacommons` — Data processing and DC API
- `gcsfs`, `google-cloud-logging` — Cloud Run support
- `datacommons-mcp` — MCP server for StatVar discovery

### 3. Set Up Environment Variables

Create a `.env` file in the project root. The pipeline loads `.env` first, and these values take priority over shell environment variables.

```bash
# Create .env file
cat > .env << 'EOF'
# Required
GEMINI_API_KEY=your-gemini-api-key-here

# Optional - Data Commons MCP integration
DC_API_KEY=your-dc-api-key-here

# Optional - Google Maps API for place resolution
MAPS_API_KEY=your-maps-api-key-here
EOF
```

Alternatively, export environment variables directly:

```bash
# Required
export GEMINI_API_KEY="your-gemini-api-key-here"

# Required for module imports
export PYTHONPATH="$(pwd):$(pwd)/src"
```

### 4. Verify Installation

```bash
# Test that key packages are installed
python -c "import pandas, google.adk, google.genai; print('Setup successful!')"

# Verify ADK is available
python -c "from google.adk.agents import LlmAgent; print('Google ADK ready')"

# Run the test suite (optional)
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```

---

## Set Up Python Path (CRITICAL)

The pipeline requires access to source modules. You **must** set the Python path:

```bash
# Export PYTHONPATH (required for every session)
export PYTHONPATH="$(pwd):$(pwd)/src"

# Verify you're in the project directory first
pwd  # Should show: /path/to/poc-auto-schematization

# Or add this to your shell profile for persistence
echo 'export PYTHONPATH="$PWD:$PWD/src"' >> ~/.zshrc
source ~/.zshrc
```

**Warning:** This is the #1 cause of `ModuleNotFoundError` errors.

### Verify PYTHONPATH

```bash
# Check that PYTHONPATH is set correctly
echo $PYTHONPATH  # Should include project root and src/ directory
```

---

## Verify Repository Structure

Your repository should have this structure:

```
poc-auto-schematization/
├── src/                          # Source code
│   ├── agents/                   # Google ADK agents (pipeline orchestration)
│   ├── config/                   # CLI configuration
│   ├── state/                    # State management
│   ├── infrastructure/           # Core utilities (io, config, metrics, logging)
│   ├── data_commons/             # Data Commons modules (api, mcf, schema, place, codes)
│   ├── pipeline/                 # Pipeline operations (sampling, validation, evaluation)
│   ├── processing/               # Data processing (mapping, filtering, transformation)
│   ├── tools/                    # ADK tool wrappers
│   ├── ui/                       # Streamlit web UI
│   ├── utils/                    # Shared utilities (artifact_plugin, template_utils)
│   └── resources/                # Static resources (prompts, schema_examples, schema_org)
├── tests/                        # Test suite (~982 tests)
├── input/                        # Datasets with input data & metadata
├── output/                       # Generated PVMAPs (created automatically)
├── ground_truth/                 # Ground truth PVMAPs for evaluation
├── deploy/                       # Cloud Run deployment scripts
├── tools/                        # Legacy processing tools (compatibility layer)
├── logs/                         # Pipeline logs (created automatically)
├── Dockerfile                    # Container image for Cloud Run
├── pyproject.toml                # Dependency definitions (source of truth)
├── src/run_pipeline.py           # Main pipeline script (ADK-based)
└── README.md                     # Main documentation
```

---

## Environment Variables Reference

### Required

| Variable | Purpose | Example |
|----------|---------|---------|
| `GEMINI_API_KEY` | Gemini API authentication (loaded from `.env` first) | `AIza...` |
| `PYTHONPATH` | Module import resolution | `$(pwd):$(pwd)/src` |

### Optional — Pipeline Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `GROUND_TRUTH_REPO` | Ground truth directory | `ground_truth/` |
| `DC_API_KEY` | Data Commons API for MCP integration | — |
| `MAPS_API_KEY` | Google Maps API for place resolution | — |
| `SAMPLING_AGENT_MODEL` | Override model for sampling agent | `gemini-3.1-pro-preview` |
| `PVMAP_GENERATOR_MODEL` | Override model for PVMAP generator | `gemini-3.1-pro-preview` |
| `FEEDBACK_AGENT_MODEL` | Override model for feedback agent | `gemini-3.1-pro-preview` |
| `DC_AGENT_MODEL` | Override model for DC query/MCP agents | `gemini-3-flash-preview` |
| `STATVAR_DISCOVERY_MODEL` | Override model for StatVar discovery | `gemini-3-flash-preview` |
| `SCHEMA_SELECTION_MODEL` | Override model for schema selection | `gemini-2.5-pro` |
| `METADATA_AGENT_MODEL` | Override model for metadata agent | `gemini-2.5-pro` |
| `PIPELINE_MODEL` | Override default model for coordinator | `gemini-3.1-pro-preview` |
| `PROMPT_VERSION` | PVMAP prompt template version | `v2` |
| `PER_ATTEMPT_TIMEOUT` | Timeout per pipeline attempt (seconds) | `300` |

### Optional — Cloud Run / UI

| Variable | Purpose | Default |
|----------|---------|---------|
| `UI_OUTPUT_DIR` | Output directory for UI runs | `ui_output` |
| `GCS_BUCKET` | GCS bucket for Cloud Run output | — |
| `MCP_PORT` | Port for DC MCP server | `3000` |
| `K_SERVICE` | Auto-set by Cloud Run (enables cloud logging) | — |
| `GOOGLE_SHEET_ID` | Google Sheet ID for developer feedback | — |

---

## Verification Checklist

Before running the pipeline, verify:

- [ ] Python 3.12+ installed (`python3 --version`)
- [ ] Virtual environment activated (`which python` shows `.venv` path)
- [ ] Dependencies installed (`python -c "import pandas, google.adk, google.genai"`)
- [ ] GEMINI_API_KEY set (`.env` file or `echo $GEMINI_API_KEY | head -c 10`)
- [ ] PYTHONPATH configured (`echo $PYTHONPATH`)
- [ ] Repository structure correct (`ls input/ output/ src/ tests/`)

---

## Next Steps

Once setup is complete:

1. **Review Input Structure** - See [INPUT_GUIDE.md](INPUT_GUIDE.md) to understand how to structure your datasets
2. **Run Your First Pipeline** - See [USAGE.md](USAGE.md) for quick start and usage instructions
3. **Deploy to Cloud Run** - See [DEPLOYMENT.md](DEPLOYMENT.md) for Cloud Run setup
4. **Troubleshooting** - If you encounter issues, see [APPENDIX.md](APPENDIX.md#a-detailed-troubleshooting-guide)

---

## Quick Troubleshooting

### Issue: ModuleNotFoundError for 'file_util'

```bash
# Solution: Set PYTHONPATH
export PYTHONPATH="$(pwd):$(pwd)/src"
```

### Issue: Gemini API key not found

```bash
# Solution: Check .env file exists and has the key
cat .env | grep GEMINI_API_KEY

# Or set via environment variable
export GEMINI_API_KEY="your-api-key-here"
```

### Issue: Import errors for pandas/google.adk

```bash
# Solution: Verify virtual environment is activated
which python  # Should show .venv path

# Activate if needed
source .venv/bin/activate

# Reinstall dependencies
uv sync --all-extras
```

For more troubleshooting, see [APPENDIX.md](APPENDIX.md#a-detailed-troubleshooting-guide).
