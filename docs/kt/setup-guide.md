# Getting Started — Auto-Schematization Pipeline

This guide will get your development environment set up and verify everything works. Budget ~30 minutes. If you get stuck on any step, reach out — happy to help.

---

## Step 1: Prerequisites

You need these installed on your machine:

| Tool | Version | Check Command |
|------|---------|---------------|
| Python | 3.12+ | `python3 --version` |
| Git | Any recent | `git --version` |
| uv | Any recent | `uv --version` |

**Don't have uv?** Install it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Step 2: Clone and Install

```bash
# Clone the repository
cd ~/work  # or your preferred location
git clone <repository-url> poc-auto-schematization
cd poc-auto-schematization

# Install all dependencies (creates .venv automatically)
uv sync --all-extras

# Activate the virtual environment
source .venv/bin/activate
```

Verify it worked:
```bash
python -c "import pandas, google.adk, google.genai; print('All good!')"
```

If you see `All good!`, move on. If not, check that `.venv` is activated (`which python` should show a `.venv` path).

---

## Step 3: Set Up Environment Variables

The pipeline needs a Gemini API key to call the LLM. Create a `.env` file in the project root:

```bash
cat > .env << 'EOF'
GEMINI_API_KEY=your-gemini-api-key-here
EOF
```

**Where to get the key:** Ask your team lead for a Gemini API key.

Now set the Python path (required every time you open a new terminal):

```bash
export PYTHONPATH="$(pwd):$(pwd)/src"
```

**Pro tip:** Add this to your shell profile so you don't have to remember:
```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export PYTHONPATH="$PWD:$PWD/src"' >> ~/.zshrc
source ~/.zshrc
```

---

## Step 4: Run Your First Pipeline

Let's process the BIS Central Bank Policy Rate dataset to verify everything works end-to-end.

```bash
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate
```

This takes about 45 seconds. You should see log output showing the pipeline progressing through its phases.

When it finishes, check the output:
```bash
ls output/bis_bis_central_bank_policy_rate/
```

You should see files like:
- `generated_pvmap.csv` — The generated PVMAP (this is the main output)
- `generation_notes.md` — Human-readable log of what happened
- `processed.csv` — Validation output (StatVarObservations)
- `processed.mcf` — StatVar definitions
- `populated_prompt.txt` — The actual prompt sent to the LLM
- `generated_response/` — Raw LLM responses per attempt

**Don't worry about understanding these files yet.** Just verify they exist — we'll walk through what each one does together.

---

## Step 5: Run the Test Suite (Optional but Recommended)

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```

This runs 1100+ tests. It takes a couple of minutes. If everything passes, your setup is solid.

**Note:** A few tests may skip (MCP integration tests). That's expected.

---

## Step 6: Familiarize Yourself

Read through this document to get a sense of the domain before we dive in:

- [ ] **`docs/kt/01-domain-primer.md`** — Explains Data Commons, PVMAPs, StatVars, and why this pipeline exists. (~10 minute read)

Don't worry about memorizing it. The goal is to have a rough mental picture so nothing feels completely foreign when we start.

Optionally skim:
- [ ] `docs/USAGE.md` — How to use the pipeline CLI

---

## Verification Checklist

Make sure you can check all of these:

- [ ] `python3 --version` shows 3.12+
- [ ] `which python` shows a `.venv` path (virtual environment active)
- [ ] `echo $PYTHONPATH` includes project root and `src/`
- [ ] `echo $GEMINI_API_KEY | head -c 10` shows something (key is set)
- [ ] `output/bis_bis_central_bank_policy_rate/generated_pvmap.csv` exists (pipeline ran successfully)
- [ ] Read `docs/kt/01-domain-primer.md`

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'file_util'`
You forgot to set PYTHONPATH:
```bash
export PYTHONPATH="$(pwd):$(pwd)/src"
```

### `Gemini API key not found` or `GEMINI_API_KEY not set`
Check your `.env` file exists and has the key:
```bash
cat .env | grep GEMINI_API_KEY
```

### `ImportError` for pandas or google.adk
Your virtual environment isn't activated:
```bash
source .venv/bin/activate
uv sync --all-extras  # reinstall if needed
```

### Pipeline hangs or takes >5 minutes
The LLM call might be slow. Check your network connection. If it's still stuck after 10 minutes, kill it (Ctrl+C) and reach out.

### `output/` directory is empty after running
Check `logs/` for error details:
```bash
tail -50 logs/pipeline_*.log
```
