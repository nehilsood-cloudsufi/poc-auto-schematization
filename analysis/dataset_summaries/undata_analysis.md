# undata - Analysis

**Generated**: 2026-01-14T14:56:48.869840

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 91.0% | 🟢 Excellent |
| Node Coverage | 95.5% | - |
| PV Accuracy | 90.3% | 🟢 Excellent |
| Precision | 92.4% | - |
| Recall | 90.3% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 89 |
| Nodes Auto-Generated | 7 |
| Nodes Matched | 81 |
| Nodes With Diff | 4 |
| Nodes Missing (LLM missed) | 4 |
| Nodes Extra (LLM added) | 1 |
| PVs Matched | 84 |
| PVs Modified | 1 |
| PVs Deleted | 8 |
| PVs Added | 7 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - Country: 1
  - measuredProperty: 1
  - populationType: 1
  - CityName: 1
  - placeOfResidenceClassification: 1
  - p1: 1
  - measurementMethod: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 1
  - GLOBAL: 1
  - prop: 1
  - p4: 1
  - measuredProperty: 1
  - statType: 1
  - populationType: 1

### Properties Modified (Different values)
  - observationDate: 1

## Generation Notes

```markdown
# undata - PVMAP Generation Notes

Generated: 2026-01-13T23:55:15.624796

Total attempts: 2

---

Looking at the error logs, the main issue is that the processor cannot resolve the place because the PVMAP is trying to create a dynamic place reference using `Åland Islands/{CityName}`, which doesn't work.

The errors show:
- "Unable to resolve place Åland Islands/{CityName}"
- "No place in SVObs" for all observations

The fix is to map the country name to its DCID directly in the `Country or Area` column, and since all rows are for cities within that country, we should map the city name directly as well. However, since we don't have city DCIDs, we'll need to use the country-level data.

Looking at the data more carefully:
- All rows are for "MARIEHAMN" city in "Åland Islands" 
- "Åland Islands" maps to country code "AX" → `country/AX`
- We should use the country as `observationAbout` since we don't have proper city DCIDs

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Country or Area:Åland Islands,observationAbout,country/AX
Year,observationDate,{Data}
Value,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
Both Sexes,gender,
Male,gender,Male
Female,gender,Female
```

```

## Diff Excerpt

```diff
  


  


  


  


  


  


  


  


  


  



```

## Generation Logs

- `logs/undata/generation_20260113_235448.log`
- `logs/undata/generation_20260113_234920.log`
