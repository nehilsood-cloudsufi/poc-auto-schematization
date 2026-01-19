# google_sustainability_financial_incentives - Analysis

**Generated**: 2026-01-19T13:36:09.890600

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.7% | - |
| PV Accuracy | 0.4% | 🔴 Poor |
| Precision | 3.1% | - |
| Recall | 0.4% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 290 |
| Nodes Auto-Generated | 290 |
| Nodes Matched | 0 |
| Nodes With Diff | 289 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 1 |
| PVs Modified | 0 |
| PVs Deleted | 281 |
| PVs Added | 31 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - CountryName: 254
  - Currency: 3
  - incentiveCategory: 2
  - populationType: 1
  - measuredProperty: 1
  - incentiveCategoryStr: 1
  - observationDate: 1
  - value: 1
  - PurchaseType: 1
  - Provider: 1
  - provider: 1
  - Url: 1
  - url: 1
  - incentiveAmount: 1
  - UrlStableHash: 1
  - IncentiveType: 1
  - IncentiveAmount1: 1
  - location: 1
  - observationAbout: 1
  - typeOf: 1
  - IncentiveName: 1
  - incentiveName: 1
  - AdminArea1: 1
  - CountrtyName: 1
  - CountryCode: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 5
  - populationType: 3
  - measuredProperty: 3
  - statType: 3
  - unit: 2
  - incentiveAmount: 2
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1
  - p6: 1
  - p7: 1
  - purchaseType: 1
  - provider: 1
  - incentiveAmount1: 1
  - url: 1
  - incentiveType: 1
  - incentiveCategoryStr: 1
  - incentiveName: 1

## Generation Notes

```markdown
# google_sustainability_financial_incentives - PVMAP Generation Notes

Generated: 2026-01-16T14:26:26.319521

Total attempts: 1

---

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
extractionConfig.locale.countryIso,observationAbout,country/{Data}
extractionConfig.locale.countryIso:AE,observationAbout,country/ARE
extractionConfig.locale.countryIso:AM,observationAbout,country/ARM
extractionConfig.locale.countryIso:AT,observationAbout,country/AUT
extractionConfig.locale.countryIso:AU,observationAbout,country/AUS
extractionConfig.incentiveCategory,incentiveCategory,{Data}
extractionConfig.incentiveCategory,incentiveCategoryStr,{Data}
incentive.purchaseType,purchaseType,{Data}
extractionConfig.url,url,{Data}
incentive.name,incentiveName,{Data}
incentive.redemptionType,incentiveType,{Data}
incentive.providerName,provider,{Data}
incentive.maximumAmount.units,incentiveAmount,{Number},populationType,SolarIncentive,measuredProperty,amount,statType,measuredValue,unit,{../incentive.maximumAmount.currencyCode}
incentive.perUnitAmount.amount.units,incentiveAmount1,{Number},populationType,SolarIncentive,measuredProperty,amount,statType,measuredValue,unit,{../incentive.perUnitAmount.amount.currencyCode}
incentive.percentageOfCostsCovered,incentiveAmount,{Number},populationType,SolarIncentive,measuredProperty,percentageOfCostsCovered,statType,measuredValue
```

**Notes:**

1. **Place mapping**: Converted ISO-2 country codes (AE, AM, AT, AU) to ISO-3 format required by Data Commons (ARE, ARM, AUT, AUS)

2. **Multi-value handling**: Two amount columns (`incentive.maximumAmount.units` and `incentive.perUnitAmount.amount.units`) both map to StatVar properties with different semantic meanings - one is maximum amount, other is per-unit amount

3. **Currency handling**: Used relative path syntax `{../columnName}` to reference currency code columns for the unit property

4. **Data limitations**:
   - Many rows have empty amount values - these will be auto-skipped by processor
   - Additional metadata columns (locale.adminArea1, perUnitAmount.unit, taxWaiverType, equipmentType) are included in #input passthrough
   - No temporal dimension (observationDate) as data represents current/standing incentive programs
   - The `percentageOfCostsCovered` column uses a different measured property to distinguish it from absolute amounts

5. **Output columns**: Custom schema includes domain-specific properties (purchaseType, incentiveCategory, etc.) that will pass through as-is rather than being transformed into standard StatVarObservation format

```

## Diff Excerpt

```diff
- CountryName: dcid:Mali
+ 


- CountryName: dcid:Romania
+ 


- CountryName: "Cocos (Keeling) Islands"
+ 


- CountryName: dcid:Eswatini
+ 


- CountryName: "French Guiana"
+ 


- CountryName: "Palestinian Territories"
+ 


- CountryName: dcid:Vietnam
+ 


- CountryName: "Christmas Island"
+ 


- CountryName: dcid:Libya
+ 


- CountryName: dcid:Namibia
+ 


- CountryName: dcid:Nepal
+ 


+ p2: dcid:v2
+ p3: dcid:v3
+ p4: dcid:v4
+ p5: dcid:v5
+ p6: dcid:v6
+ p7: dcid:v7

```

## Generation Logs

- `logs/google_sustainability_financial_incentives/generation_20260116_142609.log`
