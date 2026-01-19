# school_retention - Analysis

**Generated**: 2026-01-19T13:36:09.918844

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.8% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 543 |
| Nodes Auto-Generated | 543 |
| Nodes Matched | 0 |
| Nodes With Diff | 542 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 2750 |
| PVs Added | 8 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - schoolGradeLevel: 533
  - studentStatus: 533
  - value: 533
  - gender: 520
  - race: 364
  - disabilityStatus: 104
  - educationProgram: 104
  - englishProficiency: 52
  - educationalInstitutionType: 2
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - observationAbout: 1
  - observationDate: 1

### Properties Added (Extra in LLM output)
  - value: 1
  - property: 1
  - property2: 1
  - property3: 1
  - property4: 1
  - variableMeasured: 1
  - observationAbout: 1
  - observationDate: 1

## Generation Notes

```markdown
# school_retention - PVMAP Generation Notes

Generated: 2026-01-16T14:50:25.739503

Total attempts: 1

---

```csv
key,property,value,property2,value2,property3,value3,property4,value4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
```

---

## Analysis

**Data Structure**: This is pre-processed Data Commons format where:
- `observationAbout` contains school NCES IDs (already DCIDs: `nces/010000800303`)
- `observationDate` contains year values
- `variableMeasured` contains complete StatVar DCIDs (e.g., `dcid:Count_Student_Male_AmericanIndianOrAlaskaNative_SchoolGrade5_Retained`)
- `value` contains numeric observations

**Why This PV Map Works:**
1. **All columns map directly to their property names** - the input is already in near-final Data Commons format
2. **`variableMeasured` already contains complete StatVar DCIDs** - no need to construct `populationType`, `measuredProperty`, `statType` separately
3. **Use `{Data}` for string values** that are already formatted correctly
4. **Use `{Number}` only for the numeric value column**

**Key Insight**: When `variableMeasured` contains a complete DCID (starting with `dcid:`), the processor uses that directly instead of constructing a StatVar from individual properties. This is the simplest possible mapping.

**No Preprocessing Required**: The data is already clean and properly formatted.

```

## Diff Excerpt

```diff
+ 
- gender: dcid:Male
- race: dcid:Asian
- schoolGradeLevel: dcid:SchoolGrade8
- studentStatus: dcid:StudentRetained
- value: {Number}


+ 
- gender: dcid:Female
- race: dcid:Black
- schoolGradeLevel: dcid:SchoolGrade9
- studentStatus: dcid:StudentRetained
- value: {Number}


+ 
- gender: dcid:Female
- race: dcid:HispanicOrLatino
- schoolGradeLevel: dcid:SchoolGrade5
- studentStatus: dcid:StudentRetained
- value: {Number}


+ 
- disabilityStatus: dcid:WithDisability
- educationProgram: dcid:Section504Plan
- gender: dcid:Female
- schoolGradeLevel: dcid:SchoolGrade9
- studentStatus: dcid:StudentRetained
- value: {Number}


+ 
- gender: dcid:Female
- race: dcid:Asian
- schoolGradeLevel: dcid:SchoolGrade4
- studentStatus: dcid:StudentRetained
- value: {Number}


+ 
- gender: dcid:Male
- race: dcid:White
- schoolGradeLevel: dcid:Kindergarten
- studentStatus: dcid:StudentRetained
- value: {Number}


+ 

```

## Generation Logs

- `logs/school_retention/generation_20260116_145014.log`
