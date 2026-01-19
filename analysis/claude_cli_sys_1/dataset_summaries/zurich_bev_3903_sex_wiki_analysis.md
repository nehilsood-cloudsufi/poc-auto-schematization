# zurich_bev_3903_sex_wiki - Analysis

**Generated**: 2026-01-19T13:36:09.955514

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 16.7% | 🔴 Poor |
| Node Coverage | 66.7% | - |
| PV Accuracy | 37.5% | 🟠 Needs Work |
| Precision | 41.7% | - |
| Recall | 37.5% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 6 |
| Nodes Auto-Generated | 6 |
| Nodes Matched | 1 |
| Nodes With Diff | 3 |
| Nodes Missing (LLM missed) | 2 |
| Nodes Extra (LLM added) | 2 |
| PVs Matched | 3 |
| PVs Modified | 2 |
| PVs Deleted | 3 |
| PVs Added | 7 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - gender: 2
  - p1: 1

### Properties Added (Extra in LLM output)
  - gender: 2
  - p2: 1
  - p3: 1
  - p4: 1
  - statType: 1
  - measuredProperty: 1

### Properties Modified (Different values)
  - observationDate: 1
  - prop: 1

## Generation Notes

```markdown
# zurich_bev_3903_sex_wiki - PVMAP Generation Notes

Generated: 2026-01-14T00:41:06.834783

Total attempts: 1

---

Looking at this data, I need to understand the structure:

- `Zeit` = year (observation date)
- `Sex` = gender (M/W for Male/Female)
- `pop` = population value
- `wikiID` = Wikidata ID for the place

This is a flat data pattern (one observation per row) where each row contains a complete observation.

**Key observations:**
1. The `wikiID` column contains Wikidata IDs (Q-codes) that need to be mapped to Data Commons place DCIDs
2. Gender values are in German: `M` (Male), `W` (Female)
3. Each row is a complete observation with date, place, gender, and value

**Limitations noted:**
- The `wikiID` values are Wikidata identifiers. The processor will attempt to resolve these, but if resolution fails, you may need to provide explicit mappings from Wikidata IDs to Data Commons DCIDs for each place.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Zeit,observationDate,{Data}
pop,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
wikiID,observationAbout,wikidataId/{Data}
M,gender,Male
W,gender,Female
```

**Checklist:**
- [x] Keys exactly match input column headers (`Zeit`, `Sex`, `pop`, `wikiID`) and cell values (`M`, `W`)
- [x] No special characters requiring quoting
- [x] `value,{Number}` on value column (`pop`)
- [x] `observationDate` mapped from `Zeit` column
- [x] `observationAbout` mapped from `wikiID` column using wikidataId prefix
- [x] `populationType,Person`, `measuredProperty,count`, `statType,measuredValue` on value column
- [x] No #Regex needed (direct value mapping)
- [x] StatVar properties correctly placed on value column row

```

## Diff Excerpt

```diff
- 
+ gender: dcid:Female


- gender: dcid:Male
+ 


- 
+ gender: dcid:Male


- observationDate: {Number}
?                   ^^^^^^

+ observationDate: {Data}
?                   ^^^^



- p1: dcid:v1
?  ^        ^

+ p2: dcid:v2
?  ^        ^

+ p3: dcid:v3
+ p4: dcid:v4
- prop: dcid:val
+ prop: dcid:value
?               ++



- gender: dcid:Female
+ 


  populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  value: {Number}


  observationAbout: dcid:wikidataId/{Data}


```

## Generation Logs

- `logs/zurich_bev_3903_sex_wiki/generation_20260114_004053.log`
