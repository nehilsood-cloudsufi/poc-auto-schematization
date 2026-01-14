# nyu_diabetes_texas - Analysis

**Generated**: 2026-01-14T14:56:48.867320

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 4.7% | - |
| PV Accuracy | 4.1% | 🔴 Poor |
| Precision | 28.1% | - |
| Recall | 4.1% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 274 |
| Nodes Auto-Generated | 14 |
| Nodes Matched | 0 |
| Nodes With Diff | 13 |
| Nodes Missing (LLM missed) | 261 |
| Nodes Extra (LLM added) | 1 |
| PVs Matched | 12 |
| PVs Modified | 13 |
| PVs Deleted | 268 |
| PVs Added | 64 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 254
  - observationDate: 6
  - value: 6
  - populationType: 1
  - causeOfDeath: 1

### Properties Added (Extra in LLM output)
  - populationType: 12
  - observationAbout: 12
  - measuredProperty: 12
  - statType: 12
  - causeOfDeath: 12
  - p4: 1
  - p2: 1
  - p3: 1
  - County: 1

### Properties Modified (Different values)
  - observationDate: 12
  - prop: 1

## Generation Notes

```markdown
# nyu_diabetes_texas - PVMAP Generation Notes

Generated: 2026-01-14T00:13:14.192533

Total attempts: 1

---

I'll analyze this Texas death certificate data and create a PV map for diabetes mellitus mortality by county and year.

## Data Analysis

**Structure**: Wide format with:
- County names in first column
- Years 2011-2022 as column headers with numeric death counts
- Fixed cause of death: "Diabetes mellitus"
- Suppression markers: `--` (suppressed), `0` (zero deaths)

**Key observations**:
1. Footer metadata rows present (Notes and Source info in first 3 rows) - will cause errors but unavoidable
2. Values `--` and `0` are non-numeric markers - will be skipped (expected behavior)
3. Need to map Texas county names to geoId format
4. Each numeric cell = count of mortality events for diabetes in that county/year

## Limitations

⚠️ **Footer rows**: Rows 2-3 contain metadata ("Leading Causes Foot Note", "Source:") that don't match the county/year structure. These will cause processing errors but cannot be filtered via PVMAP.

⚠️ **County name mappings**: Texas has 254 counties. Providing explicit mappings for all would be impractical. The processor should attempt dynamic resolution of `{Data}` → county geoId, but some may fail without a complete lookup table.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Geographic Area,County,{Data}
2011,observationDate,2011-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2012,observationDate,2012-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2013,observationDate,2013-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2014,observationDate,2014-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2015,observationDate,2015-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2016,observationDate,2016-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2017,observationDate,2017-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2018,observationDate,2018-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2019,observationDate,2019-01-01,observationAbout,geoId/48/{County},value,{Number},populationType,MortalityEvent,measuredProperty,count,statType,measuredValue,causeOfDeath,Diabetes
2020,observationDate,2020-01
```

## Diff Excerpt

```diff
+ populationType: dcid:MortalityEvent
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ causeOfDeath: dcid:Diabetes
+ observationAbout: dcid:geoId/48/{County}
- observationDate: 2021
+ observationDate: 2021-01-01
?                      ++++++

  value: {Number}


- observationAbout: dcid:geoId/48007
+ 


- observationAbout: dcid:geoId/48399
+ 


- observationAbout: dcid:geoId/48235
+ 


- observationAbout: dcid:geoId/48385
+ 


- observationAbout: dcid:geoId/48435
+ 

```

## Generation Logs

- `logs/nyu_diabetes_texas/generation_20260114_001245.log`
