# us_newyork_ny_diabetes - Analysis

**Generated**: 2026-01-14T14:56:48.874749

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 25.0% | 🟠 Needs Work |
| Node Coverage | 100.0% | - |
| PV Accuracy | 53.8% | 🟡 Good |
| Precision | 57.1% | - |
| Recall | 53.8% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 4 |
| Nodes Auto-Generated | 4 |
| Nodes Matched | 1 |
| Nodes With Diff | 3 |
| Nodes Missing (LLM missed) | 1 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 7 |
| PVs Modified | 1 |
| PVs Deleted | 5 |
| PVs Added | 6 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationDate: 1
  - p5: 1
  - p1: 1
  - unit: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - prop: 1
  - age: 1
  - observationDate: 1
  - statType: 1
  - observationAbout: 1
  - County: 1

### Properties Modified (Different values)
  - measuredProperty: 1

## Generation Notes

```markdown
# us_newyork_ny_diabetes - PVMAP Generation Notes

Generated: 2026-01-14T00:34:49.976718

Total attempts: 3

---

Looking at the error, the processor found no valid data rows because of incorrect key matching. The main issues are:

1. The column header is `"Percentage of adults with diabetes"` but I need to check if keys are matching exactly
2. The place names need to be resolved via the `ny_diabetes_place_resolver.csv` file
3. The `95% CI` column should be ignored

Let me analyze the input data structure:
- Column 1: `County` - contains county names
- Column 2: `Percentage of adults with diabetes` - the value column
- Column 3: `95% CI` - confidence interval (should ignore)

The key issue is that place resolution depends on the external CSV file. The PVMAP needs to:
1. Map the `County` column to capture the county name
2. Use the place resolver to get the observationAbout
3. Map the percentage column correctly

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
County,County,{Data}
Percentage of adults with diabetes,observationDate,2024,observationAbout,{County},value,{Number},populationType,Person,measuredProperty,count,age,Years18Onwards,healthOutcome,Diabetes,statType,measuredValue
95% CI,#ignore,skip
```

**Key changes:**
1. `County` column captures the county name into a `{County}` variable
2. `Percentage of adults with diabetes` column includes all required properties:
   - Sets `observationDate` to 2024 (not specified in data, using current year)
   - Uses `{County}` variable for place lookup (will be resolved via the place_resolver.csv)
   - Extracts numeric value with `value,{Number}`
   - Adds StatVar properties: `populationType,Person`, `measuredProperty,count`, `age,Years18Onwards`, `healthOutcome,Diabetes`, `statType,measuredValue`
3. `95% CI` column is ignored to skip confidence interval data

**Note:** The `observationAbout` will be resolved by the place resolver CSV file, which should map county names like "Albany" to their DCIDs (e.g., `geoId/36001`).

```

## Diff Excerpt

```diff
- observationDate: {Number}
+ 


  


- p1: dcid:v1
  p2: dcid:v2
  p3: dcid:v3
  p4: dcid:v4
- p5: dcid:v5
+ prop: dcid:value


  populationType: dcid:Person
- measuredProperty: dcid:percent
?                        --- ^

+ measuredProperty: dcid:count
?                         ^^

+ statType: dcid:measuredValue
+ age: dcid:Years18Onwards
  healthOutcome: dcid:Diabetes
- unit: dcid:Percent
+ observationAbout: {County}
+ observationDate: 2024
  value: {Number}


```

## Generation Logs

- `logs/us_newyork_ny_diabetes/generation_20260114_003355.log`
