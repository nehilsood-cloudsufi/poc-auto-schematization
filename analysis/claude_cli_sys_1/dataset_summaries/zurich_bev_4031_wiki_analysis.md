# zurich_bev_4031_wiki - Analysis

**Generated**: 2026-01-19T13:36:09.958211

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 25.0% | 🟠 Needs Work |
| Node Coverage | 100.0% | - |
| PV Accuracy | 33.3% | 🟠 Needs Work |
| Precision | 50.0% | - |
| Recall | 33.3% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 4 |
| Nodes Auto-Generated | 4 |
| Nodes Matched | 1 |
| Nodes With Diff | 3 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 2 |
| PVs Modified | 3 |
| PVs Deleted | 1 |
| PVs Added | 5 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - p1: 1

### Properties Added (Extra in LLM output)
  - statType: 1
  - measuredProperty: 1
  - p2: 1
  - p3: 1
  - p4: 1

### Properties Modified (Different values)
  - populationType: 1
  - prop: 1
  - observationDate: 1

## Generation Notes

```markdown
# zurich_bev_4031_wiki - PVMAP Generation Notes

Generated: 2026-01-14T00:42:32.005259

Total attempts: 1

---

Looking at this dataset, I need to understand what each column represents:

- `Zeit` = Time (year)
- `bir` = appears to be a numeric value (likely birth-related count)
- `wikiID` = Wikidata IDs (e.g., Q692511, Q39240)

The config indicates:
- `place_type=Country` 
- Import name suggests this is about births in Zurich
- `observationAbout` should reference places

However, there's a **critical issue**: The Wikidata IDs in the data appear to be for individual people or entities, NOT countries. For example:
- Q39240 is likely a person
- Q692511 is likely a person

This doesn't match the `place_type=Country` setting. The data structure suggests births BY nationality or country of origin, but the wikiID column contains person/entity IDs rather than country IDs.

**Assumption**: I'll assume the `wikiID` should map to countries (perhaps these are supposed to be country Q-codes), and the processor will resolve them. The `bir` column is the birth count.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Zeit,observationDate,{Data}
bir,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
wikiID,observationAbout,wikidataId/{Data}
```

**CRITICAL LIMITATION NOTED**: 

The `wikiID` column contains Wikidata IDs that appear to reference individual entities rather than countries. If these Q-codes are indeed for people or non-place entities, the processor will fail to create valid observations because `observationAbout` requires place DCIDs. 

**To fix this dataset**, you would need to:
1. Verify what these Wikidata IDs represent
2. If they represent countries of origin, map them explicitly (e.g., `wikiID:Q39240,observationAbout,country/XXX`)
3. If they represent something else entirely, the data structure needs clarification about what place these births are associated with (likely all births are in Zurich, so you might need `observationAbout,wikidataId/Q72` for all rows)

```

## Diff Excerpt

```diff
  observationAbout: dcid:wikidataId/{Data}


- populationType: dcid:BirthEvent
?                      ^^ ^^^^^ -

+ populationType: dcid:Person
?                      ^^ ^^

+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  value: {Number}


- p1: dcid:v1
?  ^        ^

+ p2: dcid:v2
?  ^        ^

+ p3: dcid:v3
+ p4: dcid:v4
- prop: dcid:val
+ prop: dcid:value
?               ++



- observationDate: {Number}
?                   ^^^^^^

+ observationDate: {Data}
?                   ^^^^



```

## Generation Logs

- `logs/zurich_bev_4031_wiki/generation_20260114_004214.log`
