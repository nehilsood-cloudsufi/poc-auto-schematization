# zurich_bev_4031_hel_wiki - Analysis

**Generated**: 2026-01-14T14:56:48.882544

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 16.7% | 🔴 Poor |
| Node Coverage | 100.0% | - |
| PV Accuracy | 25.0% | 🟠 Needs Work |
| Precision | 41.7% | - |
| Recall | 25.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 6 |
| Nodes Auto-Generated | 6 |
| Nodes Matched | 1 |
| Nodes With Diff | 5 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 2 |
| PVs Modified | 3 |
| PVs Deleted | 3 |
| PVs Added | 7 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - nativity: 2
  - p1: 1

### Properties Added (Extra in LLM output)
  - origin: 2
  - statType: 1
  - measuredProperty: 1
  - p3: 1
  - p4: 1
  - p2: 1

### Properties Modified (Different values)
  - populationType: 1
  - prop: 1
  - observationDate: 1

## Generation Notes

```markdown
# zurich_bev_4031_hel_wiki - PVMAP Generation Notes

Generated: 2026-01-14T00:41:31.715438

Total attempts: 1

---

Looking at this data, I need to understand the structure:

- `Zeit` = Year (1998)
- `Hel` = Origin/nationality (Swiss, Foreign)
- `bir` = Birth count (numeric value)
- `wikiID` = Place identifier (Wikidata IDs like Q692511, Q39240, etc.)

This is **Pattern A: Flat Data** where each row is a complete observation. The data measures birth counts by origin (Swiss vs Foreign) for different places identified by Wikidata IDs.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Zeit,observationDate,{Data}
wikiID,observationAbout,wikidataId/{Data}
bir,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
Swiss,origin,Swiss
Foreign,origin,Foreign
```

**Notes:**

1. **Place resolution**: The `wikiID` column contains Wikidata identifiers (Q692511, Q39240, etc.). These are mapped using `wikidataId/{Data}` which allows the processor to resolve Wikidata IDs to Data Commons place DCIDs.

2. **Origin constraint**: The `Hel` column values (Swiss, Foreign) are mapped to an `origin` property to distinguish between births by Swiss nationals vs foreign nationals.

3. **Data pattern**: Each row represents births in a specific place for a specific origin group in 1998.

4. **All required properties present**: 
   - `observationDate` from Zeit column
   - `observationAbout` from wikiID column  
   - `value` from bir column
   - StatVar properties (`populationType`, `measuredProperty`, `statType`) on the bir column header

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


- nativity: dcid:ForeignBorn
+ origin: dcid:Foreign


- p1: dcid:v1
?  ^        ^

+ p2: dcid:v2
?  ^        ^

+ p3: dcid:v3
+ p4: dcid:v4
- prop: dcid:val
+ prop: dcid:value
?               ++


```

## Generation Logs

- `logs/zurich_bev_4031_hel_wiki/generation_20260114_004118.log`
