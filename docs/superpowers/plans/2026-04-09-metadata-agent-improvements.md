# Metadata Agent Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 P1 metadata flags (`output_columns`, `header_rows`, `mapped_rows`, `mapped_columns`) so auto-generated `output_metadata.csv` matches ground truth semantics.

**Architecture:** Rewrite deterministic functions in `metadata_tools.py`, add a new `compute_mapped_columns()` with PVMAP key parsing and confidence scoring, refocus the LLM enrichment prompt on `mapped_columns` refinement only, drop 3 unnecessary flags.

**Tech Stack:** Python, CSV parsing, Google ADK (LlmAgent), pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/tools/metadata_tools.py` | Modify | Core computation — rewrite `extract_output_columns`, replace `count_mapped_rows`/`count_mapped_columns`, add `compute_mapped_columns`, update `generate_processor_config` |
| `src/resources/prompts/metadata_enrichment.txt` | Rewrite | New focused prompt for `mapped_columns` column classification |
| `src/agents/metadata_generation_agent.py` | Modify | Change LLM enrichment trigger to mapped_columns confidence, pass input_headers to config |
| `tests/tools/test_metadata_tools.py` | Modify | New tests for rewritten functions, update expectations for changed ones |
| `tests/agents/test_metadata_generation_agent.py` | Modify | Update expected output shape (no generate_statvar_name, etc.) |

---

### Task 1: Rewrite `extract_output_columns()` with Required Column Guarantee

**Files:**
- Modify: `src/tools/metadata_tools.py:26-91`
- Test: `tests/tools/test_metadata_tools.py`

- [ ] **Step 1: Write failing tests for required column guarantee**

Add these tests to `tests/tools/test_metadata_tools.py` in the `TestExtractOutputColumns` class:

```python
def test_required_columns_always_present(self):
    """4 required columns present even when PVMAP has none of them."""
    pvmap_no_svobs = "key,p,v\nFoo,gender,Male\nBar,age,25\n"
    result = extract_output_columns(pvmap_no_svobs)
    cols = result.split(",")
    assert "observationAbout" in cols
    assert "observationDate" in cols
    assert "variableMeasured" in cols
    assert "value" in cols

def test_required_columns_present_with_empty_pvmap(self):
    """Empty PVMAP still returns all 4 required columns."""
    result = extract_output_columns("")
    cols = result.split(",")
    assert "variableMeasured" in cols  # Currently fails — empty returns only first 4 of _OUTPUT_COLUMNS_ORDER

def test_optional_unit_added_when_in_pvmap(self):
    """unit added only when PVMAP contains it."""
    result = extract_output_columns(PVMAP_WITH_UNIT)
    cols = result.split(",")
    assert "unit" in cols

def test_optional_not_added_when_absent(self):
    """measurementMethod NOT in output when PVMAP doesn't use it."""
    result = extract_output_columns(SIMPLE_PVMAP)
    cols = result.split(",")
    assert "measurementMethod" not in cols
```

- [ ] **Step 2: Run tests to verify failures**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestExtractOutputColumns::test_required_columns_always_present -xvs`
Expected: FAIL — current code returns empty defaults `_OUTPUT_COLUMNS_ORDER[:4]` which happens to have the right 4, but `test_required_columns_always_present` should fail because the PVMAP `pvmap_no_svobs` has no SVOBS properties and the empty-case fallback only triggers on truly empty results.

Actually, the current code returns `_OUTPUT_COLUMNS_ORDER[:4]` when nothing is found, which happens to be the correct 4. Run all new tests to check current behavior:

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestExtractOutputColumns -xvs`

- [ ] **Step 3: Rewrite `extract_output_columns()` in `src/tools/metadata_tools.py`**

Replace the constants and function (lines 26-91):

```python
# Required output columns — always included regardless of PVMAP content.
# 100% presence across 51 ground truth metadata files.
REQUIRED_OUTPUT_COLUMNS = [
    "observationAbout",
    "observationDate",
    "variableMeasured",
    "value",
]

# Optional output columns — included only when the PVMAP uses them.
# GT frequency: unit=76%, scalingFactor=51%, measurementMethod=35%, observationPeriod=39%.
OPTIONAL_OUTPUT_COLUMNS = [
    "unit",
    "scalingFactor",
    "measurementMethod",
    "observationPeriod",
]

# Combined set for validation (replaces old VALID_SVOBS_PROPERTIES).
VALID_SVOBS_PROPERTIES = set(REQUIRED_OUTPUT_COLUMNS + OPTIONAL_OUTPUT_COLUMNS)

# Full canonical ordering for output_columns.
_OUTPUT_COLUMNS_ORDER = REQUIRED_OUTPUT_COLUMNS + OPTIONAL_OUTPUT_COLUMNS


def extract_output_columns(pvmap_csv_content: str) -> str:
    """Extract output columns from PVMAP, guaranteeing required columns.

    Always includes the 4 required StatVarObs columns. Adds optional columns
    (unit, scalingFactor, measurementMethod, observationPeriod) only when
    they appear as property names in the PVMAP.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.

    Returns:
        Comma-separated string of output columns in canonical order.
    """
    found_optional = set()
    if pvmap_csv_content and pvmap_csv_content.strip():
        reader = csv.reader(io.StringIO(pvmap_csv_content))
        for row in reader:
            if not row:
                continue
            if row[0].strip().lower() == "key":
                continue
            # Odd-indexed columns are property names
            for i in range(1, len(row), 2):
                prop = row[i].strip()
                if prop in OPTIONAL_OUTPUT_COLUMNS:
                    found_optional.add(prop)

    # Build: required (always) + optional (only if found), in canonical order
    result = list(REQUIRED_OUTPUT_COLUMNS)
    for col in OPTIONAL_OUTPUT_COLUMNS:
        if col in found_optional:
            result.append(col)

    return ",".join(result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestExtractOutputColumns -xvs`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/metadata_tools.py tests/tools/test_metadata_tools.py
git commit -m "fix(metadata): always include 4 required output_columns, add optional only from PVMAP"
```

---

### Task 2: Replace `count_mapped_rows()` with `compute_mapped_rows()`

**Files:**
- Modify: `src/tools/metadata_tools.py:94-111`
- Test: `tests/tools/test_metadata_tools.py`

- [ ] **Step 1: Write failing tests**

Replace `TestCountMappedRows` class in `tests/tools/test_metadata_tools.py`:

```python
class TestComputeMappedRows:
    def test_equals_header_rows(self):
        """mapped_rows always equals header_rows."""
        assert compute_mapped_rows(1) == 1
        assert compute_mapped_rows(2) == 2
        assert compute_mapped_rows(3) == 3

    def test_minimum_1(self):
        """At least 1."""
        assert compute_mapped_rows(0) == 1
        assert compute_mapped_rows(-1) == 1
```

Update the import at the top of the test file to include `compute_mapped_rows` instead of `count_mapped_rows`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestComputeMappedRows -xvs`
Expected: FAIL — `compute_mapped_rows` doesn't exist yet

- [ ] **Step 3: Implement `compute_mapped_rows()`**

In `src/tools/metadata_tools.py`, replace `count_mapped_rows()` (lines 94-111) with:

```python
def compute_mapped_rows(header_rows: int) -> int:
    """Compute mapped_rows for stat_var_processor config.

    In the processor, mapped_rows controls which input rows get row-based
    PV lookups. Ground truth analysis confirms mapped_rows == header_rows
    in all datasets where both are set.

    Args:
        header_rows: Number of header rows in the input CSV.

    Returns:
        mapped_rows value (minimum 1).
    """
    return max(1, header_rows)
```

Keep `count_mapped_rows` as a deprecated alias for backward compatibility if it's imported elsewhere, or remove if only used in `generate_processor_config` (check imports first).

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestComputeMappedRows -xvs`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/metadata_tools.py tests/tools/test_metadata_tools.py
git commit -m "fix(metadata): mapped_rows = header_rows, not PVMAP row count"
```

---

### Task 3: Implement `compute_mapped_columns()` — Deterministic Core

**Files:**
- Modify: `src/tools/metadata_tools.py`
- Test: `tests/tools/test_metadata_tools.py`

- [ ] **Step 1: Write failing tests with real ground truth data**

Add new test class in `tests/tools/test_metadata_tools.py`:

```python
class TestComputeMappedColumns:
    """Test mapped_columns computation using PVMAP key analysis."""

    # SAHIE: 9 dimension columns (year..iprcat), remaining are value columns
    SAHIE_PVMAP = """\
key,p1,v1,p2,v2,p3,v3
year,observationDate,{Number},observationPeriod,P1Y,,
statefips,#Format,StateFips={Number:0>2},,,,
countyfips,#Format,CountyFips={Number:0>3},,,,
agecat:0,age,Years0Onwards,,,,
agecat:1,age,Years0To18,,,,
racecat:0,race,USC_AllRaces,,,,
sexcat:0,gender,USC_BothSexes,,,,
iprcat:0,povertyStatus,USC_AllIncomes,,,,
NIPR,variableMeasured,dcid:Count_Person,,,,
NUI,variableMeasured,dcid:Count_Person,,,,
"""

    SAHIE_HEADERS = [
        "year", "version", "statefips", "countyfips", "geocat",
        "agecat", "racecat", "sexcat", "iprcat",
        "NIPR", "nipr_moe", "NUI", "nui_moe", "NIC", "nic_moe",
    ]

    # BRFSS: 2 dimension columns (State, life_stage via COLUMN:VALUE keys)
    BRFSS_PVMAP = """\
key,p1,v1,p2,v2,p3,v3
State,observationAbout,{Data},populationType,Person,healthOutcome,Asthma
year,observationDate,{Data},,,,
life_stage:child,age,YearsUpto18,,,,
life_stage:adult,age,Years18Onwards,,,,
Prevalence (Percent),value,{Number},,,,
Standard Error,marginOfError,{Number},,,,
"""

    BRFSS_HEADERS = [
        "State", "Income", "Sample Sizec", "Prevalence (Percent)",
        "Standard Error", "95% CId (Percent)", "|| ||",
        "Weighted Numbere", "95% CId (Weighted Number)", "year", "life_stage",
    ]

    # BIS: all direct keys (no COLUMN:VALUE patterns)
    BIS_PVMAP = """\
key,p1,v1,p2,v2,p3,v3
REF_AREA:Reference area,observationAbout,{Data},,,,
TIME_PERIOD:Time period or range,observationDate,{Data},,,,
OBS_VALUE:Observation Value,value,{Number},,,,
UNIT_MEASURE:Unit of measure,unit,{Data},,,,
"""

    BIS_HEADERS = [
        "STRUCTURE", "STRUCTURE_ID", "ACTION", "FREQ:Frequency",
        "REF_AREA:Reference area", "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value", "UNIT_MEASURE:Unit of measure",
    ]

    def test_sahie_dimension_columns(self):
        """SAHIE has COLUMN:VALUE keys → detects dimension columns."""
        result, confidence = compute_mapped_columns(self.SAHIE_PVMAP, self.SAHIE_HEADERS)
        # Dimension columns: agecat(6), racecat(7), sexcat(8), iprcat(9)
        # Rightmost dimension column is iprcat at position 9
        assert result == 9
        assert confidence == "high"

    def test_brfss_dimension_columns(self):
        """BRFSS has life_stage:child/adult → detects life_stage as dimension."""
        result, confidence = compute_mapped_columns(self.BRFSS_PVMAP, self.BRFSS_HEADERS)
        # life_stage is at position 11, but there's a gap
        # The key insight: dimension columns aren't always contiguous from left
        # life_stage is the only COLUMN:VALUE column
        assert result >= 2  # At minimum, should find life_stage column

    def test_bis_all_direct_keys(self):
        """BIS has only direct keys (with colon in header names, not COLUMN:VALUE)."""
        result, confidence = compute_mapped_columns(self.BIS_PVMAP, self.BIS_HEADERS)
        # No COLUMN:VALUE keys → confidence should be LOW
        # BIS keys like "REF_AREA:Reference area" are direct header matches, not COLUMN:VALUE
        assert confidence == "low"

    def test_empty_pvmap(self):
        """Empty PVMAP → 0, low confidence."""
        result, confidence = compute_mapped_columns("", ["A", "B", "C"])
        assert result == 0
        assert confidence == "low"

    def test_simple_passthrough(self):
        """Passthrough PVMAP (all direct keys matching headers) → 0, low."""
        pvmap = "key,p,v\nobservationAbout,observationAbout,{Data}\nvalue,value,{Number}\n"
        headers = ["observationAbout", "observationDate", "value"]
        result, confidence = compute_mapped_columns(pvmap, headers)
        assert result == 0
        assert confidence == "low"

    def test_contiguous_dimensions_high_confidence(self):
        """When dimension columns are contiguous from left → high confidence."""
        pvmap = "key,p,v\ncol_a:1,foo,bar\ncol_a:2,foo,baz\ncol_b:x,qux,quux\nval_col,value,{Number}\n"
        headers = ["col_a", "col_b", "val_col", "other"]
        result, confidence = compute_mapped_columns(pvmap, headers)
        assert result == 2  # col_a(1) and col_b(2) are dimension columns
        assert confidence == "high"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestComputeMappedColumns -xvs`
Expected: FAIL — `compute_mapped_columns` doesn't exist

- [ ] **Step 3: Implement `compute_mapped_columns()`**

Add to `src/tools/metadata_tools.py` (replace `count_mapped_columns` at lines 114-136):

```python
def compute_mapped_columns(
    pvmap_csv_content: str,
    input_headers: List[str],
) -> tuple:
    """Compute mapped_columns by classifying input columns as dimension vs value.

    Parses PVMAP keys to find COLUMN:VALUE patterns (e.g., "agecat:0"),
    then identifies which input columns are dimension columns (their cell
    values are PVMAP keys) vs value columns (their header is a PVMAP key).

    In stat_var_processor, mapped_columns controls which input columns get
    cell-value PV lookups. It should be the 1-based position of the rightmost
    dimension column.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.
        input_headers: List of column names from the input CSV.

    Returns:
        Tuple of (mapped_columns: int, confidence: str).
        confidence is "high" or "low".
    """
    if not pvmap_csv_content or not pvmap_csv_content.strip() or not input_headers:
        return (0, "low")

    # Step 1: Parse PVMAP keys into direct_keys and column_value_columns
    direct_keys = set()
    column_value_columns = set()  # Column names from COLUMN:VALUE patterns

    reader = csv.reader(io.StringIO(pvmap_csv_content))
    for row in reader:
        if not row:
            continue
        key = row[0].strip()
        if not key or key.lower() == "key":
            continue

        # Check for COLUMN:VALUE pattern
        # Must distinguish from keys like "REF_AREA:Reference area" (header names with colons)
        if ":" in key:
            col_part = key.split(":")[0].strip()
            # It's a COLUMN:VALUE key if the column part matches an input header
            # (case-insensitive comparison)
            header_lower = {h.strip().lower() for h in input_headers}
            if col_part.lower() in header_lower:
                column_value_columns.add(col_part.lower())
                continue

        # Otherwise it's a direct key
        direct_keys.add(key)

    # Step 2: Classify each input column
    # dimension = appears in column_value_columns (cell values are PVMAP keys)
    # value/unmapped = everything else
    dimension_positions = []  # 1-based positions
    header_lower_map = {h.strip().lower(): i + 1 for i, h in enumerate(input_headers)}

    for col_lower, pos in header_lower_map.items():
        if col_lower in column_value_columns:
            dimension_positions.append(pos)

    # Step 3: Find rightmost dimension column
    if not dimension_positions:
        return (0, "low")

    dimension_positions.sort()
    rightmost = max(dimension_positions)

    # Step 4: Confidence scoring
    # Check if dimension columns are contiguous from the left
    is_contiguous = True
    if len(dimension_positions) > 1:
        # Check that all positions between min and max are dimension columns
        expected_range = set(range(min(dimension_positions), max(dimension_positions) + 1))
        actual = set(dimension_positions)
        # Allow gaps — dimension columns don't have to include ALL leading columns,
        # but they should form a block without value columns interspersed after them
        if max(dimension_positions) > len(dimension_positions) * 2:
            # Dimension columns are scattered far apart
            is_contiguous = False

    confidence = "high" if is_contiguous and len(column_value_columns) > 0 else "low"

    return (rightmost, confidence)
```

- [ ] **Step 4: Update imports in test file**

Add `compute_mapped_columns` to the import statement in `tests/tools/test_metadata_tools.py`.

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestComputeMappedColumns -xvs`
Expected: ALL PASS (iterate on BRFSS/BIS edge cases if needed)

- [ ] **Step 6: Commit**

```bash
git add src/tools/metadata_tools.py tests/tools/test_metadata_tools.py
git commit -m "feat(metadata): compute mapped_columns from PVMAP key analysis with confidence scoring"
```

---

### Task 4: Strengthen `detect_header_rows()` with PVMAP Cross-Reference

**Files:**
- Modify: `src/tools/metadata_tools.py:177-226`
- Test: `tests/tools/test_metadata_tools.py`

- [ ] **Step 1: Write failing tests**

Add to `TestDetectHeaderRows` class:

```python
def test_pvmap_cross_reference_confirms_single_header(self, tmp_path):
    """PVMAP keys matching row 1 column names confirms 1 header row."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("State,Year,Value\nAlice,2020,100\nBob,2021,200\n")
    pvmap = "key,p,v\nState,observationAbout,{Data}\nYear,observationDate,{Data}\n"
    result = detect_header_rows(input_file=str(csv_file), pvmap_csv_content=pvmap)
    assert result == 1

def test_pvmap_cross_reference_detects_two_header_rows(self, tmp_path):
    """PVMAP keys matching both row 1 and row 2 values → 2 header rows."""
    csv_file = tmp_path / "test.csv"
    # Row 1: category headers, Row 2: sub-headers, Row 3+: data
    csv_file.write_text("Category,SubCat,Value\nTypeA,SubX,Count\n10,20,100\n")
    pvmap = "key,p,v\nCategory,observationAbout,{Data}\nTypeA,populationType,{Data}\n"
    result = detect_header_rows(input_file=str(csv_file), pvmap_csv_content=pvmap)
    assert result == 2

def test_no_pvmap_falls_back_to_text_scan(self, tmp_path):
    """Without PVMAP, uses existing text-scan logic."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Name,Value,Year\nAlice,100,2020\n")
    result = detect_header_rows(input_file=str(csv_file), pvmap_csv_content=None)
    assert result == 1
```

- [ ] **Step 2: Run tests to verify failures**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestDetectHeaderRows::test_pvmap_cross_reference_confirms_single_header -xvs`
Expected: FAIL — `detect_header_rows` doesn't accept `pvmap_csv_content` parameter

- [ ] **Step 3: Update `detect_header_rows()` signature and logic**

In `src/tools/metadata_tools.py`, modify `detect_header_rows` (lines 177-226):

```python
def detect_header_rows(
    input_file: Optional[str] = None,
    data_context: Optional[dict] = None,
    pvmap_csv_content: Optional[str] = None,
) -> int:
    """Detect number of header rows.

    Uses data_context first if available, then scans input file with optional
    PVMAP cross-reference for confirmation.
    Default: 1.

    Args:
        input_file: Path to input CSV file.
        data_context: Data context dict from sampling agent.
        pvmap_csv_content: Optional PVMAP CSV for cross-reference.

    Returns:
        Number of header rows (minimum 1).
    """
    # 1. Check data_context (trusted source from sampling agent)
    if data_context:
        hr = data_context.get("header_rows")
        if hr is not None:
            try:
                return max(1, int(hr))
            except (ValueError, TypeError):
                pass

    # 2. Scan input file
    if input_file and Path(input_file).exists():
        try:
            with open(input_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = []
                for i, row in enumerate(reader):
                    if i >= 10:
                        break
                    rows.append(row)

            if len(rows) >= 2:
                # 2a. Text-scan: count leading text-only rows
                text_header_count = 0
                for row in rows:
                    if _is_text_row(row):
                        text_header_count += 1
                    else:
                        break
                text_header_count = max(1, text_header_count)

                # 2b. PVMAP cross-reference
                pvmap_header_count = _pvmap_cross_ref_headers(rows, pvmap_csv_content)

                return max(text_header_count, pvmap_header_count)
        except Exception:
            pass

    return 1


def _pvmap_cross_ref_headers(
    input_rows: List[list], pvmap_csv_content: Optional[str]
) -> int:
    """Cross-reference input rows against PVMAP keys to detect header rows.

    A row is considered a header if its cell values appear as PVMAP keys.

    Args:
        input_rows: First N rows from the input CSV.
        pvmap_csv_content: Raw PVMAP CSV text.

    Returns:
        Number of header rows detected (minimum 1, 0 if no PVMAP).
    """
    if not pvmap_csv_content or not pvmap_csv_content.strip():
        return 0

    # Collect all PVMAP keys (including COLUMN:VALUE → just the full key)
    pvmap_keys = set()
    reader = csv.reader(io.StringIO(pvmap_csv_content))
    for row in reader:
        if not row:
            continue
        key = row[0].strip()
        if key and key.lower() != "key":
            pvmap_keys.add(key.lower())

    if not pvmap_keys:
        return 0

    # Check each input row: how many cell values match PVMAP keys?
    header_count = 0
    for row in input_rows[:5]:  # Check first 5 rows max
        cells = {c.strip().lower() for c in row if c.strip()}
        matches = cells & pvmap_keys
        if len(matches) >= 1:
            header_count += 1
        else:
            break  # Stop at first non-matching row

    return max(1, header_count) if header_count > 0 else 0
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestDetectHeaderRows -xvs`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/metadata_tools.py tests/tools/test_metadata_tools.py
git commit -m "fix(metadata): strengthen header_rows detection with PVMAP cross-reference"
```

---

### Task 5: Update `generate_processor_config()` — Wire New Functions, Drop Removed Flags

**Files:**
- Modify: `src/tools/metadata_tools.py:304-398`
- Test: `tests/tools/test_metadata_tools.py`

- [ ] **Step 1: Write failing tests for new behavior**

Add/update in `TestGenerateProcessorConfig`:

```python
def test_no_generate_statvar_name(self, tmp_path):
    """generate_statvar_name no longer in output."""
    result = generate_processor_config(
        pvmap_csv_content=SIMPLE_PVMAP,
        output_dir=str(tmp_path),
    )
    assert "generate_statvar_name" not in result["parameters"]

def test_no_drop_statvars(self, tmp_path):
    """drop_statvars_without_svobs no longer in output."""
    result = generate_processor_config(
        pvmap_csv_content=SIMPLE_PVMAP,
        output_dir=str(tmp_path),
    )
    assert "drop_statvars_without_svobs" not in result["parameters"]

def test_no_multi_value_properties(self, tmp_path):
    """multi_value_properties no longer in output."""
    result = generate_processor_config(
        pvmap_csv_content=SIMPLE_PVMAP,
        output_dir=str(tmp_path),
    )
    assert "multi_value_properties" not in result["parameters"]

def test_mapped_rows_equals_header_rows(self, tmp_path):
    """mapped_rows now equals header_rows, not PVMAP row count."""
    result = generate_processor_config(
        pvmap_csv_content=SIMPLE_PVMAP,
        data_context={"header_rows": 1},
        output_dir=str(tmp_path),
    )
    assert result["parameters"]["mapped_rows"] == 1  # Was 3 (PVMAP row count)

def test_accepts_input_headers(self, tmp_path):
    """New input_headers parameter used for mapped_columns computation."""
    result = generate_processor_config(
        pvmap_csv_content=SIMPLE_PVMAP,
        input_headers=["State", "Year", "Population"],
        output_dir=str(tmp_path),
    )
    assert "mapped_columns" in result["parameters"]

def test_required_output_columns_always_present(self, tmp_path):
    """Even with minimal PVMAP, all 4 required columns present."""
    minimal_pvmap = "key,p,v\nFoo,gender,Male\n"
    result = generate_processor_config(
        pvmap_csv_content=minimal_pvmap,
        output_dir=str(tmp_path),
    )
    cols = result["parameters"]["output_columns"].split(",")
    assert "observationAbout" in cols
    assert "variableMeasured" in cols
```

- [ ] **Step 2: Run tests to verify failures**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py::TestGenerateProcessorConfig::test_no_generate_statvar_name -xvs`
Expected: FAIL — current code still includes `generate_statvar_name`

- [ ] **Step 3: Rewrite `generate_processor_config()`**

Update the function signature and body in `src/tools/metadata_tools.py`:

```python
def generate_processor_config(
    pvmap_csv_content: str,
    data_context: Optional[dict] = None,
    input_file: Optional[str] = None,
    input_headers: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    existing_metadata_path: Optional[str] = None,
    llm_enrichment: Optional[dict] = None,
) -> Dict[str, Any]:
    """Main entry: generates config dict and writes CSV.

    Computes P1 flags: output_columns, header_rows, mapped_rows, mapped_columns.
    Merges with optional LLM enrichment and existing metadata.
    Priority: existing_metadata > llm_enrichment > deterministic.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.
        data_context: Data context from sampling (optional).
        input_file: Path to input CSV for header detection (optional).
        input_headers: List of input column names (optional, read from input_file if absent).
        output_dir: Directory to write output_metadata.csv (optional).
        existing_metadata_path: Path to existing metadata CSV (optional).
        llm_enrichment: Dict of LLM-suggested params (optional).

    Returns:
        Dict with keys: success, config_path, parameters, mapped_columns_confidence, error.
    """
    if not pvmap_csv_content or not pvmap_csv_content.strip():
        return {
            "success": False,
            "config_path": None,
            "parameters": {},
            "mapped_columns_confidence": None,
            "error": "Empty PVMAP content",
        }

    try:
        auto_params: Dict[str, Any] = {}

        # 1. output_columns — required 4 always + optional from PVMAP
        auto_params["output_columns"] = extract_output_columns(pvmap_csv_content)

        # 2. header_rows — text scan + PVMAP cross-reference
        header_rows = detect_header_rows(input_file, data_context, pvmap_csv_content)
        auto_params["header_rows"] = header_rows

        # 3. mapped_rows — equals header_rows
        auto_params["mapped_rows"] = compute_mapped_rows(header_rows)

        # 4. mapped_columns — PVMAP key analysis + confidence
        # Read input headers from file if not provided
        if not input_headers and input_file and Path(input_file).exists():
            try:
                with open(input_file, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    input_headers = next(reader, [])
            except Exception:
                input_headers = []

        mapped_cols, confidence = compute_mapped_columns(
            pvmap_csv_content, input_headers or []
        )
        auto_params["mapped_columns"] = mapped_cols

        # Merge LLM enrichment (only mapped_columns override now)
        if llm_enrichment and isinstance(llm_enrichment, dict):
            if "mapped_columns" in llm_enrichment:
                auto_params["mapped_columns"] = llm_enrichment["mapped_columns"]

        # Merge with existing metadata (existing wins)
        final_params = merge_with_existing(auto_params, existing_metadata_path)

        # Write to file
        config_path = None
        if output_dir:
            config_path = write_config_csv(
                final_params, str(Path(output_dir) / "output_metadata.csv")
            )

        return {
            "success": True,
            "config_path": config_path,
            "parameters": final_params,
            "mapped_columns_confidence": confidence,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to generate processor config: {e}")
        return {
            "success": False,
            "config_path": None,
            "parameters": {},
            "mapped_columns_confidence": None,
            "error": str(e),
        }
```

- [ ] **Step 4: Update existing tests that assert old values**

In `TestGenerateProcessorConfig`:
- `test_end_to_end`: Change `assert params["mapped_rows"] == 3` → `assert params["mapped_rows"] == 1`
- `test_no_output_dir`: Change `assert result["parameters"]["mapped_rows"] == 3` → `assert result["parameters"]["mapped_rows"] == 1`
- `test_passthrough_pvmap`: Change `assert result["parameters"]["mapped_rows"] == 4` → `assert result["parameters"]["mapped_rows"] == 1`
- `test_llm_enrichment_merged`: Remove assertions for `schemaless` and `description` (no longer merged)

In `TestCountMappedColumns` (now dead): Remove the entire class or rename/update to test `compute_mapped_columns`.

- [ ] **Step 5: Update imports at top of test file**

```python
from src.tools.metadata_tools import (
    extract_output_columns,
    compute_mapped_rows,
    compute_mapped_columns,
    detect_header_rows,
    merge_with_existing,
    write_config_csv,
    generate_processor_config,
    VALID_SVOBS_PROPERTIES,
)
```

- [ ] **Step 6: Run ALL metadata_tools tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_metadata_tools.py -xvs`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/tools/metadata_tools.py tests/tools/test_metadata_tools.py
git commit -m "refactor(metadata): wire new P1 flag computations, drop unnecessary flags"
```

---

### Task 6: Rewrite `metadata_enrichment.txt` Prompt

**Files:**
- Rewrite: `src/resources/prompts/metadata_enrichment.txt`

- [ ] **Step 1: Write new focused prompt**

Replace the entire content of `src/resources/prompts/metadata_enrichment.txt`:

```
You are analyzing a CSV dataset to determine which input columns are DIMENSION columns vs VALUE columns.

Input CSV columns: {input_headers}

PVMAP key patterns (grouped by type):
  Direct keys (column headers as PVMAP keys): {direct_keys_list}
  Column:Value keys (cell values as PVMAP keys): {column_value_keys_list}

First 3 data rows from input CSV:
{sample_rows}

DEFINITIONS:
- DIMENSION column: Its cell values appear as PVMAP keys using COLUMN:VALUE syntax.
  Example: column "agecat" with PVMAP keys "agecat:0", "agecat:1" means agecat is a DIMENSION column.
- VALUE column: Its column header itself is a PVMAP key.
  Example: column "NIPR" with PVMAP key "NIPR" means NIPR is a VALUE column.
- UNMAPPED: Column is not referenced in the PVMAP at all.

TASK:
Classify each input column and determine mapped_columns = the 1-based position of the rightmost DIMENSION column.

If there are no DIMENSION columns (all keys are direct header matches), set mapped_columns to 0.

Output ONLY valid JSON:
{{"mapped_columns": N, "dimension_columns": ["col1", "col2"], "reasoning": "brief explanation"}}
```

- [ ] **Step 2: Commit**

```bash
git add src/resources/prompts/metadata_enrichment.txt
git commit -m "refactor(metadata): rewrite enrichment prompt for mapped_columns classification"
```

---

### Task 7: Update `MetadataGenerationAgent` — LLM for mapped_columns Only

**Files:**
- Modify: `src/agents/metadata_generation_agent.py`

- [ ] **Step 1: Update `_run_async_impl` to pass `input_headers` and conditionally trigger LLM**

In `src/agents/metadata_generation_agent.py`, modify `_run_async_impl`:

The key changes are:
1. Read input headers from the input file
2. Pass `input_headers` to `generate_processor_config()`
3. Only invoke LLM enrichment when `mapped_columns_confidence == "low"` AND `attempt_number == 0`
4. Prepare LLM state with the new prompt variables (`input_headers`, `direct_keys_list`, `column_value_keys_list`, `sample_rows`)

```python
async def _run_async_impl(
    self, ctx: InvocationContext
) -> AsyncGenerator[Event, None]:
    """Generate stat_var_processor config from PVMAP and data context."""

    # Step 1: Check prerequisites
    pvmap_csv = ctx.session.state.get("pvmap_csv")
    current_dataset = ctx.session.state.get("current_dataset")

    if not pvmap_csv:
        pvmap_output = ctx.session.state.get("pvmap_output")
        if pvmap_output:
            try:
                pvmap_model = self._parse_pvmap_output(pvmap_output)
                pvmap_csv = convert_pvmap_output_to_csv(pvmap_model)
            except Exception as e:
                logger.warning(f"Failed to convert pvmap_output to CSV: {e}")

    if not pvmap_csv or not current_dataset:
        yield Event(
            author=self.name,
            content=types.Content(
                parts=[types.Part(text="Skipping metadata generation (no PVMAP or dataset)")]
            ),
            actions=EventActions(escalate=False),
        )
        return

    yield Event(
        author=self.name,
        content=types.Content(
            parts=[types.Part(text="Generating stat_var_processor config...")]
        ),
    )

    # Step 2: Resolve existing metadata
    existing_metadata = self._resolve_existing_metadata(current_dataset)

    # Step 3: Get input file and headers
    input_file = None
    input_headers = []
    if current_dataset.input_data_files:
        input_file = str(current_dataset.input_data_files[0])
        input_headers = self._read_input_headers(input_file)

    # Step 4: Phase A — Deterministic config generation
    data_context = ctx.session.state.get("data_context", {})

    result = generate_processor_config(
        pvmap_csv_content=pvmap_csv,
        data_context=data_context if isinstance(data_context, dict) else {},
        input_file=input_file,
        input_headers=input_headers,
        output_dir=str(current_dataset.output_dir),
        existing_metadata_path=existing_metadata,
    )

    # Step 5: Phase B — LLM refinement for mapped_columns (first attempt, low confidence only)
    attempt_number = ctx.session.state.get("attempt_number", 0)
    confidence = result.get("mapped_columns_confidence", "high")

    if attempt_number == 0 and confidence == "low" and self.enrichment_agent:
        try:
            # Prepare state for LLM prompt templating
            ctx.session.state["input_headers"] = str(input_headers)
            direct_keys, cv_keys = self._parse_pvmap_key_types(pvmap_csv)
            ctx.session.state["direct_keys_list"] = str(sorted(direct_keys)[:30])
            ctx.session.state["column_value_keys_list"] = str(sorted(cv_keys)[:30])
            ctx.session.state["sample_rows"] = self._read_sample_rows(input_file, 3)

            async for event in self.enrichment_agent.run_async(ctx):
                yield event

            # Parse LLM output
            enrichment_str = ctx.session.state.get("metadata_enrichment", "")
            if enrichment_str:
                clean = enrichment_str.strip()
                if clean.startswith("```"):
                    lines = clean.split("\n")
                    lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean = "\n".join(lines)
                llm_result = json.loads(clean)
                if "mapped_columns" in llm_result:
                    # Re-run config generation with LLM enrichment
                    result = generate_processor_config(
                        pvmap_csv_content=pvmap_csv,
                        data_context=data_context if isinstance(data_context, dict) else {},
                        input_file=input_file,
                        input_headers=input_headers,
                        output_dir=str(current_dataset.output_dir),
                        existing_metadata_path=existing_metadata,
                        llm_enrichment=llm_result,
                    )
                    logger.info(f"LLM mapped_columns refinement: {llm_result}")

        except Exception as e:
            logger.warning(f"LLM enrichment failed (non-fatal): {e}")

    # Step 6: Update state
    if result.get("success"):
        ctx.session.state["generated_config_path"] = result["config_path"]
        ctx.session.state["generated_config_params"] = result["parameters"]

        params = result["parameters"]
        yield Event(
            author=self.name,
            content=types.Content(
                parts=[
                    types.Part(
                        text=(
                            f"Config generated: output_columns={params.get('output_columns', 'N/A')}, "
                            f"mapped_rows={params.get('mapped_rows', 'N/A')}, "
                            f"mapped_columns={params.get('mapped_columns', 'N/A')}, "
                            f"header_rows={params.get('header_rows', 'N/A')}"
                        )
                    )
                ]
            ),
            actions=EventActions(escalate=False),
        )
    else:
        logger.warning(
            f"Metadata generation failed: {result.get('error')}. "
            "Validation will proceed without auto-config."
        )
        yield Event(
            author=self.name,
            content=types.Content(
                parts=[
                    types.Part(
                        text=f"Config generation failed (non-fatal): {result.get('error', 'unknown')}"
                    )
                ]
            ),
            actions=EventActions(escalate=False),
        )
```

- [ ] **Step 2: Add helper methods to `MetadataGenerationAgent`**

Add these methods to the class:

```python
def _read_input_headers(self, input_file: str) -> list:
    """Read column headers from input CSV file."""
    try:
        with open(input_file, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            return next(reader, [])
    except Exception as e:
        logger.warning(f"Failed to read input headers: {e}")
        return []

def _read_sample_rows(self, input_file: Optional[str], n: int = 3) -> str:
    """Read first N data rows from input CSV as string."""
    if not input_file:
        return ""
    try:
        with open(input_file, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            rows = []
            for i, row in enumerate(reader):
                if i >= n:
                    break
                rows.append(",".join(row[:10]))  # Truncate wide rows
            return "\n".join(rows)
    except Exception:
        return ""

def _parse_pvmap_key_types(self, pvmap_csv: str) -> tuple:
    """Parse PVMAP keys into direct keys and column:value keys."""
    direct_keys = set()
    cv_keys = set()
    try:
        reader = csv.reader(io.StringIO(pvmap_csv))
        for row in reader:
            if not row:
                continue
            key = row[0].strip()
            if not key or key.lower() == "key":
                continue
            if ":" in key:
                cv_keys.add(key)
            else:
                direct_keys.add(key)
    except Exception:
        pass
    return direct_keys, cv_keys
```

Add `import csv, io` to the imports at the top of the file if not already present.

- [ ] **Step 3: Run existing agent tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_metadata_generation_agent.py -xvs`
Expected: Some failures due to changed output (no generate_statvar_name, mapped_rows changed)

- [ ] **Step 4: Commit**

```bash
git add src/agents/metadata_generation_agent.py
git commit -m "refactor(metadata): LLM enrichment now focuses on mapped_columns refinement only"
```

---

### Task 8: Update Agent Tests for New Output Shape

**Files:**
- Modify: `tests/agents/test_metadata_generation_agent.py`

- [ ] **Step 1: Update test expectations**

In `TestMetadataGenerationAgent`:

1. `test_generates_config_from_pvmap`: Change `assert params["mapped_rows"] == 3` → `assert params["mapped_rows"] == 1`

2. `test_generates_config_from_pvmap_output_dict`: Change `assert params["mapped_rows"] == 3` → `assert params["mapped_rows"] == 1`

3. `test_deterministic_params_always_present`: Keep as-is — all 4 P1 params should still be present.

4. `test_output_columns_exclude_statvar_props`: Keep as-is — still valid.

5. Add new test:
```python
def test_no_dropped_flags_in_output(self, agent, mock_ctx):
    """Dropped flags should not appear in generated config."""
    mock_ctx.session.state["attempt_number"] = 1

    events = run_agent(agent, mock_ctx)

    params = mock_ctx.session.state.get("generated_config_params", {})
    assert "generate_statvar_name" not in params
    assert "drop_statvars_without_svobs" not in params
    assert "multi_value_properties" not in params
```

- [ ] **Step 2: Run all agent tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_metadata_generation_agent.py -xvs`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/agents/test_metadata_generation_agent.py
git commit -m "test(metadata): update agent tests for new P1-only output shape"
```

---

### Task 9: Full Test Suite Regression + Integration Validation

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass. Note the total count.

- [ ] **Step 2: Fix any regressions**

If tests fail, check:
- Other files importing `count_mapped_rows` or `count_mapped_columns` — update to new function names
- The `detect_multi_value_properties` function and its tests — keep the function but remove from `generate_processor_config` output (it may still be imported by other code)
- Any test asserting specific `mapped_rows` counts based on PVMAP row counts

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q` after each fix.

- [ ] **Step 3: Run integration check against ground truth**

Create and run a validation script:

```bash
PYTHONPATH="$(pwd):$(pwd)/src" python3 -c "
import csv, glob
from src.tools.metadata_tools import generate_processor_config

datasets = glob.glob('ground_truth/*/pvmap/*.csv')
results = []

for pvmap_file in sorted(datasets):
    parts = pvmap_file.split('/')
    ds_name = parts[1]
    
    # Find input file
    input_files = glob.glob(f'input/{ds_name}/test_data/*_input.csv')
    input_file = input_files[0] if input_files else None
    
    # Find GT metadata
    gt_metas = glob.glob(f'ground_truth/{ds_name}/metadata/*.csv')
    gt_meta = gt_metas[0] if gt_metas else None
    
    # Read GT values
    gt_params = {}
    if gt_meta:
        with open(gt_meta, 'r') as f:
            for row in csv.reader(f):
                if len(row) >= 2 and row[0].strip() and not row[0].startswith('#'):
                    gt_params[row[0].strip()] = row[1].strip()
    
    # Generate auto config
    with open(pvmap_file, 'r') as f:
        pvmap_content = f.read()
    
    result = generate_processor_config(
        pvmap_csv_content=pvmap_content,
        input_file=input_file,
    )
    
    auto = result.get('parameters', {})
    confidence = result.get('mapped_columns_confidence', 'N/A')
    
    # Compare P1 flags
    for flag in ['header_rows', 'mapped_rows', 'mapped_columns', 'output_columns']:
        gt_val = gt_params.get(flag, 'NOT_SET')
        auto_val = str(auto.get(flag, 'NOT_SET'))
        match = gt_val == auto_val
        if not match and flag == 'output_columns':
            # Normalize ordering for comparison
            match = set(gt_val.split(',')) == set(auto_val.split(','))
        results.append((ds_name, flag, gt_val, auto_val, match, confidence))

# Summary
total = len(results)
matches = sum(1 for r in results if r[4])
print(f'Match rate: {matches}/{total} ({100*matches/total:.0f}%)')
print()
for flag in ['header_rows', 'mapped_rows', 'mapped_columns', 'output_columns']:
    flag_results = [r for r in results if r[1] == flag]
    flag_matches = sum(1 for r in flag_results if r[4])
    print(f'  {flag}: {flag_matches}/{len(flag_results)} ({100*flag_matches/len(flag_results):.0f}%)')

# Show mismatches
mismatches = [r for r in results if not r[4] and r[2] != 'NOT_SET']
if mismatches:
    print(f'\nMismatches (GT value set):')
    for ds, flag, gt, auto, _, conf in mismatches[:20]:
        print(f'  {ds}/{flag}: GT={gt}, AUTO={auto} (conf={conf})')
"
```

Expected: >80% match rate across all flags. Note specific mismatches for follow-up.

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "fix(metadata): complete P1 metadata agent improvements — correct semantics for all 4 flags"
```
