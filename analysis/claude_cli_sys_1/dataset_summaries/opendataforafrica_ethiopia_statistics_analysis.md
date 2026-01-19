# opendataforafrica_ethiopia_statistics - Analysis

**Generated**: 2026-01-19T13:36:09.911716

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 95.2% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 21 |
| Nodes Auto-Generated | 21 |
| Nodes Matched | 0 |
| Nodes With Diff | 20 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 37 |
| PVs Added | 5 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 12
  - value: 12
  - populationType: 3
  - observationDate: 3
  - gender: 2
  - p1: 1
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1

### Properties Added (Extra in LLM output)
  - value: 1
  - property: 1
  - variableMeasured: 1
  - observationDate: 1
  - observationAbout: 1

## Generation Notes

```markdown
# opendataforafrica_ethiopia_statistics - PVMAP Generation Notes

Generated: 2026-01-16T17:09:35.457439

Total attempts: 1

---

```csv
key,property,value
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
```

**Analysis:**

This is **pre-formatted Data Commons data**. Detection criteria met:
- ✅ Has `variableMeasured` column with DCID values (`dcid:Count_Person_Rural`, `dcid:Count_Person`, `dcid:Count_Person_Female`, etc.)
- ✅ Has `observationAbout` column with place DCIDs (`country/ETH`, `wikidataId/Q3444726`, etc.)
- ✅ Has `observationDate` column with standard YYYY format
- ✅ Has `value` column with numeric measurements

**Passthrough mapping applied** - no StatVar construction needed since the data already contains fully-qualified `variableMeasured` DCIDs.

**Checklist verification:**
- ✅ Pre-formatted DC data detected → passthrough mapping used
- ✅ observationAbout mapped (passthrough from existing column)
- ✅ Keys exactly match input columns
- ✅ CSV formatting valid (simple passthrough, no special characters)
- ✅ Value column uses {Number} placeholder
- ✅ No StatVar properties added (would be incorrect for pre-formatted data)
- ✅ observationDate in YYYY format (passthrough)
- ✅ observationAbout uses valid DCIDs (already in data)
- ✅ No dynamic construction needed
- ✅ Property names match DC vocabulary (exact passthrough)

**Data quality notes:**
- Data spans 2000-2011 as indicated in config
- Mix of country-level (country/ETH) and regional data (wikidataId/* for Ethiopian regions)
- Multiple statistical variables present (rural population, total population, urban population, by gender)

```

## Diff Excerpt

```diff
+ 
- observationAbout: dcid:wikidataId/Q202107
- value: {Number}


+ 
- observationAbout: dcid:country/ETH
- value: {Number}


+ 
- populationType: dcid:Person
- gender: dcid:Male
- observationDate: 2022


- 
+ value: {Number}


+ 
- populationType: dcid:Person
- gender: dcid:Female
- observationDate: 2022


+ 
- observationAbout: dcid:wikidataId/Q193494
- value: {Number}


+ 
- observationAbout: dcid:wikidataId/Q762656
- value: {Number}


+ 
- observationAbout: dcid:wikidataId/Q203009
- value: {Number}


+ 
- observationAbout: dcid:wikidataId/Q203193
- value: {Number}


+ 
- observationAbout: dcid:wikidataId/Q207635
- value: {Number}


```

## Generation Logs

- `logs/opendataforafrica_ethiopia_statistics/generation_20260116_144355.log`
- `logs/opendataforafrica_ethiopia_statistics/generation_20260116_165001.log`
- `logs/opendataforafrica_ethiopia_statistics/generation_20260116_170922.log`
