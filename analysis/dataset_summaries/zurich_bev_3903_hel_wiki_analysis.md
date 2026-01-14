# zurich_bev_3903_hel_wiki - Analysis

**Generated**: 2026-01-14T14:56:48.881464

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 50.0% | - |
| PV Accuracy | 20.0% | 🔴 Poor |
| Precision | 36.4% | - |
| Recall | 20.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 8 |
| Nodes Auto-Generated | 6 |
| Nodes Matched | 0 |
| Nodes With Diff | 4 |
| Nodes Missing (LLM missed) | 4 |
| Nodes Extra (LLM added) | 2 |
| PVs Matched | 2 |
| PVs Modified | 2 |
| PVs Deleted | 6 |
| PVs Added | 7 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - nativity: 4
  - p1: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - citizenship: 2
  - statType: 1
  - measuredProperty: 1
  - p3: 1
  - p4: 1
  - p2: 1

### Properties Modified (Different values)
  - observationDate: 1
  - prop: 1

## Generation Notes

```markdown
# zurich_bev_3903_hel_wiki - PVMAP Generation Notes

Generated: 2026-01-14T00:40:38.987665

Total attempts: 1

---

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Zeit,observationDate,{Data}
wikiID,#Format,"observationAbout=wikidataId/{Data}"
pop,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
Hel:Schweizer*in,citizenship,SwissCitizen
Hel:Ausländer*in,citizenship,NotASwissCitizen
```

**Notes:**

1. **Place Resolution**: Using `wikidataId/{Data}` format for the wikiID column, which contains Wikidata IDs (Q692511, Q39240, etc.)

2. **Citizenship Constraint**: The `Hel` column contains citizenship status values. Using column-prefixed keys `Hel:Schweizer*in` and `Hel:Ausländer*in` to map to the citizenship constraint property

3. **StatVar Properties**: All required properties (`populationType`, `measuredProperty`, `statType`) are on the `pop` column header row, so they apply to all observations

4. **Date Format**: The `Zeit` column contains years (1993), which will be used directly as observation dates

5. **Language Note**: The data is in German:
   - "Schweizer*in" = Swiss citizen
   - "Ausländer*in" = Foreign national
   - The gender-inclusive asterisk (*in) notation is preserved in the keys

**Data Characteristics:**
- Wide format: Each row contains complete observation data
- 24 observations total (2 citizenship categories × 12 places)
- All measurements from 1993
- Population counts by citizenship status and municipality (Wikidata entities)

```

## Diff Excerpt

```diff
- nativity: dcid:ForeignBorn
+ 


- 
+ citizenship: dcid:SwissCitizen


  populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  value: {Number}


- observationDate: {Number}
?                   ^^^^^^

+ observationDate: {Data}
?                   ^^^^



- nativity: dcid:Native
+ 


- nativity: dcid:ForeignBorn
+ 



```

## Generation Logs

- `logs/zurich_bev_3903_hel_wiki/generation_20260114_004025.log`
