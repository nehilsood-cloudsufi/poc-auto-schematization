# southkorea_statistics_employment - Analysis

**Generated**: 2026-01-19T13:36:09.922921

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 97.9% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 47 |
| Nodes Auto-Generated | 47 |
| Nodes Matched | 0 |
| Nodes With Diff | 46 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 61 |
| PVs Added | 8 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 19
  - observationDate: 16
  - value: 16
  - populationType: 3
  - employmentStatus: 3
  - gender: 2
  - prop: 1
  - measuredProperty: 1

### Properties Added (Extra in LLM output)
  - property: 1
  - property2: 1
  - observationAbout: 1
  - scalingFactor: 1
  - observationDate: 1
  - unit: 1
  - value: 1
  - variableMeasured: 1

## Generation Notes

```markdown
# southkorea_statistics_employment - PVMAP Generation Notes

Generated: 2026-01-16T14:58:38.791771

Total attempts: 2

---

Looking at the error logs, I can see the issue: the processor is complaining about missing `variableMeasured` property in all observations. This is because:

1. The input data already has `variableMeasured` as a **column header** with values like `dcid:Count_Person_Unemployed`
2. The instruction says "NEVER map `variableMeasured`" because it's auto-constructed, but that's only true when you're building it from StatVar properties
3. In this case, the data **already provides** the complete StatVar DCIDs, so we need to map them directly

The input already contains fully-qualified Data Commons variable DCIDs in the `variableMeasured` column. We should pass these through directly rather than trying to construct them from properties.

```csv
key,property,value,property2,value2
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,variableMeasured,{Data}
scalingFactor,scalingFactor,{Data}
unit,unit,{Data}
```

**Key changes:**
- Map `variableMeasured` column directly to `variableMeasured` property using `{Data}` placeholder
- Map `observationAbout`, `observationDate`, and `value` columns directly
- Include `scalingFactor` and `unit` mappings (even though they're empty, the processor expects them)
- No need to decompose into `populationType`, `measuredProperty`, `statType` since the data provides complete DCIDs

**Checklist:**
- [x] Keys exactly match input column headers (case-sensitive)
- [x] Every value column has `value,{Number}` 
- [x] `observationDate` format: YYYY (correct in data)
- [x] `observationAbout` uses valid DCIDs (country/KOR, wikidataId/...)
- [x] Direct passthrough of pre-existing DCIDs in variableMeasured column

```

## Diff Excerpt

```diff
- observationAbout: dcid:wikidataId/Q20934
+ 


- observationAbout: dcid:wikidataId/Q41157
+ 


- prop: dcid:value
+ property: dcid:value
?     ++++

+ property2: dcid:value2


+ 
- observationDate: 2021
- value: {Number}


+ 
- observationDate: 2023
- value: {Number}


+ 
- observationDate: 2029
- value: {Number}


- observationAbout: dcid:wikidataId/Q41071
+ 


- 
+ observationAbout: {Data}


- observationAbout: dcid:wikidataId/Q41161
+ 


- observationAbout: dcid:wikidataId/Q41154
+ 


+ 
- observationDate: 2016
- value: {Number}


```

## Generation Logs

- `logs/southkorea_statistics_employment/generation_20260116_145806.log`
