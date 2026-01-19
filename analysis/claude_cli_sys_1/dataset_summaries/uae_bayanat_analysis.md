# uae_bayanat - Analysis

**Generated**: 2026-01-19T13:36:09.926512

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 94.7% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 19 |
| Nodes Auto-Generated | 19 |
| Nodes Matched | 0 |
| Nodes With Diff | 18 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 8 |
| PVs Added | 50 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - populationType: 1
  - observationAbout: 1
  - p1: 1
  - p2: 1
  - p3: 1
  - prop: 1
  - value: 1
  - observationDate: 1

### Properties Added (Extra in LLM output)
  - populationType: 9
  - measuredProperty: 9
  - statType: 9
  - citizenship: 6
  - gender: 6
  - observationPeriod: 1
  - observationDate: 1
  - measurementMethod: 1
  - property: 1
  - property2: 1
  - property3: 1
  - property4: 1
  - property5: 1
  - property6: 1
  - property7: 1
  - observationAbout: 1

## Generation Notes

```markdown
# uae_bayanat - PVMAP Generation Notes

Generated: 2026-01-16T15:04:14.127951

Total attempts: 1

---

```csv
key,property,value,property2,value2,property3,value3,property4,value4,property5,value5,property6,value6,property7,value7
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
observationPeriod,observationPeriod,{Data}
measurementMethod,measurementMethod,{Data}
variableMeasured:dcid:Count_Person,populationType,Person,measuredProperty,count,statType,measuredValue
variableMeasured:dcid:Count_Person_Male,populationType,Person,measuredProperty,count,statType,measuredValue,gender,Male
variableMeasured:dcid:Count_Person_Female,populationType,Person,measuredProperty,count,statType,measuredValue,gender,Female
variableMeasured:dcid:Count_Person_Citizen,populationType,Person,measuredProperty,count,statType,measuredValue,citizenship,Citizen
variableMeasured:dcid:Count_Person_Citizen_Male,populationType,Person,measuredProperty,count,statType,measuredValue,citizenship,Citizen,gender,Male
variableMeasured:dcid:Count_Person_Citizen_Female,populationType,Person,measuredProperty,count,statType,measuredValue,citizenship,Citizen,gender,Female
variableMeasured:dcid:Count_Person_NotACitizen,populationType,Person,measuredProperty,count,statType,measuredValue,citizenship,NotACitizen
variableMeasured:dcid:Count_Person_NotACitizen_Male,populationType,Person,measuredProperty,count,statType,measuredValue,citizenship,NotACitizen,gender,Male
variableMeasured:dcid:Count_Person_NotACitizen_Female,populationType,Person,measuredProperty,count,statType,measuredValue,citizenship,NotACitizen,gender,Female
```

**NOTES:**

1. **Data Structure**: This is Pattern A (flat data) where each row represents one complete observation with all properties already specified in columns.

2. **observationAbout**: The data already contains proper DCIDs in the format `dcid:wikidataId/QXXXXX`. Using `{Data}` preserves these values directly.

3. **variableMeasured Mappings**: The `variableMeasured` column contains pre-constructed StatVar DCIDs. Each unique StatVar is mapped to its constituent properties:
   - Base: `Count_Person` → Person count
   - Gender constraints: `_Male`, `_Female`
   - Citizenship constraints: `_Citizen`, `_NotACitizen`
   - Combined: `_Citizen_Male`, `_Citizen_Female`, `_NotACitizen_Male`, `_NotACitizen_Female`

4. **Multi-value Properties**: The config indicates `gender` and `citizenship` as multi-value properties, which are encoded in the variableMeasured names and extracted via the mappings above.

5. **Empty Values**: Some `observationPeriod` and `measurementMethod` cells are empty in the input - these will be preserved as-is using `{Data}`.

```

## Diff Excerpt

```diff
- 
+ observationPeriod: {Data}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ citizenship: dcid:NotACitizen
+ gender: dcid:Male


  


- 
+ observationDate: {Data}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ citizenship: dcid:NotACitizen


  


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ citizenship: dcid:Citizen


+ 
- populationType: dcid:Person
- observationAbout: {Data}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ gender: dcid:Male


- 
+ measurementMethod: {Data}

```

## Generation Logs

- `logs/uae_bayanat/generation_20260116_150358.log`
