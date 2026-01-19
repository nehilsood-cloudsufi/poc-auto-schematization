# zurich_wir_2552_wiki - Analysis

**Generated**: 2026-01-19T13:36:09.959005

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 10.0% | 🔴 Poor |
| Node Coverage | 100.0% | - |
| PV Accuracy | 64.3% | 🟢 Good |
| Precision | 55.1% | - |
| Recall | 64.3% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 10 |
| Nodes Auto-Generated | 10 |
| Nodes Matched | 1 |
| Nodes With Diff | 9 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 18 |
| PVs Modified | 9 |
| PVs Deleted | 1 |
| PVs Added | 22 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - p1: 1

### Properties Added (Extra in LLM output)
  - measuredProperty: 7
  - statType: 7
  - measurementMethod: 3
  - p6: 1
  - p4: 1
  - p3: 1
  - p5: 1
  - p2: 1

### Properties Modified (Different values)
  - employmentStatus: 6
  - populationType: 1
  - observationDate: 1
  - prop: 1

## Generation Notes

```markdown
# zurich_wir_2552_wiki - PVMAP Generation Notes

Generated: 2026-01-14T00:43:02.208940

Total attempts: 1

---

Looking at this input data, I can see it's time series data about companies and employment statistics in Zurich, with a breakdown by gender. Each row represents a year with metrics for different Wikipedia entities (wikiId).

**Data Analysis:**
- **Date column**: `Zeit` (German for "Time") contains years
- **Place**: The data is about Zurich entities identified by `wikiId` - these appear to be district/area identifiers
- **Value columns**: Multiple metrics - `companies`, `employees`, `employees_f` (female), `employees_m` (male), `fte` (full-time equivalent), `fte_f`, `fte_m`
- **Pattern**: Wide data format (Pattern B) with multiple value columns

**Key Decisions:**
1. `wikiId` needs to be mapped to `observationAbout` - these are Wikidata IDs (e.g., Q692511), so I'll use `wikidataId/{Data}` format
2. Each value column represents a different statistical variable with different constraints
3. Gender breakdowns need `gender` constraint property
4. FTE vs headcount employees are different measurement methods

**Limitations Noted:**
- The `wikiId` values are Wikidata identifiers that may need verification for proper DCID resolution
- If these don't resolve properly in Data Commons, explicit mappings may be needed

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
Zeit,observationDate,{Data}
wikiId,observationAbout,wikidataId/{Data}
companies,value,{Number},populationType,BLSEstablishment,measuredProperty,count,statType,measuredValue
employees,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,employmentStatus,BLS_Employed
employees_f,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,employmentStatus,BLS_Employed,gender,Female
employees_m,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,employmentStatus,BLS_Employed,gender,Male
fte,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,employmentStatus,BLS_Employed,measurementMethod,FullTimeEquivalent
fte_f,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,employmentStatus,BLS_Employed,measurementMethod,FullTimeEquivalent,gender,Female
fte_m,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,employmentStatus,BLS_Employed,measurementMethod,FullTimeEquivalent,gender,Male
```

**Checklist:**
- [x] Keys exactly match input column headers (`Zeit`, `wikiId`, `companies`, etc.)
- [x] No special characters requiring quoting
- [x] `value,{Number}` on all value columns
- [x] `observationDate` mapped from `Zeit` column
- [x] `observationAbout` mapped from `wikiId` column using wikidataId format
- [x] `populationType`, `measuredProperty`, `statType` on each value column
- [x] Gender constraints (`Female`, `Male`) applied to gendered columns
- [x] FTE measurement method distinguished from headcount
- [x] No #Regex ne...
```

## Diff Excerpt

```diff
  populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
- employmentStatus: dcid:Employed
+ employmentStatus: dcid:BLS_Employed
?                        ++++

  value: {Number}


- populationType: dcid:Company
+ populationType: dcid:BLSEstablishment
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  value: {Number}


  populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
- employmentStatus: dcid:FullTimeEmployee
?                        ^^^^^^^^       ^

+ employmentStatus: dcid:BLS_Employed
?                        ^^^^       ^

  gender: dcid:Female
+ measurementMethod: dcid:FullTimeEquivalent
  value: {Number}


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
+ p5: dcid:v5
+ p6: dcid:v6
- prop: dcid:val

```

## Generation Logs

- `logs/zurich_wir_2552_wiki/generation_20260114_004243.log`
