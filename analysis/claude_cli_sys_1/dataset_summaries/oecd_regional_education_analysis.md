# oecd_regional_education - Analysis

**Generated**: 2026-01-19T13:36:09.909368

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 95.7% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 23 |
| Nodes Auto-Generated | 23 |
| Nodes Matched | 0 |
| Nodes With Diff | 22 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 37 |
| PVs Added | 6 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - name: 7
  - educationalAttainment: 7
  - Gender: 3
  - gender: 2
  - Age: 2
  - age: 2
  - observationDate: 1
  - value: 1
  - unit: 1
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - measurementDenominator: 1
  - observationAbout: 1
  - p1: 1
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1
  - prop: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 1
  - value: 1
  - variableMeasured: 1
  - observationDate: 1
  - property: 1
  - property2: 1

## Generation Notes

```markdown
# oecd_regional_education - PVMAP Generation Notes

Generated: 2026-01-16T14:42:53.665716

Total attempts: 1

---

Looking at the input data, I can see this is **already in Data Commons format** with:
- `observationAbout` column containing DCIDs (e.g., `dcid:country/USA`)
- `observationDate` column with years
- `variableMeasured` column with stat var DCIDs (e.g., `dcid:Count_Person_25To64Years_EducationalAttainmentMastersDegreeOrHigher_AsAFractionOf_Count_Person_25To64Years`)
- `value` column with numeric values

This is **Pattern A: Flat Data** where each row is a complete observation.

```csv
key,property,value,property2,value2
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
```

**Key Points:**
1. The data uses `dcid:` prefixes - these will be stripped automatically by the processor
2. `variableMeasured` is explicitly provided (unusual but valid pattern)
3. All observations are for `country/USA` only
4. Years range from 2000-2024
5. All StatVar properties are encoded in the `variableMeasured` DCIDs - no need to decompose them

**Data Characteristics:**
- Place: Single country (USA)
- Time: Yearly observations (2000-2024, not continuous)
- Variables: Educational attainment statistics with various breakdowns:
  - Age groups (25-64 years, 25-34 years)
  - Gender (total, female, male)
  - Education levels (Masters+, Bachelors+, Doctorate, etc.)
- Measurement: All are fractions (rates/proportions)

**Note:** This is an uncommon pattern where `variableMeasured` is provided as input data rather than being constructed by the processor. The simple pass-through mapping above is all that's needed.

```

## Diff Excerpt

```diff
- observationDate: {Number}
+ 


+ 
- Gender: "Women who"
- gender: dcid:Female


- value: {Number}
+ 


+ 
- name: "Fraction of {Age}, {Gender} have attained Below upper secondary education."
- educationalAttainment: dcid:LowerSecondaryEducation


- unit: dcid:Percent
+ 


- 
+ observationAbout: {Data}


+ 
- name: "Fraction of {Age}, {Gender} have attained Bachelor's or equivalent level."
- educationalAttainment: dcid:BachelorsDegreeOrHigher


+ 
- name: "Fraction of {Age}, {Gender} have attained Master’s or equivalent level."
- educationalAttainment: dcid:MastersDegreeOrHigher


+ 
- Gender: "Men who"
- gender: dcid:Male


  


+ 
- Age: "25 to 34 years"
- age: dcid:Years25To34


- 

```

## Generation Logs

- `logs/oecd_regional_education/generation_20260116_144239.log`
