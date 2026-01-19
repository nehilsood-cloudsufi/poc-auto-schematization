# fao_currency_and_exchange_rate - Analysis

**Generated**: 2026-01-19T13:36:09.884717

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.7% | - |
| PV Accuracy | 0.5% | 🔴 Poor |
| Precision | 23.1% | - |
| Recall | 0.5% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 313 |
| Nodes Auto-Generated | 313 |
| Nodes Matched | 0 |
| Nodes With Diff | 312 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 3 |
| PVs Modified | 0 |
| PVs Deleted | 612 |
| PVs Added | 10 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - CurrencyCode: 286
  - CurrencyName: 286
  - observationPeriod: 13
  - Month: 12
  - measurementQualifier: 2
  - CurrencyType: 2
  - Var1: 1
  - populationType: 1
  - measuredProperty: 1
  - fromCurrency: 1
  - observationAbout: 1
  - p1: 1
  - observationDate: 1
  - value: 1
  - name: 1
  - toCurrency: 1
  - unit: 1

### Properties Added (Extra in LLM output)
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - value: 1
  - observationPeriod: 1
  - p5: 1
  - prop: 1
  - unit: 1
  - observationDate: 1
  - observationAbout: 1

## Generation Notes

```markdown
# fao_currency_and_exchange_rate - PVMAP Generation Notes

Generated: 2026-01-16T13:09:25.329679

Total attempts: 1

---

Looking at this input data, I notice it's **already in Data Commons format** - it has `observationAbout`, `observationDate`, `value`, `variableMeasured`, `observationPeriod`, and `unit` as column headers with proper DCIDs and values.

However, there are issues with this data structure:

1. **`variableMeasured` is already populated** - The processor auto-constructs this from StatVar properties, so having it as an input column will conflict
2. **The data contains `dcid:` prefixes** - These need to be stripped
3. **Missing StatVar decomposition** - Since `variableMeasured` is pre-populated, we need to extract the StatVar properties from it or define them

Since the processor needs to **construct** `variableMeasured` (not consume it), I'll create a PVMAP that:
- Strips the `dcid:` prefixes from `observationAbout` and ignores the pre-filled `variableMeasured` column
- Extracts StatVar properties from the variable name pattern
- Maps the already-correct observation properties

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5
observationAbout,#Regex,"^dcid:(?P<Place>.+)$",observationAbout,{Place}
observationDate,observationDate,{Data}
observationPeriod,observationPeriod,{Data}
unit,unit,{Data}
value,value,{Number},populationType,Currency,measuredProperty,exchangeRate,statType,measuredValue
```

**CRITICAL LIMITATION**: The input data has `variableMeasured` already populated with detailed constraint information (FromCurrency_USD, ToCurrency_AFA, etc.) that cannot be easily parsed into individual constraint properties. The PVMAP above provides a **generic** exchange rate StatVar. 

If you need to preserve the currency pair constraints (fromCurrency, toCurrency), you would need to either:
1. Preprocess the data to extract these into separate columns
2. Use complex #Regex patterns on the `variableMeasured` column (unreliable for this complexity)

The `variableMeasured` column will be **ignored** by this PVMAP and reconstructed by the processor based on the StatVar properties provided.

```

## Diff Excerpt

```diff
+ 
- CurrencyCode: dcid:DJF
- CurrencyName: "Djibouti Franc"


+ 
- CurrencyCode: dcid:XSS
- CurrencyName: "Shilling Sterling (historical)"


+ 
- CurrencyCode: dcid:LYD
- CurrencyName: "Libyan Dinar"


+ 
- CurrencyCode: dcid:FRF
- CurrencyName: "French Franc"


+ 
- CurrencyCode: dcid:CUX
- CurrencyName: "Cuban Foreign Exchange Certificates (historical)"


+ 
- CurrencyCode: dcid:BGL
- CurrencyName: "Lev (historical)"


+ 
- CurrencyCode: dcid:ISK
- CurrencyName: "Iceland Krona"


+ 
- CurrencyCode: dcid:CRC
- CurrencyName: "Costa Rican Colon"


+ 
- CurrencyCode: dcid:SRD
- CurrencyName: "Surinam Dollar"


+ 
- CurrencyCode: dcid:NIO
- CurrencyName: "Cordoba Oro"



```

## Generation Logs

- `logs/fao_currency_and_exchange_rate/generation_20260116_130102.log`
- `logs/fao_currency_and_exchange_rate/generation_20260116_130910.log`
