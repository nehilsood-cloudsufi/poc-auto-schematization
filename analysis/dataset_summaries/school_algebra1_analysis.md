# school_algebra1 - Analysis

**Generated**: 2026-01-14T14:56:48.869289

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 37.2% | - |
| PV Accuracy | 15.7% | 🔴 Poor |
| Precision | 29.9% | - |
| Recall | 15.7% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 309 |
| Nodes Auto-Generated | 126 |
| Nodes Matched | 0 |
| Nodes With Diff | 115 |
| Nodes Missing (LLM missed) | 194 |
| Nodes Extra (LLM added) | 11 |
| PVs Matched | 237 |
| PVs Modified | 72 |
| PVs Deleted | 1205 |
| PVs Added | 724 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - schoolGradeLevel: 307
  - assessmentLevel: 207
  - value: 194
  - gender: 192
  - race: 128
  - enrollmentStatus: 99
  - languageLearned: 40
  - disabilityStatus: 32
  - schoolSubject: 2
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - courseContent: 123
  - populationType: 123
  - measuredProperty: 123
  - statType: 123
  - gradeLevel: 121
  - courseStatus: 60
  - englishProficiency: 12
  - specialPopulation: 12
  - value: 11
  - gender: 8

### Properties Modified (Different values)
  - race: 72

## Generation Notes

```markdown
# school_algebra1 - PVMAP Generation Notes

Generated: 2026-01-14T00:52:16.715441

Total attempts: 1

---

Looking at this data, I need to understand the structure:

- **ncesid**: School identifier
- **YEAR**: Academic year (2021)
- **LEAID/LEA_NAME**: School district identifiers
- **SCHID/SCH_NAME**: School identifiers  
- **COMBOKEY**: Composite key
- **JJ**: Binary indicator (Yes/No)
- Multiple columns with patterns like:
  - `SCH_ALGENR_G08_HI_M/F`: Algebra enrollment in grade 8 by race (HI=Hispanic, AM=American Indian, AS=Asian, HP=Pacific Islander, BL=Black, WH=White, TR=Two or more races) and gender (M/F)
  - `SCH_ALGENR_GS0910_*`: Algebra enrollment in grades 9-10
  - `SCH_ALGENR_GS1112_*`: Algebra enrollment in grades 11-12
  - `SCH_ALGPASS_*`: Algebra pass rates (same demographic breakdown)
  - `TOT_ALGENR/TOT_ALGPASS`: Totals by gender
  - `_LEP_`: Limited English Proficiency students
  - `_IDEA_`: Students with disabilities (IDEA)

This is **Pattern C (Wide Data with Row/Column Combinations)** where:
- Each row is a school
- Each metric column represents enrollment/pass counts for different grade levels, races, genders, and special populations
- The `-9` values indicate missing/suppressed data

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
ncesid,#Format,"observationAbout=nces/{Data}"
YEAR,observationDate,{Data}
SCH_ALGCLASSES_GS0708,value,{Number},populationType,MathClass,measuredProperty,count,statType,measuredValue,gradeLevel,Grade7Or8,courseContent,Algebra
SCH_MATHCLASSES_ALG,value,{Number},populationType,MathClass,measuredProperty,count,statType,measuredValue,courseContent,Algebra
SCH_ALGCERT_ALG,value,{Number},populationType,Teacher,measuredProperty,count,statType,measuredValue,courseContent,Algebra,certificationStatus,Certified
SCH_ALGENR_G08_HI_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,gradeLevel,Grade8,courseContent,Algebra,race,Hispanic,gender,Male
SCH_ALGENR_G08_HI_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,gradeLevel,Grade8,courseContent,Algebra,race,Hispanic,gender,Female
SCH_ALGENR_G08_AM_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,gradeLevel,Grade8,courseContent,Algebra,race,AmericanIndianOrAlaskaNativeAlone,gender,Male
SCH_ALGENR_G08_AM_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,gradeLevel,Grade8,courseContent,Algebra,race,AmericanIndianOrAlaskaNativeAlone,gender,Female
SCH_ALGENR_G08_AS_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,gradeLevel,Grade8,courseContent,Algebra,race,AsianAlone,gender,Male
SCH_ALGENR_G08_AS_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,gradeLevel,Grade8,courseContent,Algebra,race,AsianAlone,gender,Female
SCH_ALGENR_G08_HP_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,gradeLevel,Grade8,courseCon
```

## Diff Excerpt

```diff
- assessmentLevel: dcid:Pass
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ courseContent: dcid:Algebra
+ courseStatus: dcid:Passed
  gender: dcid:Male
+ gradeLevel: dcid:Grade9Or10
- race: dcid:AmericanIndianOrAlaskaNative
+ race: dcid:AmericanIndianOrAlaskaNativeAlone
?                                        +++++

- schoolGradeLevel: dcid:SchoolGrade9To10
  value: {Number}


+ 
- enrollmentStatus: dcid:EnrolledInEducationOrTraining
- gender: dcid:Male
- race: dcid:Asian
- schoolGradeLevel: dcid:SchoolGrade7To8
- value: {Number}


- assessmentLevel: dcid:Pass
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ courseContent: dcid:Algebra
+ courseStatus: dcid:Passed

```

## Generation Logs

- `logs/school_algebra1/generation_20260114_001245.log`
- `logs/school_algebra1/generation_20260114_005049.log`
