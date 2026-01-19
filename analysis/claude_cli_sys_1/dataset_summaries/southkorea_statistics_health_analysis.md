# southkorea_statistics_health - Analysis

**Generated**: 2026-01-19T13:36:09.924346

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.6% | - |
| PV Accuracy | 3.7% | 🔴 Poor |
| Precision | 0.5% | - |
| Recall | 3.7% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 233 |
| Nodes Auto-Generated | 233 |
| Nodes Matched | 0 |
| Nodes With Diff | 232 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 4 |
| PVs Modified | 0 |
| PVs Deleted | 104 |
| PVs Added | 760 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - medicalCondition: 67
  - value: 11
  - observationDate: 10
  - age: 8
  - populationType: 3
  - gender: 2
  - p1: 1
  - measuredProperty: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - populationType: 136
  - measuredProperty: 136
  - statType: 136
  - medicalCondition: 136
  - age: 120
  - gender: 90
  - property: 1
  - scalingFactor: 1
  - unit: 1
  - value: 1
  - observationAbout: 1
  - observationDate: 1

## Generation Notes

```markdown
# southkorea_statistics_health - PVMAP Generation Notes

Generated: 2026-01-16T15:01:21.047385

Total attempts: 1

---

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,#Regex,"^dcid:Count_MedicalConditionIncident_(?P<Demographics>.*)_Condition(?P<Disease>.*)$",populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,{Disease}
variableMeasured:dcid:Count_MedicalConditionIncident_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera
variableMeasured:dcid:Count_MedicalConditionIncident_Male_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,gender,Male
variableMeasured:dcid:Count_MedicalConditionIncident_Female_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,gender,Female
variableMeasured:dcid:Count_MedicalConditionIncident_0To9Years_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years0To9
variableMeasured:dcid:Count_MedicalConditionIncident_0To9Years_Male_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years0To9,gender,Male
variableMeasured:dcid:Count_MedicalConditionIncident_0To9Years_Female_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years0To9,gender,Female
variableMeasured:dcid:Count_MedicalConditionIncident_10To19Years_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years10To19
variableMeasured:dcid:Count_MedicalConditionIncident_10To19Years_Male_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years10To19,gender,Male
variableMeasured:dcid:Count_MedicalConditionIncident_10To19Years_Female_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years10To19,gender,Female
variableMeasured:dcid:Count_MedicalConditionIncident_20To29Years_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years20To29
variableMeasured:dcid:Count_MedicalConditionIncident_20To29Years_Male_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredValue,medicalCondition,Cholera,age,Years20To29,gender,Male
variableMeasured:dcid:Count_MedicalConditionIncident_20To29Years_Female_ConditionCholera,populationType,MedicalConditionIncident,measuredProperty,count,statType,measuredVal...
```

## Diff Excerpt

```diff
- medicalCondition: dcid:Tetanus
+ 


- p1: dcid:v1
  p2: dcid:v2
  p3: dcid:v3
  p4: dcid:v4
  p5: dcid:v5
+ property: dcid:value


- age: dcid:Years0To9
+ 


+ 
- observationDate: 2012
- value: {Number}


- medicalCondition: dcid:ParatyphoidFever
+ 


- 
+ populationType: dcid:MedicalConditionIncident
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ age: dcid:Years40To49
+ gender: dcid:Male
+ medicalCondition: dcid:Cholera


- 
+ populationType: dcid:MedicalConditionIncident
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ age: dcid:Years10To19
+ gender: dcid:Male
+ medicalCondition: dcid:TyphoidFever


- 
+ populationType: dcid:MedicalConditionIncident
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ gender: dcid:Male
+ medicalCondition: dcid:ParatyphoidFever


```

## Generation Logs

- `logs/southkorea_statistics_health/generation_20260116_145940.log`
