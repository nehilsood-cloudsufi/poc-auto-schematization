# bis_bis_central_bank_policy_rate - Analysis

**Generated**: 2026-01-14T14:56:48.858566

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 228.6% | 🟢 Excellent |
| Node Coverage | 285.7% | - |
| PV Accuracy | 73.1% | 🟢 Excellent |
| Precision | 61.3% | - |
| Recall | 73.1% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 7 |
| Nodes Auto-Generated | 23 |
| Nodes Matched | 16 |
| Nodes With Diff | 4 |
| Nodes Missing (LLM missed) | 2 |
| Nodes Extra (LLM added) | 3 |
| PVs Matched | 19 |
| PVs Modified | 0 |
| PVs Deleted | 7 |
| PVs Added | 12 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - measurementQualifier: 2
  - unit: 1
  - observationAbout: 1
  - measuredProperty: 1
  - instrumentType: 1
  - populationType: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 2
  - CountryCode: 1
  - p2: 1
  - p6: 1
  - prop: 1
  - p5: 1
  - p3: 1
  - p4: 1
  - measuredProperty: 1
  - populationType: 1

### Properties Modified (Different values)
  None

## Generation Notes

```markdown
# bis_bis_central_bank_policy_rate - PVMAP Generation Notes

Generated: 2026-01-13T21:15:33.588808

Total attempts: 3

---

Looking at the errors, the main issue is that `observationAbout` is not being set properly. The processor is warning "No place in SVObs" for every observation.

The problem is that I'm extracting the country code correctly but then trying to use `country/{Code}` which requires the Data Commons country DCID format. Let me fix this by properly mapping the country codes to their DCIDs.

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
STRUCTURE,#ignore,skip
ACTION,#ignore,skip
STRUCTURE_ID,#ignore,skip
UNIT_MULT:Unit Multiplier,#ignore,skip
TIME_FORMAT:Time Format,#ignore,skip
COMPILATION:Compilation,#ignore,skip
DECIMALS:Decimals,#ignore,skip
SOURCE_REF:Publication Source,#ignore,skip
SUPP_INFO_BREAKS:Supplemental information and breaks,#ignore,skip
TITLE:Title,#ignore,skip
OBS_STATUS:Observation Status,#ignore,skip
OBS_CONF:Observation confidentiality,#ignore,skip
OBS_PRE_BREAK:Pre-Break Observation,#ignore,skip
FREQ:Frequency,#Regex,"^(?P<FreqCode>[A-Z]+):.*"
M: Monthly,observationPeriod,P1M
D: Daily,observationPeriod,P1D
REF_AREA:Reference area,#Regex,"^(?P<Code>[A-Z]+):.*",CountryCode,{Code}
TIME_PERIOD:Time period or range,observationDate,{Data}
OBS_VALUE:Observation Value,value,{Number},populationType,FinancialInstrument,measuredProperty,interestRate,statType,measuredValue
CountryCode:AR,observationAbout,country/ARG
CountryCode:GB,observationAbout,country/GBR
UNIT_MEASURE:Unit of measure,#ignore,skip
```

```

## Diff Excerpt

```diff
- unit: dcid:PercentPerAnnum
+ 


  


  


- observationAbout: {Data}
+ CountryCode: {Code}


  


  


  observationDate: {Data}


- 
+ p2: dcid:v2
+ p3: dcid:v3
+ p4: dcid:v4
+ p5: dcid:v5
+ p6: dcid:v6
+ prop: dcid:value

```

## Generation Logs

- `logs/bis_bis_central_bank_policy_rate/generation_20260113_211446.log`
