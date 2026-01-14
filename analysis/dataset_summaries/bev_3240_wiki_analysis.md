# bev_3240_wiki - Analysis

**Generated**: 2026-01-14T14:56:48.856979

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 75.0% | - |
| PV Accuracy | 33.3% | 🟠 Needs Work |
| Precision | 60.0% | - |
| Recall | 33.3% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 4 |
| Nodes Auto-Generated | 3 |
| Nodes Matched | 0 |
| Nodes With Diff | 3 |
| Nodes Missing (LLM missed) | 1 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 2 |
| PVs Modified | 1 |
| PVs Deleted | 3 |
| PVs Added | 2 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - p1: 1
  - prop: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - measuredProperty: 1
  - statType: 1

### Properties Modified (Different values)
  - observationDate: 1

## Generation Notes

```markdown
# bev_3240_wiki - PVMAP Generation Notes

Generated: 2026-01-13T13:39:43.274847

---

Based on the search results, Q692511 refers to "Rathaus" - a quarter/neighborhood in Zurich, Switzerland. The data appears to be population counts for this area.

Looking at the URL in the processor configuration (`bev_3240_wiki.csv`), "bev" likely stands for "Bevölkerung" (German for population), confirming this is population data.

The column names in German:
- **StichtagDatJahr** = Reference date year
- **AnzBestWir** = Count of resident population (Anzahl Bestand Wohnbevölkerung)
- **wikiId** = Wikidata identifier for the place

Here's the pvmap.csv:

```
key,,,,,,
StichtagDatJahr,observationDate,{Data},,,,
AnzBestWir,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
wikiId,#Format,"observationAbout=wikidataId/{Data}",,,,
```

Wait, I need to reconsider the format. Let me provide a properly structured pvmap:

```
key,,,,,,,,
StichtagDatJahr,observationDate,{Data},,,,,,
AnzBestWir,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
wikiId,observationAbout,wikidataId/{Data},,,,,,
```

Sources:
- [Rathaus - Wikidata](https://www.wikidata.org/wiki/Q692511)

```

## Diff Excerpt

```diff
+ 
- p1: dcid:v1
- prop: dcid:val


  populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  value: {Number}


- observationAbout: dcid:wikidataId/{Data}
+ 


- observationDate: {Number}
?                   ^^^^^^

+ observationDate: {Data}
?                   ^^^^



```

## Generation Logs

No generation logs found.
