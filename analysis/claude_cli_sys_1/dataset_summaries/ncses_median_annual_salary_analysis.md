# ncses_median_annual_salary - Analysis

**Generated**: 2026-01-19T13:36:09.901407

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 97.4% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 39 |
| Nodes Auto-Generated | 39 |
| Nodes Matched | 0 |
| Nodes With Diff | 38 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 53 |
| PVs Added | 5 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - value: 13
  - occupation: 8
  - race: 6
  - observationDate: 5
  - age: 4
  - gender: 2
  - ethnicity: 2
  - citizenship: 2
  - disabilityStatus: 2
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - educationalAttainment: 1
  - employmentStatus: 1
  - observationAbout: 1
  - unit: 1
  - p1: 1
  - prop: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 1
  - observationDate: 1
  - variableMeasured: 1
  - property: 1
  - value: 1

## Generation Notes

```markdown
# ncses_median_annual_salary - PVMAP Generation Notes

Generated: 2026-01-16T17:03:55.322165

Total attempts: 1

---

Looking at this input data, I can clearly see this is **pre-formatted Data Commons data** because:

1. ✅ Has `variableMeasured` column with DCID values (e.g., `dcid:Median_Earnings_Person_EducationalAttainmentCollegeGraduate_Employed`)
2. ✅ Has `observationAbout` column with place DCIDs (`country/USA`)
3. ✅ Has `observationDate` column with standard year format (`2021`, `2023`)
4. ✅ Has `value` column with numeric measurements

This requires a **passthrough mapping** - I should NOT try to deconstruct the DCIDs or add StatVar properties.

```csv
key,property,value
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,variableMeasured,{Data}
```

**CHECKLIST COMPLETED:**
- [x] **Data format detected**: Pre-formatted DC data → passthrough mapping used
- [x] **observationAbout mapped**: Using existing `observationAbout` column (country/USA)
- [x] **Keys exactly match input**: `observationAbout`, `observationDate`, `value`, `variableMeasured`
- [x] **Special char keys double-quoted**: Not needed (no special characters)
- [x] **CSV formatting valid**: Simple structure, properly formatted
- [x] **Value column**: Maps to `{Number}` with `variableMeasured` preserved from input
- [x] **Dimension columns**: Already encoded in variableMeasured DCIDs (no separate mapping needed)
- [x] **observationDate format**: YYYY format from input data
- [x] **observationAbout uses valid DCID**: country/USA from input
- [x] **No dynamic place construction**: Using exact input values
- [x] **Property names match DC vocabulary**: Using standard DC observation properties

**Note**: This dataset is already in Data Commons format. The processor will pass through all values as-is without constructing new StatVars.

```

## Diff Excerpt

```diff
- observationDate: 2025
+ 


+ 
- race: dcid:Asian
- value: {Number}


  


+ 
- race: dcid:AmericanIndianOrAlaskaNativeAlone
- value: {Number}


- gender: dcid:Male
+ 


- occupation: dcid:SOCv2018/19-1029
+ 


+ 
- populationType: dcid:Person
- measuredProperty: dcid:earnings
- statType: dcid:medianValue
- educationalAttainment: dcid:CollegeGraduate
- employmentStatus: dcid:Employed
- observationAbout: dcid:country/USA
- unit: dcid:USDollar


- 
+ observationAbout: {Data}


- observationDate: {Data}
+ 


- age: dcid:Years50To75
+ 


+ 
- race: dcid:BlackOrAfricanAmericanAlone
- value: {Number}

```

## Generation Logs

- `logs/ncses_median_annual_salary/generation_20260116_143237.log`
- `logs/ncses_median_annual_salary/generation_20260116_165000.log`
- `logs/ncses_median_annual_salary/generation_20260116_170342.log`
