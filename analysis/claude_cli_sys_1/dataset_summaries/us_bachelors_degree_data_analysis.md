# us_bachelors_degree_data - Analysis

**Generated**: 2026-01-19T13:36:09.929142

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.2% | - |
| PV Accuracy | 2.7% | 🔴 Poor |
| Precision | 2.7% | - |
| Recall | 2.7% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 122 |
| Nodes Auto-Generated | 122 |
| Nodes Matched | 0 |
| Nodes With Diff | 121 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 6 |
| PVs Modified | 0 |
| PVs Deleted | 213 |
| PVs Added | 216 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - bachelorsDegreeMajor: 46
  - observationAbout: 38
  - observationDate: 25
  - observationPeriod: 24
  - populationType: 13
  - measuredProperty: 13
  - educationalAttainment: 13
  - gender: 13
  - value: 13
  - race: 10
  - residentStatus: 2
  - p1: 1
  - p8: 1
  - p9: 1

### Properties Added (Extra in LLM output)
  - populationType: 20
  - measuredProperty: 20
  - statType: 20
  - educationalAttainment: 20
  - gender: 20
  - observationAbout: 20
  - observationDate: 20
  - observationPeriod: 20
  - race: 20
  - value: 20
  - Race: 8
  - immigrationStatus: 3
  - Year: 2
  - prop: 1
  - GLOBAL: 1
  - ImmigrationStatus: 1

## Generation Notes

```markdown
# us_bachelors_degree_data - PVMAP Generation Notes

Generated: 2026-01-16T15:06:30.579520

Total attempts: 3

---

Looking at the errors, I can see the main issues:

1. **Duplicate observations**: The processor is treating multiple cells as the same observation because the multi-level headers aren't being properly mapped
2. **Missing place**: Some rows have no `observationAbout` 
3. **Unresolved value references**: The structure has nested headers (row 2 has year labels "2010-11" and "2011-12", row 3 has column categories)

The data has a complex header structure:
- Row 1: Title
- Row 2: "Field of study" and year labels (2010-11, 2011-12)  
- Row 3: Blank, then "Total", "White", "Black", "Hispanic", "Asian/Pacific Islander" (with sub-columns), etc.
- Row 4: Sub-categories for Asian/Pacific Islander ("Total", "Asian", "Pacific Islander")
- Row 5: Column numbers

The key issue is that each value column needs to be uniquely identified by BOTH the year AND the race/ethnicity category.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
2010-11,Year,2010-11
2011-12,Year,2011-12
Total,Race,
White,Race,White
Black,Race,Black
His- panic,Race,Hispanic
Asian/Pacific Islander,Race,AsianOrPacificIslander
Asian,Race,Asian
Pacific Islander,Race,PacificIslander
American Indian/ Alaska Native,Race,AmericanIndianOrAlaskaNative
Two or more races,Race,TwoOrMoreRaces
Non- resi- dent alien,ImmigrationStatus,NonResident
2,observationDate,{Year},value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,observationAbout,country/USA,observationPeriod,P1Y,gender,Female,educationalAttainment,BachelorsDegree,race,{Race}
3,observationDate,{Year},value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,observationAbout,country/USA,observationPeriod,P1Y,gender,Female,educationalAttainment,BachelorsDegree,race,{Race}
4,observationDate,{Year},value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,observationAbout,country/USA,observationPeriod,P1Y,gender,Female,educationalAttainment,BachelorsDegree,race,{Race}
5,observationDate,{Year},value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,observationAbout,country/USA,observationPeriod,P1Y,gender,Female,educationalAttainment,BachelorsDegree,race,{Race}
6,observationDate,{Year},value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,observationAbout,country/USA,observationPeriod,P1Y,gender,Female,educationalAttainment,BachelorsDegree,race,{Race}
7,observationDate,{Year},value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,observationAbout,country/USA,observationPeriod,P1Y,gender,Female,educationalAttainment,BachelorsDegree,race,{Race}
8,observationDate,{Year},value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,observationAbout,country/USA,observationPeriod,P1Y,gender,Female,educationalAttainment,BachelorsDegree,race,{Race}
9,observa...
```

## Diff Excerpt

```diff
- bachelorsDegreeMajor: dcid:ArchitectureAndRelatedServicesMajor
+ 


+ 
- observationAbout: dcid:country/USA
- observationDate: 2013
- observationPeriod: dcid:P1Y


+ 
- observationAbout: dcid:country/USA
- observationDate: 2033
- observationPeriod: dcid:P1Y


+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- educationalAttainment: dcid:BachelorsDegree
- gender: dcid:Male
- observationAbout: dcid:country/USA
- race: dcid:HispanicOrLatino
- value: @Number


- bachelorsDegreeMajor: dcid:TheologyAndReligionMajor
+ 


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ educationalAttainment: dcid:BachelorsDegree
+ gender: dcid:Female
+ observationAbout: dcid:country/USA
+ observationDate: {Year}
+ observationPeriod: dcid:P1Y
+ race: {Race}
+ value: {Number}


- bachelorsDegreeMajor: dcid:BusinessMajor
+ 


- bachelorsDegreeMajor: dcid:EngineeringTechnologiesMajor
+ 


```

## Generation Logs

- `logs/us_bachelors_degree_data/generation_20260116_150516.log`
