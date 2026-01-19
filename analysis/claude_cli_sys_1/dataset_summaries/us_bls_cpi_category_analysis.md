# us_bls_cpi_category - Analysis

**Generated**: 2026-01-19T13:36:09.934101

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.5% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 206 |
| Nodes Auto-Generated | 206 |
| Nodes Matched | 0 |
| Nodes With Diff | 205 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 411 |
| PVs Added | 10 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - Month: 107
  - observationPeriod: 99
  - comparisonPeriod: 97
  - consumerGoodsCategory: 58
  - observationDate: 25
  - unit: 7
  - measurementQualifier: 4
  - value: 4
  - statType: 2
  - populationType: 1
  - measuredProperty: 1
  - consumer: 1
  - measurementMethod: 1
  - observationAbout: 1
  - p1: 1
  - p2: 1
  - prop: 1

### Properties Added (Extra in LLM output)
  - variableMeasured: 1
  - observationPeriod: 1
  - observationAbout: 1
  - measurementMethod: 1
  - observationDate: 1
  - value: 1
  - scalingFactor: 1
  - property: 1
  - property2: 1
  - unit: 1

## Generation Notes

```markdown
# us_bls_cpi_category - PVMAP Generation Notes

Generated: 2026-01-16T15:07:45.537291

Total attempts: 1

---

I'll analyze the input data and generate a PV map. This data is already in a preprocessed format with Data Commons properties in the columns.

Let me examine the structure:
- `observationAbout`: Already contains place DCIDs (country/USA)
- `observationDate`: Already formatted (YYYY-MM)
- `value`: Numeric values
- `variableMeasured`: Contains full StatVar DCIDs (e.g., `dcid:SeasonallyUnadjusted_ConsumerPriceIndex_...`)
- `unit`, `scalingFactor`, `measurementMethod`, `observationPeriod`: Additional observation properties

Since `variableMeasured` contains complete StatVar DCIDs, the processor should reference these directly rather than constructing new StatVars.

```csv
key,property,value,property2,value2
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,variableMeasured,{Data}
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
measurementMethod,measurementMethod,{Data}
observationPeriod,observationPeriod,{Data}
```

**CHECKLIST:**
- [x] Keys exactly match input (case-sensitive) - All column headers matched exactly
- [x] Special char keys are double-quoted - None needed
- [x] Every value column has required properties - `value` column uses `{Number}` and references existing StatVars via `variableMeasured`
- [x] `observationDate` format - Already in YYYY-MM format, passed through with `{Data}`
- [x] `observationAbout` uses valid DCID - Already contains country/USA, passed through
- [x] No dynamic place construction - Using existing DCIDs as-is
- [x] All properties passed through directly using `{Data}` placeholder

**Note:** This data is already in Data Commons format with complete StatVar DCIDs in the `variableMeasured` column. The PV map simply passes through all columns using `{Data}` placeholder for strings and `{Number}` for the value field.

```

## Diff Excerpt

```diff
- observationDate: dcid:2033-{Month}
+ 


- consumerGoodsCategory: dcid:CerealsAndBakeryProducts
+ 


- consumerGoodsCategory: dcid:DairyAndRelatedProducts
+ 


- 
+ variableMeasured: {Data}


- consumerGoodsCategory: dcid:Shelter
+ 


- consumerGoodsCategory: dcid:MotorFuel
+ 


+ 
- measurementQualifier: dcid:BLSSeasonallyUnadjusted
- statType: dcid:growthRate
- comparisonPeriod: dcid:MonthOnChange
- observationPeriod: dcid:P1M
- value: {Number}


+ 
- Month: 1
- comparisonPeriod: dcid:YearOnChange
- observationPeriod: dcid:P1Y


+ 
- Month: 5
- comparisonPeriod: dcid:YearOnChange
- observationPeriod: dcid:P1Y


+ 
- Month: 5
- comparisonPeriod: dcid:YearOnChange
- observationPeriod: dcid:P1Y



```

## Generation Logs

- `logs/us_bls_cpi_category/generation_20260116_150731.log`
