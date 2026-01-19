# india_ndap_india_nss_health_ailments - Analysis

**Generated**: 2026-01-19T13:36:09.893293

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 5.4% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 3.1% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 37 |
| Nodes Auto-Generated | 22 |
| Nodes Matched | 0 |
| Nodes With Diff | 2 |
| Nodes Missing (LLM missed) | 35 |
| Nodes Extra (LLM added) | 20 |
| PVs Matched | 0 |
| PVs Modified | 1 |
| PVs Deleted | 39 |
| PVs Added | 31 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - medicalCondition: 16
  - age: 7
  - value: 6
  - placeOfResidenceClassification: 2
  - gender: 2
  - observationDate: 1
  - GLOBAL: 1
  - statType: 1
  - populationType: 1
  - measurementDenominator: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - age: 8
  - medicalCondition: 4
  - placeOfResidenceClassification: 2
  - observationAbout: 2
  - gender: 2
  - GLOBAL: 1
  - scalingFactor: 1
  - unit: 1
  - statType: 1
  - populationType: 1
  - value: 1
  - measuredProperty: 1
  - observationDate: 1
  - p4: 1
  - p6: 1
  - p3: 1
  - p5: 1
  - p2: 1

### Properties Modified (Different values)
  - prop: 1

## Generation Notes

```markdown
# india_ndap_india_nss_health_ailments - PVMAP Generation Notes

Generated: 2026-01-14T17:29:20.072474

Total attempts: 1

---

Looking at this Indian health survey data, I need to map ailment categories, demographics, and geographic identifiers to Data Commons format.

**Data Structure Analysis:**
- **Place**: `srcStateName` contains full state names (Punjab, Jammu And Kashmir) - needs explicit DCID mappings
- **Demographics**: `GENDER` (Female), `Age group` (0-4, 5-14, 15-29, etc.), `TRU` (Rural/Urban)
- **Date**: `srcYear` column contains year (2017)
- **Ailment**: `Broad ailment category` contains disease categories
- **Value**: `Ailments reported for each Broad ailment category per 100000 persons during last 15 days by different age groups` (rate per 100k)

**Key Challenges:**
1. State names need explicit mapping to Indian state DCIDs (wikidataId format)
2. Age groups use varied formats (0-4, 5-14, 60+, 70+)
3. Long column header for the value needs exact quoting
4. Ailment categories need mapping to appropriate medical condition properties
5. This is a **rate per 100,000 persons**, not a count

**Data Limitations:**
- Footer rows may exist after the data (not visible in sample but common in NSS datasets)
- Some cells contain text values like "0.976689818" in the sample columns which appear to be weights/estimates

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
srcStateName:Jammu And Kashmir,observationAbout,wikidataId/Q1180
srcStateName:Punjab,observationAbout,wikidataId/Q22424
srcStateName:Haryana,observationAbout,wikidataId/Q1174
srcStateName:Himachal Pradesh,observationAbout,wikidataId/Q1177
srcStateName:Chandigarh,observationAbout,wikidataId/Q43433
srcStateName:Uttarakhand,observationAbout,wikidataId/Q1499
srcStateName:Delhi,observationAbout,wikidataId/Q1353
srcStateName:Rajasthan,observationAbout,wikidataId/Q1437
srcStateName:Uttar Pradesh,observationAbout,wikidataId/Q1498
srcStateName:Bihar,observationAbout,wikidataId/Q1165
srcStateName:Sikkim,observationAbout,wikidataId/Q1505
srcStateName:Arunachal Pradesh,observationAbout,wikidataId/Q1162
srcStateName:Nagaland,observationAbout,wikidataId/Q1599
srcStateName:Manipur,observationAbout,wikidataId/Q1193
srcStateName:Mizoram,observationAbout,wikidataId/Q1264
srcStateName:Tripura,observationAbout,wikidataId/Q1363
srcStateName:Meghalaya,observationAbout,wikidataId/Q1195
srcStateName:Assam,observationAbout,wikidataId/Q1164
srcStateName:West Bengal,observationAbout,wikidataId/Q1356
srcStateName:Jharkhand,observationAbout,wikidataId/Q1184
srcStateName:Odisha,observationAbout,wikidataId/Q22048
srcStateName:Chhattisgarh,observationAbout,wikidataId/Q1184624
srcStateName:Madhya Pradesh,observationAbout,wikidataId/Q1188
srcStateName:Gujarat,observationAbout,wikidataId/Q1061
srcStateName:Daman And Diu,observationAbout,wikidataId/Q66710
srcStateName:Dadra And Nagar Haveli,observationAbout,wikidataId/Q66710
srcStateName:Maharashtra,observationAbout,wikidataId/Q1191
srcStateName:Andhra Pradesh,obse...
```

## Diff Excerpt

```diff
- age: dcid:Years60To69
+ 


- placeOfResidenceClassification: dcid:Urban
+ 


- medicalCondition: dcid:ObstetricCondition
+ 


- medicalCondition: dcid:GastroIntestinalCondition
+ 


- placeOfResidenceClassification: dcid:Rural
+ 


- age: dcid:Years70Onwards
+ 


- 
+ medicalCondition: dcid:CardiovascularDisease


- medicalCondition: dcid:EndocrineMetabolicCondition
+ 


- medicalCondition: dcid:PsychiatricNeurologicalCondition
+ 


- 
+ GLOBAL: dcid:gender


- 
+ placeOfResidenceClassification: dcid:Rural


- 
+ age: dcid:Years30To44


- 
+ age: dcid:Years60Onwards

```

## Generation Logs

- `logs/india_ndap_india_nss_health_ailments/generation_20260113_234758.log`
- `logs/india_ndap_india_nss_health_ailments/generation_20260114_001245.log`
- `logs/india_ndap_india_nss_health_ailments/generation_20260114_172844.log`
