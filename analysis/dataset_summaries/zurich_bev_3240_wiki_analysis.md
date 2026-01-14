# zurich_bev_3240_wiki - Analysis

**Generated**: 2026-01-14T14:56:48.879861

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
  - p4: 1
  - p2: 1
  - p3: 1
  - statType: 1
  - measuredProperty: 1

### Properties Modified (Different values)
  - observationDate: 1
  - prop: 1
  - populationType: 1

## Generation Notes

```markdown
# zurich_bev_3240_wiki - PVMAP Generation Notes

Generated: 2026-01-13T23:44:41.922625

Total attempts: 1

---

I'll analyze the input data and generate a PV map to transform it into Data Commons format.

## Analysis

The input data contains:
- **StichtagDatJahr**: Year (date column)
- **AnzBestWir**: Number of establishments/businesses (numeric value)
- **wikiId**: Place identifier (Q692511 appears to be a Wikidata ID)

This is a **Pattern A: Flat Data** structure where each row is a complete observation.

The data appears to track the count of businesses/establishments over time for a location identified by Wikidata ID Q692511.

## PV Map

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
StichtagDatJahr,observationDate,{Data}
AnzBestWir,value,{Number},populationType,Establishment,measuredProperty,count,statType,measuredValue
wikiId,observationAbout,wikidataId/{Data}
```

**CHECKLIST:**
- [x] Keys exactly match input column headers (`StichtagDatJahr`, `AnzBestWir`, `wikiId`)
- [x] `value,{Number}` on value column (`AnzBestWir`)
- [x] `observationDate` mapped from date column (`StichtagDatJahr`)
- [x] `observationAbout` mapped from place column (`wikiId` → `wikidataId/{Data}`)
- [x] `populationType`, `measuredProperty`, `statType` on value column
- [x] No regex needed - direct mappings
- [x] No separate empty-key row for StatVar properties

```

## Diff Excerpt

```diff
- observationDate: {Number}
?                   ^^^^^^

+ observationDate: {Data}
?                   ^^^^



  observationAbout: dcid:wikidataId/{Data}


- p1: dcid:v1
?  ^        ^

+ p2: dcid:v2
?  ^        ^

+ p3: dcid:v3
+ p4: dcid:v4
- prop: dcid:val
+ prop: dcid:value
?               ++



- populationType: dcid:Person
?                      ^ ---

+ populationType: dcid:Establishment
?                      ^^^^^^^^^^  +

```

## Generation Logs

- `logs/zurich_bev_3240_wiki/generation_20260113_234430.log`
- `logs/zurich_bev_3240_wiki/generation_20260113_233148.log`
