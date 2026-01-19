# oecd_quarterly_gdp - Analysis

**Generated**: 2026-01-19T13:36:09.908492

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 97.0% | - |
| PV Accuracy | 7.7% | 🔴 Poor |
| Precision | 3.4% | - |
| Recall | 7.7% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 33 |
| Nodes Auto-Generated | 33 |
| Nodes Matched | 0 |
| Nodes With Diff | 32 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 1 |
| PVs Modified | 0 |
| PVs Deleted | 12 |
| PVs Added | 28 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - statType: 2
  - comparisonPeriod: 2
  - measurementQualifier: 1
  - unit: 1
  - populationType: 1
  - measuredProperty: 1
  - observationPeriod: 1
  - measurementMethod: 1
  - property2: 1
  - property3: 1

### Properties Added (Extra in LLM output)
  - observationDate: 23
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - observationPeriod: 1
  - unit: 1

## Generation Notes

```markdown
# oecd_quarterly_gdp - PVMAP Generation Notes

Generated: 2026-01-16T17:09:21.703822

Total attempts: 3

---

Looking at the error logs, I can see the main issue: **"Unable to resolve SVObs date"** - the processor cannot parse the date format `2025-Q1`, `2023-Q1`, etc.

The processor expects dates in standard formats: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`. The quarterly format `YYYY-QX` needs to be converted.

Additionally, I need to map the `REF_AREA` column values to proper country DCIDs.

```csv
key,property,value
REF_AREA,observationAbout,country/{Data}
TIME_PERIOD,#Regex,"^(?P<Year>\d{4})-Q(?P<Quarter>[1-4])$",observationDate,{Year}-{Quarter:02d}
TIME_PERIOD:2020-Q1,observationDate,2020-01
TIME_PERIOD:2020-Q2,observationDate,2020-04
TIME_PERIOD:2020-Q3,observationDate,2020-07
TIME_PERIOD:2020-Q4,observationDate,2020-10
TIME_PERIOD:2021-Q1,observationDate,2021-01
TIME_PERIOD:2021-Q2,observationDate,2021-04
TIME_PERIOD:2021-Q3,observationDate,2021-07
TIME_PERIOD:2021-Q4,observationDate,2021-10
TIME_PERIOD:2022-Q1,observationDate,2022-01
TIME_PERIOD:2022-Q2,observationDate,2022-04
TIME_PERIOD:2022-Q3,observationDate,2022-07
TIME_PERIOD:2022-Q4,observationDate,2022-10
TIME_PERIOD:2023-Q1,observationDate,2023-01
TIME_PERIOD:2023-Q2,observationDate,2023-04
TIME_PERIOD:2023-Q3,observationDate,2023-07
TIME_PERIOD:2023-Q4,observationDate,2023-10
TIME_PERIOD:2024-Q1,observationDate,2024-01
TIME_PERIOD:2024-Q2,observationDate,2024-04
TIME_PERIOD:2024-Q3,observationDate,2024-07
TIME_PERIOD:2024-Q4,observationDate,2024-10
TIME_PERIOD:2025-Q1,observationDate,2025-01
TIME_PERIOD:2025-Q2,observationDate,2025-04
value,value,{Number},populationType,EconomicActivity,measuredProperty,grossDomesticProduct,statType,growthRate,unit,Percent,observationPeriod,P3M
```

**Key fixes:**
1. **observationAbout**: Maps `REF_AREA` to `country/{Data}` format (IRL→country/IRL, EST→country/EST, etc.)
2. **observationDate**: Converts quarterly format `YYYY-QX` to `YYYY-MM` format:
   - Q1 → 01 (January)
   - Q2 → 04 (April)
   - Q3 → 07 (July)
   - Q4 → 10 (October)
3. **value column**: Includes all required StatVar properties plus unit and observationPeriod

**Data limitations noted:**
- Assumes REF_AREA codes are ISO-3 country codes compatible with `country/{Data}` format
- Quarter mapping uses first month of each quarter as the observation date

```

## Diff Excerpt

```diff
  


  


- measurementQualifier: dcid:Adjusted
+ 


- unit: dcid:Percent
+ 


- 
+ observationDate: 2025-01


- 
+ observationDate: 2022-07


- 
+ observationDate: 2023-01


- 
+ observationDate: 2024-07


- 
+ observationDate: {Year}-{Quarter:02d}


- 
+ observationDate: 2022-10


- 
+ observationDate: 2020-04


- 
+ observationDate: 2021-07


  


- 

```

## Generation Logs

- `logs/oecd_quarterly_gdp/generation_20260116_144036.log`
- `logs/oecd_quarterly_gdp/generation_20260116_165000.log`
- `logs/oecd_quarterly_gdp/generation_20260116_170501.log`
