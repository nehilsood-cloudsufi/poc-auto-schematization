# us_urban_school_teachers - Analysis

**Generated**: 2026-01-14T14:56:48.877027

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 2.9% | 🔴 Poor |
| Node Coverage | 31.4% | - |
| PV Accuracy | 8.9% | 🔴 Poor |
| Precision | 32.8% | - |
| Recall | 8.9% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 35 |
| Nodes Auto-Generated | 14 |
| Nodes Matched | 1 |
| Nodes With Diff | 10 |
| Nodes Missing (LLM missed) | 24 |
| Nodes Extra (LLM added) | 3 |
| PVs Matched | 13 |
| PVs Modified | 9 |
| PVs Deleted | 124 |
| PVs Added | 45 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - populationType: 24
  - value: 24
  - employmentStatus: 17
  - timePeriod: 16
  - gender: 14
  - race: 14
  - facultyType: 7
  - teachingExperienceLevel: 4
  - absenteeismStatus: 1
  - statType: 1

### Properties Added (Extra in LLM output)
  - educatorType: 11
  - statType: 11
  - measuredProperty: 11
  - populationType: 2
  - gender: 2
  - value: 2
  - p4: 1
  - p3: 1
  - p5: 1
  - prop: 1

### Properties Modified (Different values)
  - populationType: 9

## Generation Notes

```markdown
# us_urban_school_teachers - PVMAP Generation Notes

Generated: 2026-01-14T00:50:19.920753

Total attempts: 1

---

Looking at this Civil Rights Data Collection (CRDC) education data, I need to map school staff metrics (security, teachers, counselors, etc.) to Data Commons format.

**Data Pattern**: Wide data with multiple value columns, one observation per row (school).

**Key Decisions**:
1. **observationAbout**: Use `ncesid` column (NCES school ID) → `nces/{Data}` (standard DC pattern for schools)
2. **observationDate**: Map from `YEAR` column
3. **Multiple metrics**: Each staff count column needs full StatVar properties
4. **populationType**: `Person` for all staff counts
5. **measuredProperty**: `count` for all staff counts  
6. **statType**: `measuredValue`
7. **Constraints**: Use `educatorType` to distinguish staff roles (Teacher, SecurityOfficer, Counselor, Nurse, Psychologist, SocialWorker)
8. **certificationStatus**: For teacher columns (Certified vs Not Certified)
9. **Suppression markers**: Values like `-9` (missing), `-4` (suppressed) will not parse as valid numbers and will be skipped automatically

**Limitations**:
- Suppression codes (`-9`, `-4`) will be skipped (expected behavior)
- No preprocessing needed for this flat structure

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
YEAR,observationDate,{Data}
ncesid,observationAbout,nces/{Data}
SCH_FTESECURITY_LEO,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,SecurityOfficer
SCH_FTESECURITY_GUA,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,SecurityGuard
SCH_FTETEACH_TOT,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Teacher
SCH_FTETEACH_CERT,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Teacher,certificationStatus,Certified
SCH_FTETEACH_NOTCERT,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Teacher,certificationStatus,NotCertified
TOT_TEACHERS_CURR_M,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Teacher,gender,Male
TOT_TEACHERS_CURR_F,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Teacher,gender,Female
SCH_FTECOUNSELORS,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Counselor
SCH_FTESERVICES_NUR,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Nurse
SCH_FTESERVICES_PSY,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,Psychologist
SCH_FTESERVICES_SOC,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,educatorType,SocialWorker
```

```

## Diff Excerpt

```diff
+ 
- populationType: dcid:Teacher
- gender: dcid:Male
- race: dcid:NativeHawaiianOrOtherPacificIslanderAlone
- timePeriod: dcid:CurrentSchoolYear
- value: {Number}


+ 
- populationType: dcid:Teacher
- gender: dcid:Female
- race: dcid:NativeHawaiianOrOtherPacificIslanderAlone
- timePeriod: dcid:CurrentSchoolYear
- value: {Number}


  observationAbout: dcid:nces/{Data}


- populationType: dcid:Teacher
?                      ^^^^^

+ populationType: dcid:Person
?                      ^  +++

+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  certificationStatus: dcid:Certified
- employmentStatus: dcid:FullTimeEmployee
+ educatorType: dcid:Teacher

```

## Generation Logs

- `logs/us_urban_school_teachers/generation_20260114_004015.log`
- `logs/us_urban_school_teachers/generation_20260114_005003.log`
