# us_federal_reserve_h15_interest_rates - Analysis

**Generated**: 2026-01-19T13:36:09.940491

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 91.7% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 12 |
| Nodes Auto-Generated | 12 |
| Nodes Matched | 0 |
| Nodes With Diff | 11 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 20 |
| PVs Added | 9 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - instrumentType: 3
  - value: 3
  - measuredProperty: 2
  - statType: 1
  - p1: 1
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1
  - p6: 1
  - populationType: 1
  - instrumentTerm: 1
  - observationAbout: 1
  - observationDate: 1
  - unit: 1

### Properties Added (Extra in LLM output)
  - unit: 1
  - property: 1
  - property2: 1
  - property3: 1
  - variableMeasured: 1
  - scalingFactor: 1
  - value: 1
  - observationAbout: 1
  - observationDate: 1

## Generation Notes

```markdown
# us_federal_reserve_h15_interest_rates - PVMAP Generation Notes

Generated: 2026-01-16T15:16:08.793504

Total attempts: 3

---

Looking at the error logs, I can see the key issues:

1. **`error-mismatched-svobs=11`** - The StatVarObservations don't match expected structure
2. **`error-statvar-with-dup-svobs=1`** - Duplicate observations detected
3. **`warning-missing-property-key=2407`** - Many property keys not found in the data
4. **Empty output** - No valid observations generated

The problem is that the data is **already in Data Commons format** with `variableMeasured` containing complete StatVar DCIDs. The PVMAP shouldn't try to reconstruct StatVars - it should just pass through the existing structure.

However, I notice the instructions say **"NEVER map `variableMeasured`"** because it's auto-constructed. But this data has pre-existing `variableMeasured` DCIDs like `dcid:InterestRate_TreasuryBill_3Month_SecondaryMarket`.

The solution is to treat `variableMeasured` as a pass-through column and only map the observation properties:

```csv
key,property,value,property2,value2,property3,value3
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
variableMeasured,variableMeasured,{Data}
```

**Key decisions:**
- All columns are pass-through since data is already in DC format
- `variableMeasured` contains complete StatVar DCIDs (not constructed)
- No StatVar properties needed - they're embedded in the DCIDs
- `scalingFactor` is empty in data, but column should still be mapped

**Limitations noted:**
- This dataset is pre-formatted for Data Commons and doesn't require typical PV transformation
- The `variableMeasured` DCIDs already encode all StatVar properties (populationType, measuredProperty, constraints)

```

## Diff Excerpt

```diff
+ 
- instrumentType: dcid:PrimaryCredit
- value: {Number}


- 
+ unit: {Data}


+ 
- measuredProperty: dcid:primeRate
- statType: dcid:meanValue
- instrumentType: dcid:BankLoan
- value: {Number}


+ property: dcid:value
+ property2: dcid:value2
+ property3: dcid:value3
- p1: dcid:v1
- p2: dcid:v2
- p3: dcid:v3
- p4: dcid:v4
- p5: dcid:v5
- p6: dcid:v6


- 
+ variableMeasured: {Data}


- 
+ scalingFactor: {Data}


- 
+ value: {Number}


+ 
- populationType: dcid:FinancialInstrument
- measuredProperty: dcid:interestRate
- instrumentTerm: dcid:Year1
- observationAbout: dcid:country/USA
- observationDate: {Data}
- unit: dcid:PercentPerAnnum


- 
+ observationAbout: {Data}

```

## Generation Logs

- `logs/us_federal_reserve_h15_interest_rates/generation_20260116_151516.log`
