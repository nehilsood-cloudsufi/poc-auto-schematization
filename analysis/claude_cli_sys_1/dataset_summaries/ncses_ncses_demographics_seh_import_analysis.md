# ncses_ncses_demographics_seh_import - Analysis

**Generated**: 2026-01-19T13:36:09.902645

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 44.7% | 🟠 Needs Work |
| Node Coverage | 105.3% | - |
| PV Accuracy | 14.6% | 🔴 Poor |
| Precision | 64.6% | - |
| Recall | 14.6% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 38 |
| Nodes Auto-Generated | 40 |
| Nodes Matched | 17 |
| Nodes With Diff | 23 |
| Nodes Missing (LLM missed) | 12 |
| Nodes Extra (LLM added) | 1 |
| PVs Matched | 23 |
| PVs Modified | 8 |
| PVs Deleted | 126 |
| PVs Added | 17 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - populationType: 19
  - observationAbout: 15
  - educationalDegree: 14
  - observationDate: 14
  - statType: 14
  - measuredProperty: 14
  - ethnicity: 9
  - citizenship: 8
  - value: 6
  - educationalProgram: 3
  - occupation: 2
  - educationalAttainment: 2
  - scalingFactor: 1
  - measurementDenominator: 1
  - unit: 1
  - p1: 1
  - p6: 1
  - race: 1

### Properties Added (Extra in LLM output)
  - educationLevel: 5
  - Year: 3
  - studentType: 3
  - GLOBAL: 1
  - race: 1
  - prop: 1
  - populationType: 1
  - observationDate: 1
  - measuredProperty: 1

### Properties Modified (Different values)
  - race: 6
  - citizenship: 2

## Generation Notes

```markdown
# ncses_ncses_demographics_seh_import - PVMAP Generation Notes

Generated: 2026-01-14T00:14:15.979087

Total attempts: 3

---

Looking at the error logs, I can see the main issue: **all SVObs are missing `observationAbout` (place)**. The warnings show `No place in SVObs` for every row.

The problem is that this dataset contains **national-level US statistics**, but there's no place column in the data. All observations are about `country/USA`.

Additionally, I notice:
1. The data needs `observationDate` - I need to extract the year from the section headers
2. There are rows that should be ignored (header rows, "Not Hispanic or Latino" text-only rows)
3. The `#ignore,skip` is being applied but observations are still being created

Let me fix the PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5
observationAbout,country/USA
Table 2-1,#ignore,skip
"Demographic characteristics of graduate students, postdoctoral appointees, and doctorate-holding nonfaculty researchers in science, engineering, and health: 2023",#Regex,"(?P<Year>[0-9]{4})",Year,{Year}
"Demographic characteristics of graduate students, postdoctoral appointees, and doctorate-holding nonfaculty researchers in science, engineering, and health: 2022",#Regex,"(?P<Year>[0-9]{4})",Year,{Year}
"Demographic characteristics of graduate students, postdoctoral appointees, and doctorate-holding nonfaculty researchers in science, engineering, and health: 2021",#Regex,"(?P<Year>[0-9]{4})",Year,{Year}
(Number and percent),#ignore,skip
"Sex, citizenship, ethnicity, and race",#ignore,skip
Not Hispanic or Latino,#ignore,skip
Unnamed: 1,#ignore,skip
Unnamed: 2,#ignore,skip
Unnamed: 3,#ignore,skip
Unnamed: 4,#ignore,skip
Unnamed: 5,#ignore,skip
Unnamed: 6,#ignore,skip
Unnamed: 7,#ignore,skip
Unnamed: 8,#ignore,skip
Unnamed: 9,#ignore,skip
Unnamed: 10,#ignore,skip
Number,value,{Number},observationDate,{Year},populationType,Person,measuredProperty,count,statType,measuredValue
Percent,#ignore,skip
All graduate students,studentType,AllGraduateStudents,educationLevel,GraduateStudents
Master's,studentType,Masters,educationLevel,GraduateStudents
Doctoral,studentType,Doctoral,educationLevel,GraduateStudents
Postdoctoral appointees,educationLevel,PostdoctoralAppointees
Doctorate-holding nonfaculty researchers,educationLevel,DoctorateHoldingNonfacultyResearchers
All individuals,#ignore,skip
Male,gender,Male
Female,gender,Female
U.S. citizens and permanent residentsa,citizenship,USCitizenOrPermanentResident
Hispanic or Latino,race,HispanicOrLatino
American Indian or Alaska Native,race,NotHispanicOrLatino__AmericanIndianOrAlaskaNativeAlone
Asian,race,NotHispanicOrLatino__AsianAlone
Black or African American,race,NotHispanicOrLatino__BlackOrAfricanAmericanAlone
Native Hawaiian or Other Pacific Islander,race,NotHispanicOrLatino__NativeHawaiianOrOtherPacificIslanderAlone
White,race,NotHispanicOrLatino__WhiteAlone
More than one race,race,NotHispanicOrLatino__TwoOrMoreRaces
Unknown ethnicity and race,#ignore,skip
Temporar...
```

## Diff Excerpt

```diff
- citizenship: dcid:Citizen
- ethnicity: dcid:NotHispanicOrLatino
- race: dcid:NativeHawaiianOrOtherPacificIslanderAlone
+ race: dcid:NativeHawaiianOrOtherPacificIslanderAlone__NotHispanicOrLatino
?                                                     +++++++++++++++++++++



- citizenship: dcid:VisaHolder
+ citizenship: dcid:TemporaryVisaHolder
?                   +++++++++



+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- statType: dcid:measuredValue
- educationalDegree: dcid:Engineering__Health__Science
- observationAbout: dcid:country/USA
- observationDate: 2028


  


+ race: dcid:NotHispanicOrLatino__WhiteAlone
- citizenship: dcid:Citizen
- ethnicity: dcid:NotHispanicOrLatino
- race: dcid:WhiteAlone


  


  


  gender: dcid:Female


+ 
- measurementDenominator: -citizenship,-ethnicity,-gender,-race
- scalingFactor: 100
- unit: dcid:Percent
- value: {Number}


- 
+ GLOBAL: dcid:country/USA

```

## Generation Logs

- `logs/ncses_ncses_demographics_seh_import/generation_20260114_001245.log`
