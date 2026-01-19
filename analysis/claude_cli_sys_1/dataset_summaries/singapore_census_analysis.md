# singapore_census - Analysis

**Generated**: 2026-01-19T13:36:09.919926

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.0% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 104 |
| Nodes Auto-Generated | 104 |
| Nodes Matched | 0 |
| Nodes With Diff | 103 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 206 |
| PVs Added | 118 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationDate: 69
  - value: 69
  - populationType: 15
  - measurementDenominator: 10
  - residentStatus: 10
  - scalingFactor: 10
  - statType: 6
  - ageGroupClassification: 5
  - age: 4
  - gender: 4
  - measuredProperty: 3
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - populationType: 18
  - measuredProperty: 18
  - statType: 18
  - measurementDenominator: 18
  - observationAbout: 12
  - observationDate: 12
  - value: 12
  - ethnicity: 4
  - gender: 1
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1
  - property: 1

## Generation Notes

```markdown
# singapore_census - PVMAP Generation Notes

Generated: 2026-01-16T17:23:56.989602

Total attempts: 2

---

I need to provide a more concise solution. The issue is that I'm listing 780+ date columns individually. Let me provide a smarter, complete PVMAP:

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5
Data Series:Total Deaths By Ethnic Group (Number),populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
Data Series:Malays (Number),populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths,ethnicity,Malay
Data Series:Chinese (Number),populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths,ethnicity,Chinese
Data Series:Indians (Number),populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths,ethnicity,Indian
Data Series:Other Ethnic Groups (Number),populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths,ethnicity,OtherEthnicGroup
Data Series:Total Male Deaths By Ethnic Group (Number),populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths,gender,Male
1960 Jan,#Regex,"^(?P<Year>\d{4}) (?P<Month>\w{3})$",observationDate,{Year}-01,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Feb,observationDate,1960-02,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Mar,observationDate,1960-03,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Apr,observationDate,1960-04,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 May,observationDate,1960-05,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Jun,observationDate,1960-06,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Jul,observationDate,1960-07,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Aug,observationDate,1960-08,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Sep,observationDate,1960-09,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenominator,Deaths
1960 Oct,observationDate,1960-10,value,{Number},observationAbout,country/SGP,populationType,Person,measuredProperty,count,statType,measuredValue,measurementDenomin...
```

## Diff Excerpt

```diff
+ 
- observationDate: 2008
- value: {Number}


+ 
- populationType: dcid:MortalityEvent
- measurementDenominator: ,+medicalStatus=LiveBirth,+populationType=BirthEvent
- age: dcid:YearsUpto5
- residentStatus: dcid:Resident
- scalingFactor: 1000


+ 
- observationDate: 2011
- value: {Number}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ measurementDenominator: dcid:Deaths
+ observationAbout: dcid:country/SGP
+ observationDate: 1960-12
+ value: {Number}


+ 
- observationDate: 1983
- value: {Number}


+ 
- populationType: dcid:MortalityEvent
- measurementDenominator: ,+medicalStatus=LiveBirth,+populationType=BirthEvent,-ageGroupClassification
- ageGroupClassification: dcid:Infant
- gender: dcid:Female
- residentStatus: dcid:Resident
- scalingFactor: 1000


+ 
- observationDate: 1996
- value: {Number}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count

```

## Generation Logs

- `logs/singapore_census/generation_20260116_145127.log`
- `logs/singapore_census/generation_20260116_165001.log`
- `logs/singapore_census/generation_20260116_171023.log`
