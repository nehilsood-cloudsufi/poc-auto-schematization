# us_urban_school_maths_and_science_enrollment - Analysis

**Generated**: 2026-01-14T14:56:48.876226

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 7.0% | - |
| PV Accuracy | 4.2% | 🔴 Poor |
| Precision | 36.3% | - |
| Recall | 4.2% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 284 |
| Nodes Auto-Generated | 23 |
| Nodes Matched | 0 |
| Nodes With Diff | 20 |
| Nodes Missing (LLM missed) | 264 |
| Nodes Extra (LLM added) | 3 |
| PVs Matched | 47 |
| PVs Modified | 6 |
| PVs Deleted | 1075 |
| PVs Added | 93 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - schoolSubject: 280
  - value: 262
  - gender: 262
  - race: 182
  - englishProficiency: 28
  - educationProgram: 28
  - disabilityStatus: 26
  - educationalInstitutionType: 2
  - observationAbout: 1
  - measuredProperty: 1

### Properties Added (Extra in LLM output)
  - statType: 20
  - measuredProperty: 20
  - populationType: 20
  - courseLevel: 20
  - value: 2
  - gender: 2
  - englishLearnerStatus: 2
  - prop: 1
  - p5: 1
  - p7: 1

### Properties Modified (Different values)
  - race: 6

## Generation Notes

```markdown
# us_urban_school_maths_and_science_enrollment - PVMAP Generation Notes

Generated: 2026-01-14T00:50:01.879049

Total attempts: 1

---

Looking at this education data with chemistry enrollment broken down by race, gender, and disability status, I need to create a PV map that transforms these columns into proper StatVarObservation format.

Let me analyze the structure:
- Each row represents a school (identified by `ncesid`)
- `YEAR` provides the observation date
- Multiple enrollment columns with pattern `SCH_SCIENR_CHEM_{RACE}_{GENDER}` plus totals and disability columns
- The data contains `-9` values (likely suppression/missing data markers)

Here's the PV map:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
ncesid,#Format,"observationAbout=nces/{Data}"
YEAR,observationDate,{Data}
SCH_SCIENR_CHEM_HI_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,HispanicOrLatino,gender,Male,courseLevel,Chemistry
SCH_SCIENR_CHEM_HI_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,HispanicOrLatino,gender,Female,courseLevel,Chemistry
SCH_SCIENR_CHEM_AM_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,AmericanIndianOrAlaskaNative,gender,Male,courseLevel,Chemistry
SCH_SCIENR_CHEM_AM_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,AmericanIndianOrAlaskaNative,gender,Female,courseLevel,Chemistry
SCH_SCIENR_CHEM_AS_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,AsianAlone,gender,Male,courseLevel,Chemistry
SCH_SCIENR_CHEM_AS_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,AsianAlone,gender,Female,courseLevel,Chemistry
SCH_SCIENR_CHEM_HP_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,NativeHawaiianOrPacificIslander,gender,Male,courseLevel,Chemistry
SCH_SCIENR_CHEM_HP_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,NativeHawaiianOrPacificIslander,gender,Female,courseLevel,Chemistry
SCH_SCIENR_CHEM_BL_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,BlackOrAfricanAmericanAlone,gender,Male,courseLevel,Chemistry
SCH_SCIENR_CHEM_BL_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,BlackOrAfricanAmericanAlone,gender,Female,courseLevel,Chemistry
SCH_SCIENR_CHEM_WH_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,WhiteAlone,gender,Male,courseLevel,Chemistry
SCH_SCIENR_CHEM_WH_F,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,WhiteAlone,gender,Female,courseLevel,Chemistry
SCH_SCIENR_CHEM_TR_M,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,race,TwoOrMoreRaces,gender,Male,courseLevel,Chemistry
SCH_SCIENR_CHEM_TR_F,value,{Number},popu
```

## Diff Excerpt

```diff
+ 
- gender: dcid:Female
- race: dcid:TwoOrMoreRaces
- schoolSubject: dcid:Physics
- value: {Number}


+ 
- gender: dcid:Male
- schoolSubject: dcid:Calculus
- value: {Number}


+ 
- gender: dcid:Male
- race: dcid:TwoOrMoreRaces
- schoolSubject: dcid:Calculus
- value: {Number}


+ 
- gender: dcid:Male
- race: dcid:WhiteAlone
- schoolSubject: dcid:AdvancedMathematics
- value: {Number}


+ 
- gender: dcid:Male
- schoolSubject: dcid:Calculus

```

## Generation Logs

- `logs/us_urban_school_maths_and_science_enrollment/generation_20260114_004940.log`
- `logs/us_urban_school_maths_and_science_enrollment/generation_20260114_004006.log`
