# doctoratedegreeemployment - Analysis

**Generated**: 2026-01-19T13:36:09.883112

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 12.9% | 🔴 Poor |
| Node Coverage | 61.3% | - |
| PV Accuracy | 20.0% | 🟠 Needs Work |
| Precision | 34.7% | - |
| Recall | 20.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 31 |
| Nodes Auto-Generated | 28 |
| Nodes Matched | 4 |
| Nodes With Diff | 15 |
| Nodes Missing (LLM missed) | 12 |
| Nodes Extra (LLM added) | 9 |
| PVs Matched | 14 |
| PVs Modified | 3 |
| PVs Deleted | 53 |
| PVs Added | 32 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - occupation: 11
  - value: 6
  - facultyType: 5
  - doctorateDegreeMajor: 5
  - observationAbout: 5
  - educationalAttainment: 5
  - tenureStatus: 3
  - measuredProperty: 3
  - populationType: 3
  - gender: 2
  - p6: 1
  - p7: 1
  - p1: 1
  - p5: 1
  - ethnicity: 1

### Properties Added (Extra in LLM output)
  - occupationType: 9
  - statType: 5
  - tenureStatus: 4
  - populationType: 3
  - value: 3
  - measuredProperty: 3
  - gender: 2
  - prop: 1
  - race: 1
  - observationAbout: 1

### Properties Modified (Different values)
  - race: 2
  - observationDate: 1

## Generation Notes

```markdown
# doctoratedegreeemployment - PVMAP Generation Notes

Generated: 2026-01-14T00:53:10.736221

Total attempts: 2

---

Looking at the data and error logs, the primary issue is that **no observations have a place** (`observationAbout`). The error `"No place in SVObs"` appears for every row.

The problem is that this dataset has **no place/geography column**. The data shows doctorate degree holders by occupation, tenure status, race/ethnicity, and gender - but it doesn't specify WHICH geographic area these counts apply to.

Looking at the processor config, I see `#places_within,country/USA` is set, suggesting this is US-level data. Since there's no place column in the input, I need to set `observationAbout` **globally** on a column that appears in every row.

The data also has several structural issues:
1. **Header rows** like "All occupations", "Scientist", "Biological/life scientist" are category labels, not data rows
2. **Demographic labels** like "Female", "Male", "White", "Black or African American" appear as standalone rows without clear association
3. The dataset uses a **hierarchical indentation pattern** that the processor cannot handle directly

However, I can create a PVMAP that will work for the **properly structured data rows** - those with actual numeric values and complete demographic information.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Year,observationDate,{Data},observationAbout,country/USA,,,,
Total,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,tenureStatus,Total
Tenured,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,tenureStatus,Tenured
On Tenure Track,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,tenureStatus,OnTenureTrack
Not On Tenure Track,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,tenureStatus,NotOnTenureTrack
Tenure Not Applicable,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,tenureStatus,NotApplicable
"All Females",gender,Female,,,,,,
"Hispanic or Latinoa",race,HispanicOrLatino,,,,,,
"American Indian or Alaska Native",race,AmericanIndianOrAlaskaNative,,,,,,
"Native Hawaiian or Other Pacific Islander",race,NativeHawaiianOrOtherPacificIslander,,,,,,
White,race,WhiteAlone,,,,,,
"Black or African American",race,BlackOrAfricanAmericanAlone,,,,,,
Asian,race,AsianAlone,,,,,,
"More than one raceb",race,TwoOrMoreRaces,,,,,,
"All Males",gender,Male,,,,,,
"All occupations",occupationType,All,,,,,,
"All Scientists",occupationType,Scientist,,,,,,
"All Biological/life scientists",occupationType,BiologicalScientist,,,,,,
"All Computer and information scientists",occupationType,ComputerScientist,,,,,,
"All Mathematical scientists",occupationType,MathematicalScientist,,,,,,
"Physical scientist",occupationType,PhysicalScientist,,,,,,
Psychologist,occupationType,Psychologist,,,,,,
Engineer,occupationType,Engineer,,,,,,
"S&E-related occupationsd",occupationTyp...
```

## Diff Excerpt

```diff
  race: dcid:BlackOrAfricanAmericanAlone


- 
+ occupationType: dcid:All


+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- doctorateDegreeMajor: dcid:ScienceAndEngineeringRelatedMajor
- educationalAttainment: dcid:DoctorateDegree
- facultyType: dcid:UniversityAndCollegeTeacher
- observationAbout: dcid:country/USA
- tenureStatus: dcid:NotOnTenureTrack
- value: {Number}


- gender: dcid:Female
+ 


- occupation: dcid:SOCv2018/19-3030
+ occupationType: dcid:Psychologist


- occupation: dcid:ScienceAndEngineeringRelated
+ occupationType: dcid:SERelated


- value: 0
+ 


- p1: dcid:v1
  p2: dcid:v2
  p3: dcid:v3
  p4: dcid:v4
+ prop: dcid:value
- p5: dcid:v5
- p6: dcid:v6
- p7: dcid:v7


  race: dcid:AmericanIndianOrAlaskaNative


- value: 0
+ 


```

## Generation Logs

- `logs/doctoratedegreeemployment/generation_20260114_001245.log`
- `logs/doctoratedegreeemployment/generation_20260114_001723.log`
- `logs/doctoratedegreeemployment/generation_20260114_005221.log`
