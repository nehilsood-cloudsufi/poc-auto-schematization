# mexico_subnational_population_statistics_mexico_census_aa2 - Analysis

**Generated**: 2026-01-19T13:36:09.900351

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 98.6% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 72 |
| Nodes Auto-Generated | 72 |
| Nodes Matched | 0 |
| Nodes With Diff | 71 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 164 |
| PVs Added | 8 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - value: 60
  - age: 57
  - gender: 40
  - GLOBAL: 2
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - observationAbout: 1
  - observationDate: 1

### Properties Added (Extra in LLM output)
  - property: 1
  - property2: 1
  - value: 1
  - observationDate: 1
  - unit: 1
  - variableMeasured: 1
  - scalingFactor: 1
  - observationAbout: 1

## Generation Notes

```markdown
# mexico_subnational_population_statistics_mexico_census_aa2 - PVMAP Generation Notes

Generated: 2026-01-16T14:31:35.802857

Total attempts: 1

---

Looking at this input data, I can see it's **already in Data Commons format** with:
- `observationAbout` containing DCIDs (wikidataId/Q391149, wikidataId/Q8206694)
- `observationDate` with years
- `value` with counts
- `variableMeasured` containing StatVar DCIDs (dcid:Count_Person_Female, etc.)

The `variableMeasured` column contains complete StatVar definitions that already encode all the properties (populationType, measuredProperty, statType, and constraints like age/gender).

Since the processor **auto-constructs `variableMeasured`** and you should **NEVER map it**, but this data already has it pre-populated, the PV map is minimal:

```csv
key,property,value,property2,value2
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,variableMeasured,{Data}
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
```

**CHECKLIST:**
- [x] Keys exactly match input (case-sensitive)
- [x] Special char keys are double-quoted (none needed)
- [x] `observationDate` format: YYYY ✓
- [x] `observationAbout` uses valid DCID ✓
- [x] No dynamic place construction ✓

**Note:** This is an unusual case where the input is already in DC format. Typically you'd extract StatVar properties from column headers/values, but here `variableMeasured` is pre-populated with complete DCIDs. The processor will pass these through as-is.

```

## Diff Excerpt

```diff
+ 
- age: dcid:Years0To4
- gender: dcid:Female
- value: {Number}


+ 
- age: dcid:Years45To49
- value: {Number}


+ 
- age: dcid:Years65Onwards
- gender: dcid:Female
- value: {Number}


- 
+ property: dcid:value
+ property2: dcid:value2


+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- statType: dcid:measuredValue
- observationAbout: {Data}


+ 
- age: dcid:Years55To59
- gender: dcid:Female
- value: {Number}


- GLOBAL: 2
+ 


+ 
- age: dcid:Years50To54
- gender: dcid:Male
- value: {Number}


- 
+ value: {Number}


+ 

```

## Generation Logs

- `logs/mexico_subnational_population_statistics_mexico_census_aa2/generation_20260116_143123.log`
