# ccd_enrollment - Analysis

**Generated**: 2026-01-14T14:56:48.859363

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

### Properties Modified (Different values)
  - prop: 1
  - race: 1

## Generation Notes

```markdown
# ccd_enrollment - PVMAP Generation Notes

Generated: 2026-01-14T00:09:48.248954

Total attempts: 2

---

Looking at the input data, I can see this has a complex carry-forward pattern that the processor **cannot handle**:

1. Year markers appear as standalone rows (`2013,,,,,`) with empty values
2. Demographic breakdowns follow without repeating the year
3. The data also contains footer notes and metadata after blank rows
4. The last section appears to be completely different data (school district data with different columns)

**CRITICAL LIMITATION**: This data pattern requires preprocessing before it can be mapped with PVMAP. The processor cannot:
- Carry forward year values from sparse marker rows to subsequent data rows
- Handle mixed datasets with different column structures in one file
- Filter out footer metadata automatically

However, I'll provide the best possible PVMAP for the **school enrollment data portion** (rows with demographic breakdowns), assuming the data has been preprocessed to:
1. Include the year value on every data row (not just marker rows)
2. Remove the school district data section (different schema)
3. Remove footer notes and blank rows

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
Year,observationDate,{Data},observationAbout,country/USA,populationType,Person,measuredProperty,count,statType,measuredValue
All grades,detailedLevelOfSchool,,value,{Number}
Total_PK_8,detailedLevelOfSchool,PreKTo8thGrade,value,{Number}
Prekindergarten,detailedLevelOfSchool,EnrolledInPreschool,value,{Number}
Kindergarten,detailedLevelOfSchool,EnrolledInKindergarten,value,{Number}
1st grade,detailedLevelOfSchool,Grade1,value,{Number}
2nd grade,detailedLevelOfSchool,Grade2,value,{Number}
3rd grade,detailedLevelOfSchool,Grade3,value,{Number}
4th grade,detailedLevelOfSchool,Grade4,value,{Number}
5th grade,detailedLevelOfSchool,Grade5,value,{Number}
6th grade,detailedLevelOfSchool,Grade6,value,{Number}
7th grade,detailedLevelOfSchool,Grade7,value,{Number}
8th grade,detailedLevelOfSchool,Grade8,value,{Number}
Total_9_12,detailedLevelOfSchool,Grade9To12,value,{Number}
9th grade,detailedLevelOfSchool,Grade9,value,{Number}
10th grade,detailedLevelOfSchool,Grade10,value,{Number}
11th grade,detailedLevelOfSchool,Grade11,value,{Number}
12th grade,detailedLevelOfSchool,Grade12,value,{Number}
  Total,race,
"American Indian/Alaska 
   Native",race,AmericanIndianOrAlaskaNativeAlone
Asian,race,AsianAlone
Black,race,BlackOrAfricanAmericanAlone
Hispanic,race,HispanicOrLatino
Pacific Islander,race,NativeHawaiianOrOtherPacificIslanderAlone
White,race,WhiteAlone
Two or more races,race,TwoOrMoreRaces
```

**PREPROCESSING REQUIRED:**
1. Filter rows to only include demographic breakdown rows (exclude year markers, school district data, footers)
2. Add year column value to each demographic row
3. Clean the data to have consistent structure

**Note**: The `#` and `-9` values in the data are non-numeric suppression markers - these cells will be automatically skip
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

```

## Generation Logs

- `logs/ccd_enrollment/generation_20260114_000911.log`
- `logs/ccd_enrollment/generation_20260114_000023.log`
