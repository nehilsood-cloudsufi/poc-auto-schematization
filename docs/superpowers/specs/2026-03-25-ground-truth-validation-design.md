# Ground Truth Validation — Design Spec

## Goal

Validate that ground truth PVMAPs actually produce valid StatVarObservations when run against their input CSVs. Answer: "is our ground truth even correct?"

## Scope

- 48 datasets from `analysis/factor_analysis/dataset_features_and_accuracy.csv`
- Run stat_var_processor on each ground truth PVMAP file individually
- Requires all three inputs: input CSV, PVMAP, metadata

## Script

**File:** `tools/validate_ground_truth.py`

### Input Resolution Per Dataset

1. **Input CSV:** `input/{dataset}/test_data/*_input.csv` — first match
2. **Ground truth PVMAPs:** All `*.csv` files in `ground_truth/{dataset}/pvmap/` — each gets its own run
3. **Metadata:**
   - Primary: `ground_truth/{dataset}/metadata/*.csv` — first match
   - Fallback: `input/{dataset}/input_metadata/*.csv` — first match, flagged in output
   - Neither: skip dataset, mark as "skipped: no metadata"

### Execution

For each (dataset, pvmap_file) pair:

```bash
python3 src/pipeline/validation/stat_var_processor.py \
  --input_data={input_csv} \
  --pv_map={pvmap_csv} \
  --config_file={metadata_csv} \
  --generate_statvar_name=True \
  --output_path=output/ground_truth_validation/{dataset}/{pvmap_stem}/processed
```

- 300-second timeout (matches pipeline)
- Set `PYTHONPATH` to include project root and src/
- Capture return code, check for `processed.csv` existence and row count

### Pass/Fail Criteria

- **PASS:** return code 0 AND `processed.csv` exists AND has >= 1 data row (not just header)
- **FAIL:** non-zero exit, empty output, timeout, or missing output file
- **SKIP:** missing metadata or missing input CSV

### Output

**CSV:** `analysis/factor_analysis/ground_truth_validation.csv`

| Column | Description |
|--------|-------------|
| dataset | Dataset folder name |
| pvmap_file | PVMAP filename (basename) |
| status | PASS / FAIL / SKIP |
| data_rows | Number of data rows in processed.csv (0 if failed) |
| return_code | Process return code (-1 for timeout) |
| metadata_source | "ground_truth" or "input_fallback" or "none" |
| error | Short error description if failed/skipped, empty if passed |

**Markdown:** `analysis/ground_truth_validation_report.md`

Structure:
1. Summary line: "X of Y PVMAP files pass validation across Z datasets"
2. Results table (all rows from CSV)
3. Failures section: list datasets/PVMAPs that failed with reason
4. Metadata fallback section: list datasets that used input metadata
5. Skipped section: list datasets that couldn't be validated

Style: same anti-slop rules as the factor analysis doc. Plain English, tables, no filler.

## Out of Scope

- Comparing ground truth output vs generated output (that's a separate task)
- Fixing broken ground truth PVMAPs
- Warning log analysis (too verbose, not useful for this pass/fail check)
- Running on datasets outside the 48-dataset factor analysis set
