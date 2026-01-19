# us_nces - Analysis

**Generated**: 2026-01-19T13:36:09.942454

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 97.8% | - |
| PV Accuracy | 2.2% | 🔴 Poor |
| Precision | 17.6% | - |
| Recall | 2.2% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 46 |
| Nodes Auto-Generated | 46 |
| Nodes Matched | 0 |
| Nodes With Diff | 45 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 3 |
| PVs Modified | 0 |
| PVs Deleted | 136 |
| PVs Added | 14 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - value: 19
  - populationType: 16
  - measuredProperty: 16
  - educationalAttainment: 16
  - employmentStatus: 16
  - observationAbout: 16
  - observationDate: 16
  - occupation: 8
  - race: 6
  - gender: 2
  - ethnicity: 1
  - p1: 1
  - p5: 1
  - p6: 1
  - p7: 1

### Properties Added (Extra in LLM output)
  - measurementMethod: 1
  - observationDate: 1
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - value: 1
  - unit: 1
  - observationPeriod: 1
  - prop: 1
  - educationalAttainment: 1
  - employmentStatus: 1
  - variableMeasuredSuffix: 1
  - scalingFactor: 1
  - observationAbout: 1

## Generation Notes

```markdown
# us_nces - PVMAP Generation Notes

Generated: 2026-01-16T13:13:38.983488

Total attempts: 1

---

Looking at this input data, I can see it's **already in Data Commons format** - it has `observationAbout`, `observationDate`, `value`, and `variableMeasured` columns with complete DCID references. However, to generate a PV map as requested, I need to extract the StatVar properties from the `variableMeasured` DCIDs and map them appropriately.

This is **Pattern A: Flat Data** - each row is a complete observation.

## Analysis of variableMeasured patterns:

The DCIDs encode multiple constraints:
- Base: `Count_Person_EducationalAttainmentBachelorsDegreeOrHigher_Employed`
- With demographics: `_HispanicOrLatino`, `_Female`, `_Male`, `_Asian`, `_BlackOrAfricanAmericanAlone`, `_WhiteAlone`, `_TwoOrMoreRaces`, `_AmericanIndianOrAlaskaNative`, `_OtherPacificIslander`
- With occupations: `_SOCLifeScientistsOccupation`, `_SOCComputerMathematicalOccupation`, `_SOCEngineersOccupation`, `_ScienceAndEngineeringRelatedOccupation`, `_NonScienceAndEngineeringOccupation`, etc.

Since the `variableMeasured` column contains complete DCIDs that the processor would auto-construct, I'll map the data so the processor reconstructs these same DCIDs from the individual property constraints.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
variableMeasured,#Regex,"dcid:Count_Person_EducationalAttainmentBachelorsDegreeOrHigher_Employed(?P<Constraints>.*)",educationalAttainment,BachelorsDegreeOrHigher,employmentStatus,Employed,variableMeasuredSuffix,{Constraints}
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
measurementMethod,measurementMethod,{Data}
observationPeriod,observationPeriod,{Data}
```

**Note:** This data has a critical limitation - the `variableMeasured` column contains pre-constructed DCIDs with encoded constraints (race, sex, occupation) that cannot be reliably parsed back into individual property-value pairs using regex alone. The above PVMAP extracts the base properties (educational attainment, employment status) but preserves the constraint suffix. 

For proper schematization, you would need to either:
1. Parse each unique `variableMeasured` DCID and create explicit mappings for all combinations
2. Request source data with separate columns for race, sex, and occupation categories

The processor will attempt to match `variableMeasuredSuffix` but this is a non-standard approach. For production use, explicit mapping of each unique `variableMeasured` value would be more reliable.

```

## Diff Excerpt

```diff
+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- educationalAttainment: dcid:BachelorsDegreeOrHigher
- employmentStatus: dcid:Employed
- observationAbout: dcid:country/USA
- observationDate: 2021
- value: @Number


- occupation: dcid:ScienceAndEngineeringRelated
+ 


- 
+ measurementMethod: {Data}


+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- educationalAttainment: dcid:BachelorsDegreeOrHigher
- employmentStatus: dcid:Employed
- observationAbout: dcid:country/USA
- observationDate: 2017
- value: @Number


- race: dcid:BlackOrAfricanAmericanAlone
+ 


+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- educationalAttainment: dcid:BachelorsDegreeOrHigher
- employmentStatus: dcid:Employed
- observationAbout: dcid:country/USA
- observationDate: 2013
- value: @Number


- race: dcid:Asian
+ 


- occupation: dcid:SOCv2018/19-1000
+ 



```

## Generation Logs

- `logs/us_nces/generation_20260116_131319.log`
