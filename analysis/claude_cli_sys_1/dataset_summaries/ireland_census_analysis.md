# ireland_census - Analysis

**Generated**: 2026-01-19T13:36:09.899248

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 93.8% | - |
| PV Accuracy | 15.4% | 🔴 Poor |
| Precision | 18.2% | - |
| Recall | 15.4% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 16 |
| Nodes Auto-Generated | 16 |
| Nodes Matched | 0 |
| Nodes With Diff | 15 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 2 |
| PVs Modified | 0 |
| PVs Deleted | 11 |
| PVs Added | 9 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - gender: 2
  - GLOBAL: 2
  - populationType: 1
  - measuredProperty: 1
  - causeOfDeath: 1
  - p1: 1
  - observationDate: 1
  - value: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - p4: 1
  - p5: 1
  - property: 1
  - observationDate: 1
  - observationAbout: 1
  - variableMeasured: 1
  - value: 1
  - unit: 1
  - scalingFactor: 1

## Generation Notes

```markdown
# ireland_census - PVMAP Generation Notes

Generated: 2026-01-16T14:30:20.664047

Total attempts: 1

---

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,variableMeasured,{Data}
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
```

**Analysis:**

This input data is already in **Data Commons format** - it contains complete StatVarObservation nodes with all required properties already populated:

- `observationAbout`: Already contains DCIDs (country/IRL, wikidataId/Q181882, etc.)
- `observationDate`: Already populated (1981, 1986, 2006)
- `value`: Already contains numeric values
- `variableMeasured`: Already contains the StatVar DCID (dcid:Count_Person_15OrMoreYears)
- `unit`: Present but empty (appropriate for counts)
- `scalingFactor`: Present but empty (meaning 1:1 scale)

**Key Insight:** Since `variableMeasured` is already provided as a complete DCID, the processor will use it directly rather than constructing a new StatVar. This is a **pass-through** schema where all columns map directly to their properties using `{Data}` or `{Number}` placeholders.

**No transformation needed** - the PV map simply passes each column through to its corresponding property. The processor will handle the "dcid:" prefix removal automatically when parsing the observationAbout and variableMeasured values.

```

## Diff Excerpt

```diff
+ 
- populationType: dcid:MortalityEvent
- measuredProperty: dcid:count
- causeOfDeath: dcid:Suicide


- p1: dcid:v1
  p2: dcid:v2
  p3: dcid:v3
+ p4: dcid:v4
+ p5: dcid:v5
+ property: dcid:value


- observationDate: {Number}
+ 


- gender: dcid:Male
+ 


- value: {Number}
+ 


- gender: dcid:Female
+ 


- 
+ observationDate: {Data}


- 
+ observationAbout: {Data}


- 
+ variableMeasured: {Data}


- 
+ value: {Number}


- 
+ unit: {Data}



```

## Generation Logs

- `logs/ireland_census/generation_20260116_143009.log`
