# india_ndap - Analysis

**Generated**: 2026-01-14T14:56:48.864125

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 3.3% | 🔴 Poor |
| Node Coverage | 10.0% | - |
| PV Accuracy | 12.1% | 🔴 Poor |
| Precision | 29.4% | - |
| Recall | 12.1% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 30 |
| Nodes Auto-Generated | 9 |
| Nodes Matched | 1 |
| Nodes With Diff | 2 |
| Nodes Missing (LLM missed) | 27 |
| Nodes Extra (LLM added) | 6 |
| PVs Matched | 4 |
| PVs Modified | 1 |
| PVs Deleted | 28 |
| PVs Added | 12 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 24
  - gender: 2
  - observationPeriod: 1
  - populationType: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 3
  - gender: 2
  - populationType: 1
  - statType: 1
  - p5: 1
  - p3: 1
  - p2: 1
  - p4: 1
  - GLOBAL: 1

### Properties Modified (Different values)
  - prop: 1

## Generation Notes

```markdown
# india_ndap - PVMAP Generation Notes

Generated: 2026-01-13T23:48:12.934142

Total attempts: 1

---

Looking at this input data, I need to create a PV map for life expectancy data across Indian states/UTs by year and gender.

## Data Structure Analysis

This is **Pattern A: Flat Data** - each row is a complete observation with:
- **Place**: `State/UT` column (e.g., "Jammu And Kashmir", "Delhi", "Himachal Pradesh")
- **Date**: `OBS_Year` column (e.g., 1997, 1998, 1999)
- **Gender**: `Gender` column (Male, Female, Total)
- **Value**: `Life expectancy in years` column

## Key Mapping Decisions

1. **Place Resolution**: Indian states need mapping to DCIDs. I'll use the wikidataId format that Data Commons uses for Indian administrative divisions.
2. **Gender Constraint**: Map to Data Commons gender properties
3. **Value Column**: Contains life expectancy measurements
4. **Empty Values**: Dataset has many empty value rows - these will be skipped by processor

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5
State/UT:Jammu And Kashmir,observationAbout,wikidataId/Q1180
State/UT:Delhi,observationAbout,wikidataId/Q1353
State/UT:Himachal Pradesh,observationAbout,wikidataId/Q1177
OBS_Year,observationDate,{Number}
Gender:Male,gender,Male
Gender:Female,gender,Female
Gender:Total,gender,""
Life expectancy in years,value,{Number},populationType,Person,measuredProperty,lifeExpectancy,statType,measuredValue,unit,Year
```

**CHECKLIST:**
- [x] Keys exactly match input column headers or cell values (using COLUMN:VALUE pattern)
- [x] `value,{Number}` on value column
- [x] `observationDate` mapped from OBS_Year column
- [x] `observationAbout` mapped from State/UT values
- [x] `populationType`, `measuredProperty`, `statType` on value column
- [x] No #Regex needed (direct mappings work)
- [x] No separate empty-key row for StatVar properties

```

## Diff Excerpt

```diff
- observationAbout: dcid:wikidataId/Q1499
+ 


- observationAbout: dcid:wikidataId/Q1356
+ 


- observationAbout: dcid:wikidataId/Q1186
+ 


- observationAbout: dcid:wikidataId/Q1437
+ 


- observationAbout: dcid:wikidataId/Q1184
+ 


- 
+ gender: dcid:Male


- observationAbout: dcid:wikidataId/Q1159
+ 


- observationAbout: dcid:wikidataId/Q1177
+ 

```

## Generation Logs

- `logs/india_ndap/generation_20260113_234758.log`
