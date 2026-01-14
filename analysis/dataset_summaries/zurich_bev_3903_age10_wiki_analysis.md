# zurich_bev_3903_age10_wiki - Analysis

**Generated**: 2026-01-14T14:56:48.880683

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 26.7% | - |
| PV Accuracy | 11.8% | 🔴 Poor |
| Precision | 20.0% | - |
| Recall | 11.8% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 15 |
| Nodes Auto-Generated | 15 |
| Nodes Matched | 0 |
| Nodes With Diff | 4 |
| Nodes Missing (LLM missed) | 11 |
| Nodes Extra (LLM added) | 11 |
| PVs Matched | 2 |
| PVs Modified | 2 |
| PVs Deleted | 13 |
| PVs Added | 16 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - age: 11
  - p1: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - age: 11
  - p4: 1
  - p3: 1
  - p2: 1
  - measuredProperty: 1
  - statType: 1

### Properties Modified (Different values)
  - prop: 1
  - observationDate: 1

## Generation Notes

```markdown
# zurich_bev_3903_age10_wiki - PVMAP Generation Notes

Generated: 2026-01-14T00:03:51.273544

Total attempts: 2

---

Looking at the error logs, the issue is clear: **every observation has "No place in SVObs"**. This means the `wikiID` column values are not being mapped to `observationAbout`.

The problem is that the `wikiID` column contains Wikidata QIDs (Q692511, Q39240, Q10987378), which need to be converted to Data Commons place DCIDs. Wikidata entities use the format `wikidataId/{QID}` in Data Commons.

Additionally, I need to map the age range values properly.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Zeit,observationDate,{Data}
pop,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
wikiID,#Format,observationAbout=wikidataId/{Data}
Age10:0-9,age,Years0To9
Age10:10-19,age,Years10To19
Age10:20-29,age,Years20To29
Age10:30-39,age,Years30To39
Age10:40-49,age,Years40To49
Age10:50-59,age,Years50To59
Age10:60-69,age,Years60To69
Age10:70-79,age,Years70To79
Age10:80-89,age,Years80To89
Age10:90-99,age,Years90To99
Age10:100 and above,age,Years100Onwards
```

```

## Diff Excerpt

```diff
- age: dcid:Years90To99
+ 


- 
+ age: dcid:Years10To19


- age: dcid:Years100Onwards
+ 


- age: dcid:Years70To79
+ 


- 
+ age: dcid:Years50To59


- age: dcid:Years10To19
+ 


- age: dcid:Years20To29
+ 


- age: dcid:Years50To59
+ 

```

## Generation Logs

- `logs/zurich_bev_3903_age10_wiki/generation_20260114_000326.log`
