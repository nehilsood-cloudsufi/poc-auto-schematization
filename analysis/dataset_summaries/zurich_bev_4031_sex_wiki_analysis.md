# zurich_bev_4031_sex_wiki - Analysis

**Generated**: 2026-01-14T14:56:48.883138

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 33.3% | 🟠 Needs Work |
| Node Coverage | 83.3% | - |
| PV Accuracy | 37.5% | 🟠 Needs Work |
| Precision | 26.1% | - |
| Recall | 37.5% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 6 |
| Nodes Auto-Generated | 17 |
| Nodes Matched | 2 |
| Nodes With Diff | 3 |
| Nodes Missing (LLM missed) | 1 |
| Nodes Extra (LLM added) | 12 |
| PVs Matched | 3 |
| PVs Modified | 3 |
| PVs Deleted | 2 |
| PVs Added | 17 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - p1: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 12
  - measuredProperty: 1
  - statType: 1
  - p3: 1
  - p2: 1
  - p4: 1

### Properties Modified (Different values)
  - populationType: 1
  - prop: 1
  - observationDate: 1

## Generation Notes

```markdown
# zurich_bev_4031_sex_wiki - PVMAP Generation Notes

Generated: 2026-01-14T00:42:02.275876

Total attempts: 1

---

Looking at this data, I need to map births by sex and place (identified by wikiID).

**Key observations:**
1. `Zeit` (German for "time") = year → `observationDate`
2. `Sex` = M/F → `gender` constraint
3. `bir` = birth count → `value` (numeric)
4. `wikiID` = Wikidata ID for places → needs to be mapped to `observationAbout`

**Data characteristics:**
- Each row represents birth count for a specific year, sex, and place
- This is **Pattern A: Flat Data** - one observation per row
- The `wikiID` contains Wikidata Q-codes that need to be resolved to Data Commons place DCIDs

**Critical limitation:** The processor cannot automatically resolve Wikidata IDs (Q-codes) to Data Commons DCIDs. You would need to either:
1. Pre-process the data to convert wikiIDs to DCIDs, or
2. Provide explicit mappings for each unique wikiID in the PVMAP

Since there are 12 unique wikiIDs in this sample, I'll note this limitation but provide the PVMAP structure that would work if you add the explicit mappings.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Zeit,observationDate,{Data}
bir,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
Sex:M,gender,Male
Sex:F,gender,Female
wikiID:Q692511,observationAbout,dcid/Q692511
wikiID:Q39240,observationAbout,dcid/Q39240
wikiID:Q10987378,observationAbout,dcid/Q10987378
wikiID:Q1093831,observationAbout,dcid/Q1093831
wikiID:Q642353,observationAbout,dcid/Q642353
wikiID:Q691367,observationAbout,dcid/Q691367
wikiID:Q648218,observationAbout,dcid/Q648218
wikiID:Q433012,observationAbout,dcid/Q433012
wikiID:Q693357,observationAbout,dcid/Q693357
wikiID:Q370104,observationAbout,dcid/Q370104
wikiID:Q531899,observationAbout,dcid/Q531899
wikiID:Q1805410,observationAbout,dcid/Q1805410
```

**IMPORTANT NOTE:** You must replace `dcid/QXXXXX` with the actual Data Commons DCIDs for these Wikidata entities. For example:
- If Q692511 corresponds to a specific district in Zurich, find its Data Commons DCID (e.g., `wikidataId/Q692511` or a proper geoId if available)
- The processor cannot automatically resolve Wikidata IDs to DCIDs

If the full dataset has more wikiIDs beyond these 12, you'll need to add mappings for all of them.

```

## Diff Excerpt

```diff
  gender: dcid:Male


  gender: dcid:Female


- 
+ observationAbout: dcid:dcid/Q642353


- 
+ observationAbout: dcid:dcid/Q648218


- 
+ observationAbout: dcid:dcid/Q39240


- 
+ observationAbout: dcid:dcid/Q692511


- 
+ observationAbout: dcid:dcid/Q691367


- 
+ observationAbout: dcid:dcid/Q370104



```

## Generation Logs

- `logs/zurich_bev_4031_sex_wiki/generation_20260114_004144.log`
