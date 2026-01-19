# southkorea_statistics_education - Analysis

**Generated**: 2026-01-19T13:36:09.921952

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 98.9% | - |
| PV Accuracy | 4.8% | 🔴 Poor |
| Precision | 2.6% | - |
| Recall | 4.8% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 91 |
| Nodes Auto-Generated | 91 |
| Nodes Matched | 0 |
| Nodes With Diff | 90 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 4 |
| PVs Modified | 0 |
| PVs Deleted | 79 |
| PVs Added | 151 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - value: 27
  - observationDate: 18
  - populationType: 11
  - schoolGradeLevel: 11
  - typeOfSchool: 3
  - measuredProperty: 3
  - schoolEnrollment: 2
  - educationalAttainment: 1
  - occupationalCategory: 1
  - p1: 1
  - p6: 1

### Properties Added (Extra in LLM output)
  - populationType: 24
  - measuredProperty: 24
  - statType: 24
  - value: 24
  - observationAbout: 18
  - gender: 8
  - scheduleType: 4
  - enrollmentStatus: 4
  - occupation: 4
  - classroomType: 4
  - institutionCategory: 4
  - institutionType: 3
  - grade: 3
  - classType: 1
  - employment: 1
  - property: 1

## Generation Notes

```markdown
# southkorea_statistics_education - PVMAP Generation Notes

Generated: 2026-01-16T14:57:01.850634

Total attempts: 2

---

Looking at the error logs, I can see the main issue: **"No place in SVObs"** warnings appearing for every data cell. This means `observationAbout` is not being set properly.

The problem is in the multi-level header structure. Let me analyze the data:

1. **Row 1 (Header)**: `By province(1)` appears in the first two columns
2. **Row 2 (Sub-header)**: More granular classifications
3. **Row 3 & 4**: Additional classification details
4. **Row 5**: The actual column headers like `Sub Summary`, `Daytime`, `Evening`, etc.
5. **Data rows start at row 6**: `Total`, `Seoul`, etc. in the first column

The processor expects the first column (`By province(1)`) to contain place information, but the current PVMAP isn't mapping these place values to `observationAbout`.

Here's the corrected PVMAP:

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5
By province(1):Total,observationAbout,country/KOR
By province(1):Seoul,observationAbout,wikidataId/Q8684
By province(1):Busan,observationAbout,wikidataId/Q16520
By province(1):Daegu,observationAbout,wikidataId/Q20927
By province(1):Incheon,observationAbout,wikidataId/Q20927
By province(1):Gwangju,observationAbout,wikidataId/Q12585
By province(1):Daejeon,observationAbout,wikidataId/Q20921
By province(1):Ulsan,observationAbout,wikidataId/Q42077
By province(1):Sejong,observationAbout,wikidataId/Q42096
By province(1):Gyeonggi,observationAbout,wikidataId/Q20937
By province(1):Gangwon,observationAbout,wikidataId/Q20937
By province(1):North Chungcheong,observationAbout,wikidataId/Q41141
By province(1):South Chungcheong,observationAbout,wikidataId/Q20934
By province(1):North Jeolla,observationAbout,wikidataId/Q41183
By province(1):South Jeolla,observationAbout,wikidataId/Q20925
By province(1):North Gyeongsang,observationAbout,wikidataId/Q20932
By province(1):South Gyeongsang,observationAbout,wikidataId/Q20936
By province(1):Jeju,observationAbout,wikidataId/Q41071
Classification(1):Total,#ignore,skip
Classification(1):National,institutionType,National
Classification(1):Public,institutionType,Public
Classification(1):Private,institutionType,Private
2022,observationDate,2022
2023,observationDate,2023
2024,observationDate,2024
Schools_Total (EA),value,{Number},populationType,EducationalOrganization,measuredProperty,count,statType,measuredValue,institutionCategory,School
School Staffs (In Person),value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,employment,SchoolStaff
Instructors_Total,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,occupation,Instructor
Clerical Staffs_Total,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,occupation,ClericalStaff
Entrants_Total (In Person),value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,enrollmentStatus,Entrant
Graduates_Total (In Person),v...
```

## Diff Excerpt

```diff
- 
+ institutionType: dcid:National


- 
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ grade: dcid:Grade11
+ value: {Number}


  


- 
+ scheduleType: dcid:Daytime


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ enrollmentStatus: dcid:Graduate
+ value: {Number}


- 
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ value: {Number}


- value: 1
+ 


  observationDate: 2023
- value: {Number}


+ 
- observationDate: 2018
- value: {Number}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count

```

## Generation Logs

- `logs/southkorea_statistics_education/generation_20260116_145446.log`
