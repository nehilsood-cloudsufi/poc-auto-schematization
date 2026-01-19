# inpe_fire - Analysis

**Generated**: 2026-01-19T13:36:09.896837

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 12.5% | 🔴 Poor |
| Node Coverage | 45.8% | - |
| PV Accuracy | 44.3% | 🟢 Good |
| Precision | 46.6% | - |
| Recall | 44.3% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 48 |
| Nodes Auto-Generated | 32 |
| Nodes Matched | 6 |
| Nodes With Diff | 16 |
| Nodes Missing (LLM missed) | 29 |
| Nodes Extra (LLM added) | 13 |
| PVs Matched | 35 |
| PVs Modified | 13 |
| PVs Deleted | 31 |
| PVs Added | 55 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 30
  - variableMeasured: 1

### Properties Added (Extra in LLM output)
  - statType: 13
  - measuredProperty: 13
  - populationType: 13
  - observationAbout: 13
  - Place: 1
  - p4: 1
  - p3: 1

### Properties Modified (Different values)
  - value: 13

## Generation Notes

```markdown
# inpe_fire - PVMAP Generation Notes

Generated: 2026-01-14T00:54:11.786779

Total attempts: 2

---

Looking at the errors, the processor is correctly parsing the data but failing with "Unable to resolve place" errors like `geoId/BR-AC`, `geoId/BR-AL`, etc. This is because the place DCIDs in Data Commons use ISO 3166-2 format with a dash (e.g., `BR-AC` for Acre state in Brazil), but they need to be resolved through the API or mapped correctly.

However, the core issue is that **all rows are being dropped** because the place resolution is failing. The processor is generating the correct DCID format (`geoId/BR-AC`), but these may not exist in Data Commons or the processor cannot resolve them.

Let me also check the input data more carefully - I notice rows like `Máximo*`, `Média*`, `Mínimo*` which are statistical summaries, not actual place names. These should be ignored.

Here's the corrected PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
year,Year,{Number}
place,Place,{Data}
Janeiro,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-01,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Fevereiro,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-02,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Março,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-03,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Abril,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-04,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Maio,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-05,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Junho,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-06,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Julho,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-07,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Agosto,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-08,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Setembro,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-09,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Outubro,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-10,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Novembro,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",observationDate,{Year}-11,observationPeriod,P1M,value,{Month},populationType,Wildfire,measuredProperty,count,statType,measuredValue
Dezembro,#Regex,"^(?P<Month>[0-9]+\\.?[0-9]*)$",...
```

## Diff Excerpt

```diff
+ populationType: dcid:Wildfire
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  observationDate: {Year}-01
  observationPeriod: dcid:P1M
- value: {Number}
+ value: {Month}


+ populationType: dcid:Wildfire
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  observationDate: {Year}-06
  observationPeriod: dcid:P1M
- value: {Number}
+ value: {Month}


+ populationType: dcid:Wildfire
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  observationDate: {Year}-08
  observationPeriod: dcid:P1M
- value: {Number}
+ value: {Month}


- observationAbout: dcid:wikidataId/Q41587
+ 


- observationAbout: dcid:wikidataId/Q42362
+ 


- 
+ observationAbout: dcid:wikidataId/Q41587


- 
+ observationAbout: dcid:wikidataId/Q39109


+ populationType: dcid:Wildfire
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  observationDate: {Year}
  observationPeriod: dcid:P1Y
- value: {Number}
+ value: {Annual}

```

## Generation Logs

- `logs/inpe_fire/generation_20260114_001245.log`
- `logs/inpe_fire/generation_20260114_001723.log`
- `logs/inpe_fire/generation_20260114_005314.log`
