# us_bls_us_cpi - Analysis

**Generated**: 2026-01-19T13:36:09.935038

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 98.7% | - |
| PV Accuracy | 2.2% | 🔴 Poor |
| Precision | 2.1% | - |
| Recall | 2.2% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 77 |
| Nodes Auto-Generated | 77 |
| Nodes Matched | 0 |
| Nodes With Diff | 76 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 2 |
| PVs Modified | 0 |
| PVs Deleted | 88 |
| PVs Added | 93 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationDate: 25
  - Month: 24
  - Year: 21
  - consumer: 4
  - populationType: 3
  - measuredProperty: 3
  - observationAbout: 3
  - measurementQualifier: 1
  - value: 1
  - p1: 1
  - consumerGoodsCategory: 1
  - Category: 1

### Properties Added (Extra in LLM output)
  - populationType: 13
  - measuredProperty: 13
  - statType: 13
  - observationAbout: 13
  - observationDate: 13
  - value: 13
  - expenditureCategory: 8
  - IndentLevel: 1
  - p4: 1
  - p5: 1
  - p6: 1
  - p7: 1
  - property: 1
  - ExpenditureCategory: 1

## Generation Notes

```markdown
# us_bls_us_cpi - PVMAP Generation Notes

Generated: 2026-01-16T15:11:53.769529

Total attempts: 2

---

Looking at the errors, I can see the main issue: **every observation is missing `observationAbout` (place)** and is being dropped. The logs show `warning-svobs-missing-place = 352`.

Analyzing the input data structure, this is a **multi-row header with wide data** where:
- Row 4 contains first-level column headers (`Unadjusted indexes`, `Seasonally adjusted indexes`, etc.)
- Row 5 contains second-level headers (dates like `Jun. 2024`, `Jul. 2024`)
- Row 6 contains third-level headers (redundant dates like `Jun. 2024- Jun. 2025`)

The data represents **US national CPI data**, so `observationAbout` should be `country/USA`.

Key issues to fix:
1. Add `observationAbout,country/USA` to ALL value columns
2. Map the actual date columns from row 5 (not the multi-row header structure)
3. Parse dates correctly (e.g., "Jun. 2024" → "2024-06")
4. Add complete StatVar properties to each value column
5. The first few rows contain metadata and should be handled correctly by `header_rows=6`

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
Indent Level,IndentLevel,{Data}
Expenditure category,ExpenditureCategory,{Data}
All items,expenditureCategory,AllItems
Food,expenditureCategory,Food
Food at home,expenditureCategory,FoodAtHome
Cereals and bakery products,expenditureCategory,CerealsBakeryProducts
Cereals and cereal products,expenditureCategory,CerealsCerealProducts
Flour and prepared flour mixes,expenditureCategory,FlourPreparedFlourMixes
Breakfast cereal(4),expenditureCategory,BreakfastCereal
"Rice, pasta, cornmeal",expenditureCategory,RicePastaCornmeal
"Jun. 2024",observationDate,2024-06,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Jul. 2024",observationDate,2024-07,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Aug. 2024",observationDate,2024-08,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Sep. 2024",observationDate,2024-09,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Oct. 2024",observationDate,2024-10,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Nov. 2024",observationDate,2024-11,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Dec. 2024",observationDate,2024-12,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Jan. 2025",observationDate,2025-01,value,{Number},observationAbout,country/USA,populationType,ConsumerPriceIndex,measuredProperty,index,statType,measuredValue
"Feb. 2025",observationDate,2025-02,...
```

## Diff Excerpt

```diff
- Year: 2010
+ 


+ 
- Month: 8
- observationDate: {Year}-{Month}


- Year: 2013
+ 


+ 
- Month: 12
- observationDate: {Year}-{Month}


- 
+ populationType: dcid:ConsumerPriceIndex
+ measuredProperty: dcid:index
+ statType: dcid:measuredValue
+ observationAbout: dcid:country/USA
+ observationDate: 2024-06
+ value: {Number}


- Year: 2014
+ 


- consumer: dcid:UrbanConsumer
+ 


- 
+ populationType: dcid:ConsumerPriceIndex
+ measuredProperty: dcid:index
+ statType: dcid:measuredValue
+ observationAbout: dcid:country/USA
+ observationDate: 2024-11
+ value: {Number}


+ 
- Month: 7
- observationDate: {Year}-{Month}


+ 

```

## Generation Logs

- `logs/us_bls_us_cpi/generation_20260116_150847.log`
