# ccd_enrollment - Analysis

**Generated**: 2026-01-19T13:36:09.871549

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 15.8% | 🔴 Poor |
| Node Coverage | 65.8% | - |
| PV Accuracy | 20.4% | 🟠 Needs Work |
| Precision | 47.2% | - |
| Recall | 20.4% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 38 |
| Nodes Auto-Generated | 27 |
| Nodes Matched | 6 |
| Nodes With Diff | 19 |
| Nodes Missing (LLM missed) | 13 |
| Nodes Extra (LLM added) | 3 |
| PVs Matched | 23 |
| PVs Modified | 2 |
| PVs Deleted | 88 |
| PVs Added | 28 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - populationType: 19
  - observationAbout: 19
  - schoolGradeLevel: 17
  - schoolType: 16
  - observationDate: 9
  - typeOfSchool: 3
  - race: 2
  - value: 2
  - enrollmentLevel: 1

### Properties Added (Extra in LLM output)
  - detailedLevelOfSchool: 16
  - race: 1
  - observationDate: 1
  - statType: 1
  - measuredProperty: 1
  - populationType: 1
  - observationAbout: 1
  - p3: 1
  - p6: 1
  - p4: 1
  - p2: 1
  - p5: 1
  - GLOBAL: 1

### Properties Modified (Different values)
  - prop: 1
  - race: 1

## Generation Notes

```markdown
# ccd_enrollment - PVMAP Generation Notes

Generated: 2026-01-14T17:31:01.624713

Total attempts: 3

---

Looking at the errors, I can see the main issues:

1. **No place resolution**: The processor can't find `observationAbout` for any rows
2. **Date resolution failures**: `observationDate` is being set to race names like "Total", "Asian", "White" instead of the year
3. **Multiple data formats mixed**: The file contains two completely different datasets (enrollment by race/grade for 2013-2017, and detailed 2022 school-level data with 200+ columns)

The fundamental problem is **Pattern 1 (carry-forward data)** - a known limitation:
- Row 3 has just the year "2013" with empty values
- Rows 4-11 have the demographic breakdowns but DON'T repeat the year
- The processor cannot handle this "year marker row followed by data rows" pattern

However, I can provide a PVMAP that will work for the **2022 dataset portion** (rows 26-27), which has proper flat structure with Year column.

For the 2013-2017 data, you would need to **preprocess** to repeat the year on each data row.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
Year,observationDate,{Data}
All grades,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,AllGrades,schoolEnrollment,EnrolledInSchool
Total_PK_8,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,PreKTo8,schoolEnrollment,EnrolledInSchool
Prekindergarten,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,PreKindergarten,schoolEnrollment,EnrolledInSchool
Kindergarten,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Kindergarten,schoolEnrollment,EnrolledInSchool
1st grade,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Grade1,schoolEnrollment,EnrolledInSchool
2nd grade,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Grade2,schoolEnrollment,EnrolledInSchool
3rd grade,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Grade3,schoolEnrollment,EnrolledInSchool
4th grade,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Grade4,schoolEnrollment,EnrolledInSchool
5th grade,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Grade5,schoolEnrollment,EnrolledInSchool
6th grade,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Grade6,schoolEnrollment,EnrolledInSchool
7th grade,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,detailedLevelOfSchool,Grade7,schoolEnrollment,EnrolledInSchool
8th grade,value,{Number},populationType,Student,measuredProperty,count,statType...
```

## Diff Excerpt

```diff
- observationDate: 2013
+ 


+ detailedLevelOfSchool: dcid:EnrolledInKindergarten
- populationType: dcid:Student
- observationAbout: dcid:country/USA
- schoolGradeLevel: dcid:Kindergarten
- typeOfSchool: dcid:PublicSchool
  value: {Number}


- populationType: dcid:Student
- observationAbout: dcid:country/USA
- typeOfSchool: dcid:PublicSchool
  value: {Number}


+ detailedLevelOfSchool: dcid:Grade9
- populationType: dcid:Student
- observationAbout: dcid:country/USA
- schoolGradeLevel: dcid:SchoolGrade9
- schoolType: dcid:PublicSchool
  value: {Number}


  race: dcid:TwoOrMoreRaces


- observationDate: 2025
+ 


+ detailedLevelOfSchool: dcid:Grade12
- populationType: dcid:Student
- observationAbout: dcid:country/USA
- schoolGradeLevel: dcid:SchoolGrade12
- schoolType: dcid:PublicSchool
  value: {Number}


- observationDate: 2017
+ 


  race: dcid:NativeHawaiianOrOtherPacificIslanderAlone


+ detailedLevelOfSchool: dcid:Grade8
- populationType: dcid:Student

```

## Generation Logs

- `logs/ccd_enrollment/generation_20260114_000023.log`
- `logs/ccd_enrollment/generation_20260114_000911.log`
- `logs/ccd_enrollment/generation_20260114_172926.log`
