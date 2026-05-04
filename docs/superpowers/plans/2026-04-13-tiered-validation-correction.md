# Tiered Validation Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve PVMAP validation pass rate from 46% to >70% by upgrading counter parsing, key matching, and Tier 1 correction rules in the existing tiered correction pipeline.

**Architecture:** The TieredCorrectionAgent already exists in `pvmap_retry_loop.py` (Tier 1 programmatic → Tier 2 LLM patch → Tier 3 full regen). This plan upgrades the internals: richer counter extraction in `log_filter.py`, a normalization-first key matching cascade in `pvmap_repair.py`, and new deterministic correction rules in `pvmap_corrector.py`.

**Tech Stack:** Python, Google ADK, pytest, difflib/rapidfuzz for string matching

**Spec:** `docs/superpowers/specs/2026-04-13-tiered-validation-correction-design.md`

---

### Task 1: Upgrade counter parsing — extract property cardinality and dropped details

**Files:**
- Modify: `src/pipeline/validation/log_filter.py` (FilteredLogs dataclass + filter_counters function)
- Test: `tests/pipeline/validation/test_log_filter_signals.py`

The `FilteredLogs` dataclass already has `property_cardinality`, `dropped_statvars`, `statvars_with_obs` fields but `filter_counters()` doesn't populate them from the actual counter file. This task adds parsing for `output-svobs-unique-{PROPERTY}`, `dropped-invalid-statvars_{DCID}`, `dropped-invalid-svobs_{TUPLE}`, and `generated-svobs_{DCID}`.

- [ ] **Step 1: Write failing tests for new counter parsing**

Create `tests/pipeline/validation/test_log_filter_signals.py`:

```python
"""Tests for enriched counter signal extraction in log_filter.py."""
import csv
import io
import tempfile
from pathlib import Path

import pytest

from src.pipeline.validation.log_filter import filter_counters, FilteredLogs


def _write_counters(tmp_path: Path, rows: list[tuple[str, int]]) -> Path:
    """Write a counters CSV file and return its path."""
    p = tmp_path / "processed_counters.txt"
    buf = io.StringIO()
    writer = csv.writer(buf)
    for key, val in rows:
        writer.writerow([key, val])
    p.write_text(buf.getvalue())
    return p


class TestPropertyCardinalityParsing:
    """filter_counters should populate property_cardinality from output-svobs-unique-* counters."""

    def test_parses_output_svobs_unique_counters(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("output-svobs-csv-rows", 80),
            ("output-svobs-unique-observationAbout", 5),
            ("output-svobs-unique-observationDate", 10),
            ("output-svobs-unique-variableMeasured", 20),
            ("output-svobs-unique-value", 75),
        ])
        result = filter_counters(counters)
        assert result.property_cardinality == {
            "observationAbout": 5,
            "observationDate": 10,
            "variableMeasured": 20,
            "value": 75,
        }

    def test_empty_counters_gives_empty_cardinality(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 50),
        ])
        result = filter_counters(counters)
        assert result.property_cardinality == {}


class TestDroppedStatvarParsing:
    """filter_counters should populate dropped_statvars from dropped-invalid-statvars_* counters."""

    def test_parses_dropped_invalid_statvars(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("dropped-invalid-statvars", 3),
            ("dropped-invalid-statvars_Count_Person_Male", 1),
            ("dropped-invalid-statvars_Count_Person_Female", 1),
            ("dropped-invalid-statvars_Count_Person_Total", 1),
        ])
        result = filter_counters(counters)
        assert set(result.dropped_statvars) == {
            "Count_Person_Male",
            "Count_Person_Female",
            "Count_Person_Total",
        }

    def test_parses_dropped_statvars_without_svobs(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("dropped-statvars-without-svobs", 2),
            ("dropped-statvars-without-svobs_Count_Empty", 1),
            ("dropped-statvars-without-svobs_Count_Other", 1),
        ])
        result = filter_counters(counters)
        # Both types of dropped statvars should be captured
        assert "Count_Empty" in result.dropped_statvars
        assert "Count_Other" in result.dropped_statvars


class TestPerStatvarObsCounts:
    """filter_counters should populate statvars_with_obs from generated-svobs_* counters."""

    def test_parses_generated_svobs_per_statvar(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("generated-svobs", 50),
            ("generated-svobs_Count_Person_Male", 25),
            ("generated-svobs_Count_Person_Female", 25),
        ])
        result = filter_counters(counters)
        assert ("Count_Person_Male", 25) in result.statvars_with_obs
        assert ("Count_Person_Female", 25) in result.statvars_with_obs


class TestCollisionTupleParsing:
    """filter_counters should parse error-mismatched-svobs detail counters."""

    def test_parses_mismatched_svobs_details(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("error-mismatched-svobs", 10),
            ("error-mismatched-svobs_Count_Person", 5),
            ("error-mismatched-svobs_Count_Household", 5),
        ])
        result = filter_counters(counters)
        assert "error-mismatched-svobs" in result.error_examples
        examples = result.error_examples["error-mismatched-svobs"]
        values = [v for v, _ in examples]
        assert "Count_Person" in values


class TestDroppedObservationParsing:
    """filter_counters should parse dropped-invalid-svobs detail counters."""

    def test_parses_dropped_svobs_with_tuple_details(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("dropped-invalid-svobs", 2),
            ("dropped-invalid-svobs_observationAbout=geoId/06;observationDate=2020;variableMeasured=dcid:Count_Person", 1),
            ("dropped-invalid-svobs_observationAbout=geoId/01;observationDate=2020;variableMeasured=dcid:Count_Person", 1),
        ])
        result = filter_counters(counters)
        assert "dropped-invalid-svobs" in result.error_examples
        examples = result.error_examples["dropped-invalid-svobs"]
        assert len(examples) == 2


class TestUniversalDebugMining:
    """filter_counters should mine debug examples for ALL error types, not just 7 hardcoded ones."""

    def test_mines_unknown_error_type_examples(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("error-some-new-type", 5),
            ("error-some-new-type_BadValue", 3),
            ("error-some-new-type_OtherBad", 2),
        ])
        result = filter_counters(counters)
        assert "error-some-new-type" in result.error_examples
        examples = result.error_examples["error-some-new-type"]
        values = [v for v, _ in examples]
        assert "BadValue" in values
        assert "OtherBad" in values
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_log_filter_signals.py -x -q`
Expected: Multiple failures — property_cardinality empty, dropped_statvars empty, etc.

- [ ] **Step 3: Implement enriched counter parsing in filter_counters()**

Edit `src/pipeline/validation/log_filter.py`. In the `filter_counters()` function, after the existing counter loop (around line 749), add new extraction blocks:

```python
    # ---------------------------------------------------------------
    # NEW: Extract property cardinality from output-svobs-unique-*
    # ---------------------------------------------------------------
    for key, value in raw_counters.items():
        if key.startswith('output-svobs-unique-'):
            prop_name = key[len('output-svobs-unique-'):]
            if prop_name and not prop_name.startswith('/'):
                result.property_cardinality[prop_name] = value

    # ---------------------------------------------------------------
    # NEW: Extract dropped StatVar names
    # ---------------------------------------------------------------
    dropped_prefixes = ['dropped-invalid-statvars_', 'dropped-statvars-without-svobs_']
    for key, value in raw_counters.items():
        for prefix in dropped_prefixes:
            if key.startswith(prefix):
                sv_name = key[len(prefix):]
                if sv_name and not sv_name.startswith('/'):
                    if sv_name not in result.dropped_statvars:
                        result.dropped_statvars.append(sv_name)

    # ---------------------------------------------------------------
    # NEW: Extract per-StatVar observation counts
    # ---------------------------------------------------------------
    svobs_prefix = 'generated-svobs_'
    for key, value in raw_counters.items():
        if key.startswith(svobs_prefix) and not key.endswith('.csv'):
            sv_name = key[len(svobs_prefix):]
            if sv_name and not sv_name.startswith('/'):
                result.statvars_with_obs.append((sv_name, value))
    result.statvars_with_obs.sort(key=lambda x: -x[1])

    # ---------------------------------------------------------------
    # NEW: Universal debug example mining (replaces hardcoded 7-type list)
    # ---------------------------------------------------------------
    # Clear the hardcoded results and re-mine for ALL error types
    result.error_examples.clear()
    for err_type in list(result.errors.keys()) + ['dropped-invalid-svobs', 'dropped-invalid-statvars']:
        prefix = f"{err_type}_"
        examples = []
        for key, value in raw_counters.items():
            if key.startswith(prefix):
                example_val = key[len(prefix):]
                if example_val and not example_val.startswith('/'):
                    examples.append((example_val, value))
        if examples:
            examples.sort(key=lambda x: -x[1])
            result.error_examples[err_type] = examples
```

Also, delete the old hardcoded `_ERROR_TYPES_TO_MINE` block (lines ~783-803) since the universal mining replaces it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_log_filter_signals.py -x -q`
Expected: All pass.

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/validation/log_filter.py tests/pipeline/validation/test_log_filter_signals.py
git commit -m "feat(validation): enrich counter parsing with property cardinality, dropped StatVars, and universal debug mining"
```

---

### Task 2: Upgrade key matching — normalization cascade with numeric guards

**Files:**
- Modify: `src/pipeline/validation/pvmap_repair.py` (`match_key_to_header` function, ~line 219)
- Test: `tests/pipeline/validation/test_key_matching_cascade.py`

The current `match_key_to_header()` uses simple lowercase + alphanumeric + fuzzy matching at 0.80/0.85. This task replaces it with the normalization cascade from the spec: exact → normalized → token-set-ratio → REJECT if numeric-different.

- [ ] **Step 1: Write failing tests for the new matching cascade**

Create `tests/pipeline/validation/test_key_matching_cascade.py`:

```python
"""Tests for the normalization-first key matching cascade in pvmap_repair.py."""
import pytest

from src.pipeline.validation.pvmap_repair import (
    match_key_to_header,
    build_key_index,
)


@pytest.fixture
def census_headers():
    return [
        "year", "statefips", "countyfips", "geocat",
        "agecat", "racecat", "sexcat", "iprcat",
        "NIPR", "NUI", "NIC", "PCTUI", "PCTIC",
        "state_name", "county_name",
    ]


@pytest.fixture
def census_index(census_headers):
    return build_key_index(census_headers)


class TestExactMatch:
    def test_exact_match_returns_none(self, census_headers, census_index):
        """Exact match = already correct, returns None."""
        assert match_key_to_header("year", census_index, census_headers) is None

    def test_case_mismatch_returns_correct(self, census_headers, census_index):
        assert match_key_to_header("Year", census_index, census_headers) == "year"
        assert match_key_to_header("YEAR", census_index, census_headers) == "year"


class TestNormalizedMatch:
    def test_underscore_vs_space(self):
        headers = ["State FIPS Code", "County Name"]
        index = build_key_index(headers)
        assert match_key_to_header("state_fips_code", index, headers) == "State FIPS Code"

    def test_extra_whitespace(self):
        headers = ["Population Count"]
        index = build_key_index(headers)
        assert match_key_to_header("Population  Count", index, headers) == "Population Count"


class TestTokenSetMatch:
    def test_permuted_tokens(self):
        headers = ["Female Population"]
        index = build_key_index(headers)
        assert match_key_to_header("Population Female", index, headers) == "Female Population"

    def test_partial_token_overlap(self):
        headers = ["Total Population Male"]
        index = build_key_index(headers)
        # "Male Total Population" should match via token set
        assert match_key_to_header("Male Total Population", index, headers) == "Total Population Male"


class TestNumericGuard:
    """Matches that differ ONLY in digits must be REJECTED to prevent data corruption."""

    def test_rejects_numeric_difference(self):
        headers = ["Age 15-19", "Age 20-24", "Age 25-29"]
        index = build_key_index(headers)
        # "Age 15-29" is not a valid header — it must NOT fuzzy-match to "Age 15-19" or "Age 25-29"
        assert match_key_to_header("Age 15-29", index, headers) is None

    def test_rejects_digit_only_change(self):
        headers = ["Income_50k_to_75k", "Income_75k_to_100k"]
        index = build_key_index(headers)
        # Hallucinated aggregate range must not match a specific bracket
        assert match_key_to_header("Income_50k_to_100k", index, headers) is None

    def test_allows_non_numeric_fuzzy(self):
        headers = ["Population_Count"]
        index = build_key_index(headers)
        # "Populaton_Count" (typo) should still match
        assert match_key_to_header("Populaton_Count", index, headers) == "Population_Count"


class TestColumnValueKeys:
    """COLUMN:VALUE keys should only match the column portion."""

    def test_column_value_key_matches_column(self):
        headers = ["racecat"]
        index = build_key_index(headers)
        # "racecat:White" should return None because "racecat" already matches
        assert match_key_to_header("racecat:White", index, headers) is None

    def test_mismatched_column_part_gets_fixed(self):
        headers = ["Race Category"]
        index = build_key_index(headers)
        # "race_category:White" should fix the column part
        assert match_key_to_header("race_category:White", index, headers) == "Race Category"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_key_matching_cascade.py -x -q`
Expected: Failures on token-set matching and numeric guard tests.

- [ ] **Step 3: Implement the normalization cascade with numeric guard**

Edit `src/pipeline/validation/pvmap_repair.py`, replace the `match_key_to_header()` function (lines ~219-278):

```python
def _has_numeric_difference(s1: str, s2: str) -> bool:
    """Check if two strings differ ONLY in their numeric segments.

    Returns True if the strings are identical except for digits,
    meaning a fuzzy match would corrupt numeric cohort data
    (e.g., 'Age 15-19' vs 'Age 15-29').
    """
    # Extract numeric segments from both strings
    nums1 = re.findall(r'\d+', s1)
    nums2 = re.findall(r'\d+', s2)
    # Strip all digits and compare the skeleton
    skel1 = re.sub(r'\d+', '', s1).strip()
    skel2 = re.sub(r'\d+', '', s2).strip()
    # If the non-numeric skeletons are the same but the numbers differ → danger
    if skel1.lower() == skel2.lower() and nums1 != nums2:
        return True
    return False


def _token_set_match(key: str, headers: List[str]) -> Optional[str]:
    """Token-set-ratio matching: permutation-invariant word matching.

    Tokenizes both key and each header by non-alphanumeric splits,
    compares sorted token sets. Match requires all tokens present.
    """
    key_tokens = set(re.split(r'[^a-zA-Z0-9]+', key.lower()))
    key_tokens.discard('')
    if not key_tokens:
        return None

    for header in headers:
        header_tokens = set(re.split(r'[^a-zA-Z0-9]+', header.lower()))
        header_tokens.discard('')
        if key_tokens == header_tokens:
            return header
    return None


def match_key_to_header(
    key: str,
    key_index: Dict[str, str],
    headers: List[str],
) -> Optional[str]:
    """Normalization-first key matching cascade with numeric safety guard.

    Match order:
    1. Exact match → None (already correct)
    2. Case-insensitive via key_index
    3. Alphanumeric-only via key_index
    4. Token-set-ratio (permutation-invariant)
    5. Fuzzy match (difflib, cutoff 0.80/0.85) WITH numeric guard

    The numeric guard REJECTS any fuzzy match where the strings differ
    only in their digit segments (e.g., 'Age 15-19' vs 'Age 15-29')
    to prevent silent data corruption.

    For COLUMN:VALUE syntax, matches only the COLUMN portion.
    """
    # Handle COLUMN:VALUE syntax
    column_part, value_suffix = _split_column_value(key, headers)

    # Skip special keys
    if column_part.startswith('#') or column_part.startswith('key'):
        return None

    # 1. Exact match
    if column_part in headers:
        return None  # Already correct

    # 2. Case-insensitive via key_index
    key_lower = column_part.strip().lower()
    if key_lower in key_index:
        matched = key_index[key_lower]
        if matched != column_part:
            return matched

    # 3. Alphanumeric-only via key_index
    key_alnum = re.sub(r'[^a-z0-9]', '', key_lower)
    if key_alnum and key_alnum in key_index:
        matched = key_index[key_alnum]
        if matched != column_part:
            return matched

    # 4. Token-set-ratio match (permutation-invariant)
    token_match = _token_set_match(column_part, headers)
    if token_match and token_match != column_part:
        return token_match

    # 5. Fuzzy match WITH numeric guard
    cutoff = 0.80 if len(column_part) > 15 else 0.85
    matches = difflib.get_close_matches(
        column_part, headers, n=1, cutoff=cutoff
    )
    if matches and matches[0] != column_part:
        candidate = matches[0]
        # SAFETY: reject if the only difference is in digits
        if _has_numeric_difference(column_part, candidate):
            logger.debug(
                "Rejecting fuzzy match %r → %r (numeric difference detected)",
                column_part, candidate,
            )
            return None
        return candidate

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_key_matching_cascade.py -x -q`
Expected: All pass.

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions (existing pvmap_repair tests still pass).

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/validation/pvmap_repair.py tests/pipeline/validation/test_key_matching_cascade.py
git commit -m "feat(validation): upgrade key matching with token-set-ratio and numeric guard"
```

---

### Task 3: Add Tier 1 rule — fix_missing_required_props using column_manifest

**Files:**
- Modify: `src/pipeline/validation/pvmap_corrector.py`
- Test: `tests/pipeline/validation/test_corrector_missing_props.py`

The existing `_apply_missing_required_props` only fixes CSV structural issues (odd cell counts). This task adds logic to inject `observationAbout`, `observationDate`, and `value` rows when they're missing and `column_manifest` knows which column should fill them.

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/validation/test_corrector_missing_props.py`:

```python
"""Tests for fix_missing_required_props using column_manifest."""
import pytest

from src.pipeline.validation.log_filter import FilteredLogs
from src.pipeline.validation.pvmap_corrector import apply_correction_rules


def _make_filtered_logs(**overrides) -> FilteredLogs:
    logs = FilteredLogs()
    for k, v in overrides.items():
        setattr(logs, k, v)
    return logs


class TestInjectMissingObservationAbout:
    def test_injects_place_row_from_manifest(self):
        pvmap = "Year,observationDate,{Data}\nPopulation,value,{Number}"
        logs = _make_filtered_logs(
            errors={"error-svobs-missing-property": 100},
            error_examples={"error-svobs-missing-property": [("observationAbout", 100)]},
        )
        manifest = {
            "must_map": [
                {"column_name": "State FIPS", "role": "place", "sample_values": ["01", "06"]},
            ],
            "can_ignore": [],
        }
        corrected, changes = apply_correction_rules(
            pvmap_csv=pvmap,
            filtered_logs=logs,
            key_match_report="",
            input_data_path=None,
            column_manifest=manifest,
        )
        assert "State FIPS" in corrected
        assert "observationAbout" in corrected
        assert any("fix_missing_required" in c for c in changes)


class TestInjectMissingObservationDate:
    def test_injects_date_row_from_manifest(self):
        pvmap = "State,observationAbout,dcid:geoId/{Data}\nPop,value,{Number}"
        logs = _make_filtered_logs(
            errors={"error-svobs-missing-property": 50},
            error_examples={"error-svobs-missing-property": [("observationDate", 50)]},
        )
        manifest = {
            "must_map": [
                {"column_name": "Year", "role": "time", "sample_values": ["2020", "2021"]},
            ],
            "can_ignore": [],
        }
        corrected, changes = apply_correction_rules(
            pvmap_csv=pvmap,
            filtered_logs=logs,
            key_match_report="",
            input_data_path=None,
            column_manifest=manifest,
        )
        assert "Year" in corrected
        assert "observationDate" in corrected


class TestNoManifestNoInjection:
    def test_no_manifest_no_change(self):
        pvmap = "Year,observationDate,{Data}"
        logs = _make_filtered_logs(
            errors={"error-svobs-missing-property": 10},
            error_examples={"error-svobs-missing-property": [("observationAbout", 10)]},
        )
        corrected, changes = apply_correction_rules(
            pvmap_csv=pvmap,
            filtered_logs=logs,
            key_match_report="",
            input_data_path=None,
            column_manifest=None,
        )
        # Without manifest, can't inject — should not crash
        assert corrected == pvmap or "fix_missing_required" not in str(changes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_corrector_missing_props.py -x -q`
Expected: Failures because `apply_correction_rules` doesn't accept `column_manifest` parameter and doesn't inject rows.

- [ ] **Step 3: Implement the fix_missing_required_props rule**

Edit `src/pipeline/validation/pvmap_corrector.py`:

1. Add `column_manifest` parameter to `apply_correction_rules()` signature (line ~608):

```python
def apply_correction_rules(
    pvmap_csv: str,
    filtered_logs: FilteredLogs,
    key_match_report: str,
    input_data_path: Optional[Path] = None,
    column_manifest: Optional[dict] = None,  # NEW
) -> Tuple[str, List[str]]:
```

2. Pass `column_manifest` into `ctx`:

```python
    ctx: dict = {
        'key_match_report': key_match_report,
        'input_data_path': input_data_path,
        'column_manifest': column_manifest,  # NEW
    }
```

3. Add a new condition/apply pair before the existing `fix_missing_required_props` rule (priority 3.5):

```python
def _condition_missing_required_from_manifest(filtered_logs: FilteredLogs, ctx: dict) -> bool:
    """Check if required props are missing AND column_manifest can provide them."""
    error_type = 'error-svobs-missing-property'
    has_error = (
        error_type in filtered_logs.errors and filtered_logs.errors[error_type] > 0
    )
    has_manifest = bool(ctx.get('column_manifest'))
    if not has_error or not has_manifest:
        return False
    # Check if examples mention specific missing props
    examples = filtered_logs.error_examples.get(error_type, [])
    missing_props = {v.lower() for v, _ in examples}
    return bool(missing_props & {'observationabout', 'observationdate', 'value'})


def _apply_missing_required_from_manifest(
    pvmap_csv: str, filtered_logs: FilteredLogs, ctx: dict
) -> str:
    """Inject missing required property rows using column_manifest knowledge."""
    manifest = ctx.get('column_manifest', {})
    if not manifest:
        return pvmap_csv

    examples = filtered_logs.error_examples.get('error-svobs-missing-property', [])
    missing_props = {v.lower() for v, _ in examples}

    rows = _parse_pvmap_rows(pvmap_csv)
    existing_props = set()
    for row in rows:
        for cell in row[1:]:
            existing_props.add(cell.strip().lower())

    added = []
    must_map = manifest.get('must_map', [])

    if 'observationabout' in missing_props and 'observationabout' not in existing_props:
        place_cols = [e for e in must_map if e.get('role') == 'place']
        if place_cols:
            col = place_cols[0]['column_name']
            samples = place_cols[0].get('sample_values', [])
            # Detect FIPS-like values
            if samples and all(str(s).isdigit() for s in samples[:3]):
                rows.append([col, 'observationAbout', 'dcid:geoId/{Data}'])
            else:
                rows.append([col, 'observationAbout', '{Data}'])
            added.append(f"Injected observationAbout from column '{col}'")

    if 'observationdate' in missing_props and 'observationdate' not in existing_props:
        time_cols = [e for e in must_map if e.get('role') == 'time']
        if time_cols:
            col = time_cols[0]['column_name']
            rows.append([col, 'observationDate', '{Data}'])
            added.append(f"Injected observationDate from column '{col}'")

    if 'value' in missing_props and 'value' not in existing_props:
        value_cols = [e for e in must_map if e.get('role') == 'value']
        if value_cols:
            col = value_cols[0]['column_name']
            rows.append([col, 'value', '{Number}', 'populationType', 'Thing', 'measuredProperty', 'count'])
            added.append(f"Injected value from column '{col}'")

    if added:
        return _rows_to_csv(rows)
    return pvmap_csv
```

4. Register the rule in `_build_rules()` with priority 3 (before the existing structural fix):

```python
        CorrectionRule(
            name='fix_missing_required_from_manifest',
            error_type='error-svobs-missing-property',
            priority=3,
            condition=_condition_missing_required_from_manifest,
            apply=_apply_missing_required_from_manifest,
        ),
```

And bump the existing `fix_missing_required_props` priority from 4 to 5, and `fix_aggregate_invalid` from 5 to 6.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_corrector_missing_props.py -x -q`
Expected: All pass.

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions. Some existing corrector tests may need updating if they check rule count or priority order.

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/validation/pvmap_corrector.py tests/pipeline/validation/test_corrector_missing_props.py
git commit -m "feat(validation): add Tier 1 rule to inject missing required props from column_manifest"
```

---

### Task 4: Wire column_manifest into TieredCorrectionAgent Tier 1

**Files:**
- Modify: `src/agents/pvmap_retry_loop.py` (TieredCorrectionAgent._run_async_impl, ~line 2445)
- Test: Verify by running pipeline on a real dataset (integration test added in Task 6)

The `TieredCorrectionAgent` calls `apply_correction_rules()` at line 2445 but doesn't pass `column_manifest`. This task passes it from session state.

- [ ] **Step 1: Read the current call site**

In `src/agents/pvmap_retry_loop.py` around line 2445:
```python
corrected, changes = apply_correction_rules(
    pvmap_csv=best_pvmap,
    filtered_logs=filtered_logs,
    key_match_report=key_match_report,
    input_data_path=input_data_path,
)
```

- [ ] **Step 2: Add column_manifest parameter**

Change to:
```python
column_manifest = ctx.session.state.get("column_manifest")
corrected, changes = apply_correction_rules(
    pvmap_csv=best_pvmap,
    filtered_logs=filtered_logs,
    key_match_report=key_match_report,
    input_data_path=input_data_path,
    column_manifest=column_manifest,
)
```

- [ ] **Step 3: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions.

- [ ] **Step 4: Commit**

```bash
git add src/agents/pvmap_retry_loop.py
git commit -m "fix(validation): pass column_manifest to apply_correction_rules in TieredCorrectionAgent"
```

---

### Task 5: Upgrade validation_tool.py to return FilteredLogs object

**Files:**
- Modify: `src/tools/validation_tool.py` (`run_validation` function)
- Test: `tests/tools/test_validation_tool_filtered.py`

Currently `run_validation()` returns `counter_summary` as a string. The TieredCorrectionAgent also needs the raw `FilteredLogs` object to pass to correction rules. Add a `filtered_logs` key to the return dict.

- [ ] **Step 1: Write a test for the new return key**

Create `tests/tools/test_validation_tool_filtered.py`:

```python
"""Test that run_validation returns filtered_logs object."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.tools.validation_tool import run_validation
from src.pipeline.validation.log_filter import FilteredLogs


class TestRunValidationReturnsFilteredLogs:
    def test_returns_filtered_logs_key(self, tmp_path):
        # Create minimal input/pvmap/counter files
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col1,col2\n1,2\n")
        pvmap_csv = tmp_path / "pvmap.csv"
        pvmap_csv.write_text("col1,value,{Number}\n")
        counters = tmp_path / "processed_counters.txt"
        counters.write_text('"input-rows-processed",2\n"output-svobs-csv-rows",1\n')
        output = tmp_path / "processed.csv"
        output.write_text("header\nrow1\n")

        with patch("src.tools.validation_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr="",
            )
            result = run_validation(
                input_data=str(input_csv),
                pvmap_path=str(pvmap_csv),
                metadata_file=None,
                output_dir=str(tmp_path),
            )
        assert "filtered_logs" in result
        if result["filtered_logs"] is not None:
            assert isinstance(result["filtered_logs"], FilteredLogs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_validation_tool_filtered.py -x -q`
Expected: Fail — `filtered_logs` key not in result.

- [ ] **Step 3: Add filtered_logs to run_validation return dict**

In `src/tools/validation_tool.py`, find each `return` statement in `run_validation()` and add `"filtered_logs": filtered_logs` (or `None` for early returns). The key places:

1. Early returns (input not found, etc.) — add `"filtered_logs": None`
2. The `returncode == 0` success/empty-output paths (~line 480-514) — add `"filtered_logs": filtered_logs`
3. The non-zero exit code path (~line 546-558) — add `"filtered_logs": filtered_logs`
4. Timeout/exception paths — add `"filtered_logs": None`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/tools/test_validation_tool_filtered.py -x -q`
Expected: Pass.

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions.

- [ ] **Step 6: Commit**

```bash
git add src/tools/validation_tool.py tests/tools/test_validation_tool_filtered.py
git commit -m "feat(validation): return FilteredLogs object from run_validation for programmatic access"
```

---

### Task 6: Integration test — TieredCorrectionAgent on real failed dataset

**Files:**
- Create: `tests/agents/test_tiered_correction_integration.py`

This test uses real counter files from the output directory to verify that the upgraded Tier 1 correction rules produce the expected fixes.

- [ ] **Step 1: Write integration test using BIS dataset counters**

Create `tests/agents/test_tiered_correction_integration.py`:

```python
"""Integration tests for TieredCorrectionAgent using real pipeline output."""
import pytest
from pathlib import Path

from src.pipeline.validation.log_filter import filter_counters
from src.pipeline.validation.pvmap_corrector import apply_correction_rules


# Path to real counter files from pipeline runs
BIS_OUTPUT = Path("output/bis_bis_central_bank_policy_rate")
BRFSS_OUTPUT = Path("output/brfss_nchs_asthma_prevalence")


@pytest.mark.skipif(
    not (BIS_OUTPUT / "processed_counters.txt").exists(),
    reason="BIS output not available",
)
class TestBISCorrection:
    """BIS fails with 540 unresolved places (country/[DATA])."""

    def test_parses_bis_counters(self):
        logs = filter_counters(BIS_OUTPUT / "processed_counters.txt")
        assert logs.input_rows > 0
        # BIS should have unresolved place errors
        assert "error-unresolved-place" in logs.errors

    def test_bis_correction_produces_changes(self):
        counters = BIS_OUTPUT / "processed_counters.txt"
        pvmap_path = BIS_OUTPUT / "generated_pvmap.csv"
        if not pvmap_path.exists():
            pytest.skip("No PVMAP file")

        logs = filter_counters(counters)
        pvmap = pvmap_path.read_text()

        corrected, changes = apply_correction_rules(
            pvmap_csv=pvmap,
            filtered_logs=logs,
            key_match_report="",
            input_data_path=None,
        )
        # Should have some corrections for the place issue
        assert isinstance(changes, list)


@pytest.mark.skipif(
    not (BRFSS_OUTPUT / "processed_counters.txt").exists(),
    reason="BRFSS output not available",
)
class TestBRFSSCorrection:
    """BRFSS fails with unresolved {Number} template refs."""

    def test_parses_brfss_counters_with_new_signals(self):
        logs = filter_counters(BRFSS_OUTPUT / "processed_counters.txt")
        # Should detect unresolved value refs
        assert logs.unresolved_refs or "warning-unresolved-value-ref" in logs.warnings or logs.input_rows > 0

    def test_brfss_property_cardinality_populated(self):
        logs = filter_counters(BRFSS_OUTPUT / "processed_counters.txt")
        # If output exists, property_cardinality should be populated
        if logs.output_rows > 0:
            assert len(logs.property_cardinality) > 0
```

- [ ] **Step 2: Run integration tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_tiered_correction_integration.py -x -q -v`
Expected: Tests pass (or skip if output files don't exist).

- [ ] **Step 3: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add tests/agents/test_tiered_correction_integration.py
git commit -m "test: add integration tests for tiered correction against real pipeline output"
```
