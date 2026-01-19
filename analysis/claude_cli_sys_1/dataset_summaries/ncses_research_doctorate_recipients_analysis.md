# ncses_research_doctorate_recipients - Analysis

**Generated**: 2026-01-19T13:36:09.903729

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 97.6% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 41 |
| Nodes Auto-Generated | 41 |
| Nodes Matched | 0 |
| Nodes With Diff | 40 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 47 |
| PVs Added | 73 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationDate: 11
  - value: 11
  - race: 6
  - citizenship: 4
  - ethnicity: 3
  - educationalAttainment: 2
  - gender: 2
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - observationAbout: 1
  - p1: 1
  - p2: 1
  - p3: 1
  - p4: 1

### Properties Added (Extra in LLM output)
  - populationType: 10
  - measuredProperty: 10
  - statType: 10
  - educationalAttainment: 10
  - gender: 10
  - citizenship: 7
  - ethnicity: 6
  - race: 2
  - observationDate: 1
  - value: 1
  - property: 1
  - property2: 1
  - property3: 1
  - property4: 1
  - property5: 1
  - observationAbout: 1

## Generation Notes

```markdown
# ncses_research_doctorate_recipients - PVMAP Generation Notes

Generated: 2026-01-16T14:36:34.060186

Total attempts: 1

---

```csv
key,property,value,property2,value2,property3,value3,property4,value4,property5,value5
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured:dcid:Count_Person_EducationalAttainmentDoctorateDegree_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female
variableMeasured:dcid:Count_Person_Citizen_EducationalAttainmentDoctorateDegree_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,citizenship,Citizen
variableMeasured:dcid:Count_Person_VisaHolder_EducationalAttainmentDoctorateDegree_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,citizenship,VisaHolder
variableMeasured:dcid:Count_Person_CitizenshipUnknown_EducationalAttainmentDoctorateDegree_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,citizenship,CitizenshipUnknown
variableMeasured:dcid:Count_Person_EducationalAttainmentDoctorateDegree_HispanicOrLatino_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,ethnicity,HispanicOrLatino
variableMeasured:dcid:Count_Person_Citizen_EducationalAttainmentDoctorateDegree_HispanicOrLatino_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,ethnicity,HispanicOrLatino,citizenship,Citizen
variableMeasured:dcid:Count_Person_VisaHolder_EducationalAttainmentDoctorateDegree_HispanicOrLatino_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,ethnicity,HispanicOrLatino,citizenship,VisaHolder
variableMeasured:dcid:Count_Person_CitizenshipUnknown_EducationalAttainmentDoctorateDegree_HispanicOrLatino_Female,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,ethnicity,HispanicOrLatino,citizenship,CitizenshipUnknown
variableMeasured:dcid:Count_Person_EducationalAttainmentDoctorateDegree_NotHispanicOrLatino_Female_AmericanIndianOrAlaskaNativeAlone,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,ethnicity,NotHispanicOrLatino,race,AmericanIndianOrAlaskaNativeAlone
variableMeasured:dcid:Count_Person_Citizen_EducationalAttainmentDoctorateDegree_NotHispanicOrLatino_Female_AmericanIndianOrAlaskaNativeAlone,populationType,Person,measuredProperty,count,statType,measuredValue,educationalAttainment,DoctorateDegree,gender,Female,ethnicity,NotHispanicOrLatino,race,AmericanIndianOrAlaskaNativeAlone,citizenship,Citizen
```

**CHECKLI...
```

## Diff Excerpt

```diff
+ 
- educationalAttainment: dcid:DoctorateDegree
- gender: dcid:Female


- 
+ observationDate: {Data}


- ethnicity: dcid:NotHispanicOrLatino
+ 


+ 
- observationDate: 2011
- value: {Number}


+ 
- observationDate: 2015
- value: {Number}


- race: dcid:AmericanIndianOrAlaskaNativeAlone
+ 


- citizenship: dcid:CitizenshipUnknown
+ 


+ 
- observationDate: 2021
- value: {Number}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ educationalAttainment: dcid:DoctorateDegree
+ ethnicity: dcid:HispanicOrLatino
+ gender: dcid:Female


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ educationalAttainment: dcid:DoctorateDegree

```

## Generation Logs

- `logs/ncses_research_doctorate_recipients/generation_20260116_143613.log`
