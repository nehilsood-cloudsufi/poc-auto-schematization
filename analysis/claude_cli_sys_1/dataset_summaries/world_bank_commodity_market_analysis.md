# world_bank_commodity_market - Analysis

**Generated**: 2026-01-19T13:36:09.951375

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 76.6% | - |
| PV Accuracy | 48.8% | 🟢 Good |
| Precision | 22.9% | - |
| Recall | 48.8% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 94 |
| Nodes Auto-Generated | 74 |
| Nodes Matched | 0 |
| Nodes With Diff | 72 |
| Nodes Missing (LLM missed) | 22 |
| Nodes Extra (LLM added) | 2 |
| PVs Matched | 106 |
| PVs Modified | 42 |
| PVs Deleted | 69 |
| PVs Added | 499 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - geographicalIndicator: 27
  - Month: 12
  - observationDate: 12
  - unit: 8
  - p1: 1
  - p7: 1
  - measurementMethod: 1
  - statType: 1
  - measuredProperty: 1
  - populationType: 1
  - observationAbout: 1
  - Year: 1
  - observationPeriod: 1
  - measurementQualifier: 1

### Properties Added (Extra in LLM output)
  - observationDate: 71
  - populationType: 71
  - observationAbout: 71
  - observationPeriod: 71
  - unit: 71
  - statType: 71
  - measuredProperty: 70
  - prop: 1
  - Month: 1
  - Year: 1

### Properties Modified (Different values)
  - commodityType: 41
  - measuredProperty: 1

## Generation Notes

```markdown
# world_bank_commodity_market - PVMAP Generation Notes

Generated: 2026-01-13T21:20:37.264000

Total attempts: 2

---

Looking at the error logs, I can see the main issue: all observations are being dropped because `observationAbout` is set to "Earth" but the processor cannot resolve it as a valid place DCID.

The problem is that for global commodity prices, we should use `observationAbout,dcid:Earth` instead of just `observationAbout,Earth`.

Here's the corrected PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
Year,Year,{Number}
Month,#Regex,"M(?P<Mon>[0-9]+)",Month,{Mon}
"Crude oil, average",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,CrudeOil,unit,USDollarPerBarrel,observationPeriod,P1M
"Crude oil, Brent",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,CrudeOil_Brent,unit,USDollarPerBarrel,observationPeriod,P1M
"Crude oil, Dubai",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,CrudeOil_Dubai,unit,USDollarPerBarrel,observationPeriod,P1M
"Crude oil, WTI",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,CrudeOil_WTI,unit,USDollarPerBarrel,observationPeriod,P1M
"Coal, Australian",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,Coal_Australian,unit,USDollarPerMetricTon,observationPeriod,P1M
"Coal, South African **",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,Coal_SouthAfrican,unit,USDollarPerMetricTon,observationPeriod,P1M
"Natural gas, US",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,NaturalGas_US,unit,USDollarPerMmbtu,observationPeriod,P1M
"Natural gas, Europe",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,NaturalGas_Europe,unit,USDollarPerMmbtu,observationPeriod,P1M
"Liquefied natural gas, Japan",observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,LiquefiedNaturalGas_Japan,unit,USDollarPerMmbtu,observationPeriod,P1M
Natural gas index,observationDate,{Year}-{Month},observationAbout,dcid:Earth,value,{Number},populationType,Commodity,measuredProperty,price,statType,measuredValue,commodityType,NaturalGas,unit,Index,observationPeriod,P1M
Cocoa,observa...
```

## Diff Excerpt

```diff
+ populationType: dcid:Commodity
+ measuredProperty: dcid:price
+ statType: dcid:measuredValue
- commodityType: dcid:Broilers
?                     ^^^ ^ ^^

+ commodityType: dcid:Chicken
?                     ^^ ^^ ^

+ observationAbout: dcid:Earth
+ observationDate: {Year}-{Month}
+ observationPeriod: dcid:P1M
+ unit: dcid:USDollarPerKilogram
  value: {Number}


+ 
- Month: 2
- observationDate: {Year}-{Month}


+ populationType: dcid:Commodity
+ measuredProperty: dcid:price
+ statType: dcid:measuredValue
- commodityType: dcid:CottonAIndex
?                           ------

+ commodityType: dcid:Cotton
+ observationAbout: dcid:Earth
+ observationDate: {Year}-{Month}
+ observationPeriod: dcid:P1M
+ unit: dcid:USDollarPerKilogram
  value: {Number}


+ populationType: dcid:Commodity
+ measuredProperty: dcid:price
+ statType: dcid:measuredValue
  commodityType: dcid:Urea
+ observationAbout: dcid:Earth
+ observationDate: {Year}-{Month}
+ observationPeriod: dcid:P1M
+ unit: dcid:USDollarPerMetricTon
  value: {Number}


+ populationType: dcid:Commodity
+ measuredProperty: dcid:price
+ statType: dcid:measuredValue
  commodityType: dcid:Nickel

```

## Generation Logs

- `logs/world_bank_commodity_market/generation_20260113_211826.log`
