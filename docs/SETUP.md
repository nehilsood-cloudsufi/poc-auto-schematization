# Setup Guide

This guide walks you through setting up the PVMAP Pipeline environment from scratch.

## Prerequisites

Before starting, ensure you have:
- **Python 3.12 or higher** installed
- **Git** installed
- An **Anthropic API key** for Claude Code CLI
- **Claude Code CLI** ([installation guide](https://github.com/anthropics/claude-code))

### Verify Prerequisites

```bash
# Check Python version (should be 3.12+)
python3 --version

# Check Git
git --version
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

Choose one of the following methods:

#### Option A: Using uv (Recommended - Faster)

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
.venv\Scripts\activate     # On Windows
```

#### Option B: Using pip (Traditional)

```bash
# Create virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate   # On Unix/macOS
venv\Scripts\activate      # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
# Test that key packages are installed
python -c "import pandas, datacommons; print('✅ Setup successful!')"

# Run the test suite (optional)
pytest tools/
```

---

## Configure Claude Code CLI

### Install Claude Code CLI

Visit the [Claude Code GitHub repository](https://github.com/anthropics/claude-code) for installation instructions.

### Set Your API Key

```bash
# Set your Anthropic API key for the current session
export ANTHROPIC_API_KEY="your-api-key-here"

# Or add it to your shell profile for persistence
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc

# Test Claude Code CLI
claude --version
```

---

## Set Up Python Path (CRITICAL)

The pipeline requires access to tool and utility modules. You **must** set the Python path:

```bash
# Export PYTHONPATH (required for every session)
export PYTHONPATH="$(pwd):$(pwd)/tools:$(pwd)/util"

# Verify you're in the project directory first
pwd  # Should show: /path/to/poc-auto-schematization

# Or add this to your shell profile for persistence
echo 'export PYTHONPATH="$PWD:$PWD/tools:$PWD/util"' >> ~/.zshrc
source ~/.zshrc
```

**⚠️ Important:** This is the #1 cause of "ModuleNotFoundError: No module named 'file_util'" errors.

### Verify PYTHONPATH

```bash
# Check that PYTHONPATH is set correctly
echo $PYTHONPATH  # Should include project, tools, and util directories
```

---

## Verify Repository Structure

Your repository should have this structure:

```
poc-auto-schematization/
├── input/                    # 39 datasets with input data & metadata
├── output/                   # Generated PVMAPs (created automatically)
├── schema_example_files/     # 7 schema categories for auto-selection
├── test_input/               # Test datasets (optional)
├── test_output/              # Test output (optional)
├── tools/                    # Processing tools
├── util/                     # Utility modules
├── logs/                     # Pipeline logs (created automatically)
├── run_pvmap_pipeline.py     # Main pipeline script
├── requirements.txt          # Python dependencies
└── README.md                 # Main documentation
```

---

## Environment Variables Reference

| Variable | Purpose | Example |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Claude API authentication | `sk-ant-api03-...` |
| `PYTHONPATH` | Module import resolution | `$(pwd):$(pwd)/tools:$(pwd)/util` |
| `GROUND_TRUTH_REPO` | Default ground truth directory (optional) | `/path/to/datacommonsorg-data/ground_truth` |
| `DC_API_KEY` | Data Commons API (optional) | `your_dc_api_key` |
| `MAPS_API_KEY` | Google Maps API (optional) | `your_maps_api_key` |

---

## Verification Checklist

Before running the pipeline, verify:

- [ ] Python 3.12+ installed (`python3 --version`)
- [ ] Virtual environment activated (`which python` shows venv path)
- [ ] Dependencies installed (`python -c "import pandas, datacommons"`)
- [ ] Claude Code CLI installed (`claude --version`)
- [ ] ANTHROPIC_API_KEY set (`echo $ANTHROPIC_API_KEY | head -c 10`)
- [ ] PYTHONPATH configured (`echo $PYTHONPATH`)
- [ ] Repository structure correct (`ls input/ output/ schema_example_files/ tools/ util/`)

---

## Next Steps

Once setup is complete:

1. **Review Input Structure** - See [INPUT_GUIDE.md](INPUT_GUIDE.md) to understand how to structure your datasets
2. **Run Your First Pipeline** - See [USAGE.md](USAGE.md) for quick start and usage instructions
3. **Troubleshooting** - If you encounter issues, see [APPENDIX.md](APPENDIX.md#a-detailed-troubleshooting-guide)

---

## Quick Troubleshooting

### Issue: ModuleNotFoundError for 'file_util'

```bash
# Solution: Set PYTHONPATH
export PYTHONPATH="$(pwd):$(pwd)/tools:$(pwd)/util"
```

### Issue: Claude Code CLI not found

```bash
# Solution: Verify installation
claude --version

# If not found, check PATH
which claude
```

### Issue: Import errors for pandas/datacommons

```bash
# Solution: Verify virtual environment is activated
which python  # Should show venv path

# Activate if needed
source .venv/bin/activate  # or: source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

For more troubleshooting, see [APPENDIX.md](APPENDIX.md#a-detailed-troubleshooting-guide).
