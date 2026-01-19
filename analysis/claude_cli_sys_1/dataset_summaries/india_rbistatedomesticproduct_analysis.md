# india_rbistatedomesticproduct - Analysis

**Generated**: 2026-01-19T13:36:09.895434

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 98.1% | - |
| PV Accuracy | 3.5% | 🔴 Poor |
| Precision | 33.3% | - |
| Recall | 3.5% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 53 |
| Nodes Auto-Generated | 53 |
| Nodes Matched | 0 |
| Nodes With Diff | 52 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 5 |
| PVs Modified | 0 |
| PVs Deleted | 136 |
| PVs Added | 10 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationDate: 26
  - observationPeriod: 26
  - value: 26
  - populationType: 6
  - measuredProperty: 6
  - activitySource: 6
  - unit: 6
  - Sector: 6
  - economicSector: 6
  - Base: 4
  - name: 4
  - Product: 3
  - measurementQualifier: 2
  - Price: 2
  - measurementMethod: 2
  - measurementDenominator: 2
  - observationAbout: 1
  - p1: 1
  - prop: 1

### Properties Added (Extra in LLM output)
  - observationDate: 1
  - observationAbout: 1
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - value: 1
  - measurementMethod: 1
  - prop: 1
  - unit: 1
  - observationPeriod: 1

## Generation Notes

```markdown
# india_rbistatedomesticproduct - PVMAP Generation Notes

Generated: 2026-01-16T13:13:16.860325

Total attempts: 1

---

Looking at this input data, I can see it's already in a partially Data Commons-compatible format with some columns already using DCID notation. Let me analyze the structure:

**Input Analysis:**
- `observationAbout`: Contains DCIDs in format `dcid:wikidataId/Q...` (Indian states/territories)
- `observationDate`: Date values like `2005-03`
- `variableMeasured`: Contains DCID for the statistical variable `dcid:Nominal_Amount_EconomicActivity_NetValueAdded_Construction`
- `value`: Numeric values
- `unit`: INR (Indian Rupees)
- `measurementMethod`: ConstantPrice_WithBaseYear2004_05
- `observationPeriod`: P1Y (1 year)

**Key Issues:**
1. The `observationAbout` values have `dcid:` prefix which needs to be stripped
2. The `variableMeasured` column should NOT be mapped (per instructions) - instead we need to decompose it into StatVar properties
3. The variable represents: Net Value Added in Construction sector at constant prices

**Data Pattern:** This is Pattern A (Flat Data) - one observation per row.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
observationAbout,#Regex,"^dcid:(?P<DCID>.+)$",observationAbout,{DCID}
observationDate,observationDate,{Data}
value,value,{Number},populationType,EconomicActivity,measuredProperty,netValueAdded,statType,measuredValue
unit,unit,{Data}
measurementMethod,measurementMethod,{Data}
observationPeriod,observationPeriod,{Data}
```

**Notes:**
- The `variableMeasured` column is intentionally not mapped - the processor will auto-construct it from the StatVar properties
- Used `#Regex` to strip the `dcid:` prefix from `observationAbout` values
- Decomposed the statistical variable into: `populationType=EconomicActivity`, `measuredProperty=netValueAdded`, `statType=measuredValue`
- The constraint property `economicActivity=Construction` would normally be needed, but since all rows are for Construction, it may be implicit in the dataset context
- All other columns (unit, measurementMethod, observationPeriod) are passed through directly

```

## Diff Excerpt

```diff
+ 
- populationType: dcid:EconomicActivity
- measuredProperty: dcid:amount
- Product: "Gross domestic product"
- activitySource: dcid:GrossDomesticProduction
- unit: dcid:INR


+ 
- Sector: "in Construction Sector"
- economicSector: dcid:Construction


+ 
- observationDate: 2006-03
- observationPeriod: dcid:P1Y
- value: {Number}


- 
+ observationDate: {Data}


+ 
- observationDate: 2022-03
- observationPeriod: dcid:P1Y
- value: {Number}


- Base: dcid:BaseYear2011_12
+ 


+ 
- observationDate: 2028-03
- observationPeriod: dcid:P1Y
- value: {Number}


+ 
- observationDate: 2019-03
- observationPeriod: dcid:P1Y
- value: {Number}


+ 
- name: "Amount of Economic Activity {Price}: Net Domestic Production"
- populationType: dcid:EconomicActivity
- measuredProperty: dcid:amount
- activitySource: dcid:NetDomesticProduction

```

## Generation Logs

- `logs/india_rbistatedomesticproduct/generation_20260116_131301.log`
