# usa_dol - Analysis

**Generated**: 2026-01-19T13:36:09.949120

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
| Nodes Ground Truth | 69 |
| Nodes Auto-Generated | 69 |
| Nodes Matched | 0 |
| Nodes With Diff | 68 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 127 |
| PVs Added | 12 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 58
  - value: 58
  - observationDate: 4
  - populationType: 1
  - measuredProperty: 1
  - unit: 1
  - p1: 1
  - p2: 1
  - p3: 1
  - p4: 1

### Properties Added (Extra in LLM output)
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - value: 1
  - observationDate: 1
  - observationAbout: 1
  - property: 1
  - property2: 1
  - property3: 1
  - property4: 1
  - unit: 1
  - scalingFactor: 1

## Generation Notes

```markdown
# usa_dol - PVMAP Generation Notes

Generated: 2026-01-16T15:22:10.877378

Total attempts: 1

---

Looking at this data, I can see it's already in a clean, structured format with observations about minimum wages for US states over time. The `variableMeasured` column contains `dcid:MinimumWage_Person` which indicates the StatVar is already defined.

Let me analyze the structure:
- **observationAbout**: Already contains geoId values (US states/territories)
- **observationDate**: Years (1968-1996 in the sample)
- **variableMeasured**: Contains `dcid:MinimumWage_Person` (pre-defined StatVar)
- **value**: The minimum wage amount
- **unit**: `USDollarPerHour`
- **scalingFactor**: Empty (meaning no scaling)

Since `variableMeasured` contains a DCID reference, I need to map the columns to extract the StatVar properties and create proper observations.

```csv
key,property,value,property2,value2,property3,value3,property4,value4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number},populationType,Person,measuredProperty,minimumWage,statType,measuredValue
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
```

**Notes:**
- The `observationAbout` column already contains proper DCIDs (geoId format), so it can be passed through directly
- The `observationDate` column contains years in YYYY format, which is valid
- The `value` column is mapped with all required StatVar properties:
  - `populationType`: Person (minimum wage applies to persons/workers)
  - `measuredProperty`: minimumWage (the property being measured)
  - `statType`: measuredValue (this is a measured value, not a statistical aggregation)
- The `unit` and `scalingFactor` are passed through as-is
- The `variableMeasured` column is intentionally not mapped (as per instructions: "NEVER map `variableMeasured`")

```

## Diff Excerpt

```diff
+ 
- observationAbout: dcid:geoId/56
- value: {Number}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:minimumWage
+ statType: dcid:measuredValue
+ value: {Number}


+ 
- observationAbout: dcid:geoId/11
- value: {Number}


+ 
- observationAbout: dcid:geoId/10
- value: {Number}


+ 
- observationAbout: dcid:geoId/26
- value: {Number}


+ 
- observationAbout: dcid:geoId/05
- value: {Number}


+ 
- observationAbout: dcid:geoId/29
- value: {Number}


+ 
- observationAbout: dcid:geoId/32
- value: {Number}


+ 
- observationAbout: dcid:geoId/42
- value: {Number}


+ 
- observationAbout: dcid:geoId/01
- value: {Number}

```

## Generation Logs

- `logs/usa_dol/generation_20260116_152158.log`
