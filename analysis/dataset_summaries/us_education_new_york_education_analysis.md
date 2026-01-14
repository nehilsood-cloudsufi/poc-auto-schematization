# us_education_new_york_education - Analysis

**Generated**: 2026-01-14T14:56:48.874169

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 6.4% | 🔴 Poor |
| Node Coverage | 53.2% | - |
| PV Accuracy | 33.3% | 🟠 Needs Work |
| Precision | 44.4% | - |
| Recall | 33.3% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 47 |
| Nodes Auto-Generated | 24 |
| Nodes Matched | 3 |
| Nodes With Diff | 22 |
| Nodes Missing (LLM missed) | 23 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 27 |
| PVs Modified | 13 |
| PVs Deleted | 41 |
| PVs Added | 50 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - assessmentScoreLevel: 10
  - schoolGradeLevel: 6
  - measurementDenominator: 5
  - race: 4
  - gender: 4
  - disabilityStatus: 4
  - educationalDegree: 2
  - languageLearned: 2
  - populationType: 1
  - schoolSubject: 1

### Properties Added (Extra in LLM output)
  - measuredProperty: 11
  - statType: 11
  - assessmentType: 11
  - performanceLevel: 10
  - scoreType: 1
  - p6: 1
  - p2: 1
  - p3: 1
  - p5: 1
  - p4: 1

### Properties Modified (Different values)
  - observationAbout: 5
  - race: 3
  - observationDate: 1
  - measuredProperty: 1
  - statType: 1

## Generation Notes

```markdown
# us_education_new_york_education - PVMAP Generation Notes

Generated: 2026-01-14T00:33:44.480236

Total attempts: 1

---

Looking at this NYC school data, I need to map test scores and performance levels by demographic groups across boroughs.

**Key observations:**
1. Each row is a complete observation (Pattern A - Flat Data)
2. Geographic entity: Borough (Bronx shown)
3. Temporal: Year column
4. Demographic constraint: Column with race/ethnicity values
5. Multiple metrics: Number Tested, Mean Scale Score, and various Level counts/percentages
6. Need to map Borough → DCID (using explicit mapping)
7. Grade needs to be captured as a constraint

**Mapping strategy:**
- Use column-specific properties for shared StatVar attributes on each metric column
- Map Borough values to DCIDs (Bronx likely maps to a geoId)
- Capture Year for observationDate
- Map Demographic values to race property
- Map Grade to constraint property (will need to format as "Grade3", "Grade4", etc.)
- Each metric column gets full StatVar definition

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
Borough:BRONX,observationAbout,geoId/3600536000
Borough:BROOKLYN,observationAbout,geoId/3600547000
Borough:MANHATTAN,observationAbout,geoId/3600561000
Borough:QUEENS,observationAbout,geoId/3600581000
Borough:STATEN ISLAND,observationAbout,geoId/3600585000
Grade,#Format,"grade=Grade{Number}"
Year,observationDate,{Data}
Demographic:Asian,race,AsianAlone
Demographic:Black,race,BlackOrAfricanAmericanAlone
Demographic:Hispanic,race,HispanicOrLatino
Demographic:White,race,WhiteAlone
Number Tested,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,assessmentType,StandardizedTest
Mean Scale Score,value,{Number},populationType,Student,measuredProperty,mean,statType,measuredValue,assessmentType,StandardizedTest,scoreType,ScaleScore
Num Level 1,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,assessmentType,StandardizedTest,performanceLevel,Level1
Pct Level 1,value,{Number},populationType,Student,measuredProperty,percentage,statType,measuredValue,assessmentType,StandardizedTest,performanceLevel,Level1
Num Level 2,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,assessmentType,StandardizedTest,performanceLevel,Level2
Pct Level 2,value,{Number},populationType,Student,measuredProperty,percentage,statType,measuredValue,assessmentType,StandardizedTest,performanceLevel,Level2
Num Level 3,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,assessmentType,StandardizedTest,performanceLevel,Level3
Pct Level 3,value,{Number},populationType,Student,measuredProperty,percentage,statType,measuredValue,assessmentType,StandardizedTest,performanceLevel,Level3
Num Level 4,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,assessmentType,StandardizedTest,performanceLevel,Level4
Pct Level 4,value,{Number},populationType,Student,measuredPropert
```

## Diff Excerpt

```diff
- race: dcid:White
+ 


- observationAbout: dcid:geoId/36005
+ observationAbout: dcid:geoId/3600536000
?                                   +++++



  populationType: dcid:Student
- measurementDenominator: -assessmentScoreLevel
- assessmentScoreLevel: dcid:AssessmentLevel4
+ measuredProperty: dcid:percentage
+ statType: dcid:measuredValue
+ assessmentType: dcid:StandardizedTest
+ performanceLevel: dcid:Level4
  value: {Number}


- educationalDegree: dcid:GeneralEducation
+ 


  populationType: dcid:Student
- assessmentScoreLevel: dcid:AssessmentLevel3AndLevel4
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ assessmentType: dcid:StandardizedTest
+ performanceLevel: dcid:Level3And4

```

## Generation Logs

- `logs/us_education_new_york_education/generation_20260114_003320.log`
