# oecd_wastewater_treatment - Analysis

**Generated**: 2026-01-14T14:56:48.868103

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 7.7% | 🔴 Poor |
| Node Coverage | 38.5% | - |
| PV Accuracy | 12.5% | 🔴 Poor |
| Precision | 39.1% | - |
| Recall | 12.5% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 13 |
| Nodes Auto-Generated | 14 |
| Nodes Matched | 1 |
| Nodes With Diff | 4 |
| Nodes Missing (LLM missed) | 8 |
| Nodes Extra (LLM added) | 10 |
| PVs Matched | 7 |
| PVs Modified | 2 |
| PVs Deleted | 47 |
| PVs Added | 14 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - name: 8
  - waterTreatmentSystem: 8
  - measurementDenominator: 8
  - waterTreatmentStatus: 7
  - waterTreatmentType: 6
  - waterTreatmentLevel: 4
  - populationType: 1
  - measuredProperty: 1
  - wasteTreatmentType: 1
  - scalingFactor: 1

### Properties Added (Extra in LLM output)
  - wastewaterTreatmentType: 8
  - observationPeriod: 1
  - prop: 1
  - unit: 1
  - populationType: 1
  - statType: 1
  - measuredProperty: 1

### Properties Modified (Different values)
  - observationAbout: 1
  - observationDate: 1

## Generation Notes

```markdown
# oecd_wastewater_treatment - PVMAP Generation Notes

Generated: 2026-01-13T23:47:42.248547

Total attempts: 3

---

Looking at the error logs, I can see several issues:

1. **No place resolution**: The main error is `"No place in SVObs"` for all observations. The `REF_AREA` column contains values like "AUT" (Austria), but the PVMAP needs to map these to country DCIDs.

2. **Incorrect #Regex usage**: The current PVMAP likely has `#Regex` on the wrong rows or isn't properly extracting the country code.

3. **Schema validation**: There are spell-check errors for "wastewater" which should be capitalized as "Wastewater" in schema properties.

Here's the corrected PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
REF_AREA,observationAbout,country/{Data}
TIME_PERIOD,observationDate,{Data}
FREQ,observationPeriod,P1Y
UNIT_MEASURE,unit,Percent
OBS_VALUE,value,{Number},populationType,Wastewater,measuredProperty,count,statType,measuredValue
MEASURE:OTHERTR,wastewaterTreatmentType,UnspecifiedTreatment
MEASURE:PUBNOTR,wastewaterTreatmentType,PublicSewerageWithoutTreatment
MEASURE:INDEPDTR,wastewaterTreatmentType,IndependentTreatment
MEASURE:TOTTR,wastewaterTreatmentType,TotalWastewaterTreatment
MEASURE:PUBADVTR,wastewaterTreatmentType,TertiaryTreatment
MEASURE:PUBBIOTR,wastewaterTreatmentType,SecondaryTreatment
MEASURE:TOTPUBSEW,wastewaterTreatmentType,TotalPublicSewerage
MEASURE:PUBTOTTR,wastewaterTreatmentType,PublicTotalTreatment
```

**Key fixes:**
1. `REF_AREA` maps to `country/{Data}` - the values are already ISO 3-letter codes (AUT, etc.)
2. Removed incorrect `#Regex` usage
3. `MEASURE` values are prefixed with column name (`MEASURE:OTHERTR`) to create unique keys
4. Capitalized "Wastewater" in `populationType`
5. All StatVar properties on the `OBS_VALUE` row apply to entire column
6. Each measurement type gets its own `wastewaterTreatmentType` constraint

```

## Diff Excerpt

```diff
- 
+ wastewaterTreatmentType: dcid:UnspecifiedTreatment


- populationType: dcid:Person
- measuredProperty: dcid:count
- observationAbout: {Data}
+ observationAbout: dcid:country/{Data}
?                   +++++++++++++

- scalingFactor: 100
- unit: dcid:Percent
- wasteTreatmentType: dcid:WasteWaterTreatment


+ 
- name: "Percentage of population connected to the primary treatment"
- measurementDenominator: -waterTreatmentLevel,-waterTreatmentStatus,-waterTreatmentType
- waterTreatmentLevel: dcid:PrimaryTreatment
- waterTreatmentStatus: dcid:WasteWaterTreated
- waterTreatmentSystem: dcid:PublicSewerage
- waterTreatmentType: dcid:WasteWaterTreatmentPlant


  


+ 
- name: "Percentage of population connected to the total public sewerage"
- measurementDenominator: -wasteTreatmentType,-waterTreatmentSystem

```

## Generation Logs

- `logs/oecd_wastewater_treatment/generation_20260113_234341.log`
- `logs/oecd_wastewater_treatment/generation_20260113_234650.log`
- `logs/oecd_wastewater_treatment/generation_20260113_233032.log`
