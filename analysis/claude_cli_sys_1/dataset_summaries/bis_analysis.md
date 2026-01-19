# bis - Analysis

**Generated**: 2026-01-19T13:36:09.863506

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 28.6% | 🟠 Needs Work |
| Node Coverage | 57.1% | - |
| PV Accuracy | 25.0% | 🟠 Needs Work |
| Precision | 22.2% | - |
| Recall | 25.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 7 |
| Nodes Auto-Generated | 9 |
| Nodes Matched | 2 |
| Nodes With Diff | 2 |
| Nodes Missing (LLM missed) | 4 |
| Nodes Extra (LLM added) | 5 |
| PVs Matched | 3 |
| PVs Modified | 1 |
| PVs Deleted | 8 |
| PVs Added | 14 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - measurementQualifier: 2
  - observationPeriod: 2
  - populationType: 1
  - instrumentType: 1
  - measuredProperty: 1
  - unit: 1

### Properties Added (Extra in LLM output)
  - measurementQualifier: 2
  - observationPeriod: 2
  - populationType: 1
  - statType: 1
  - measuredProperty: 1
  - property5: 1
  - property1: 1
  - property2: 1
  - property4: 1
  - property3: 1
  - unit: 1
  - observationStatus: 1

### Properties Modified (Different values)
  - observationAbout: 1

## Generation Notes

```markdown
# BIS Central Bank Policy Rates - PV Map Generation Notes

## Dataset Overview

**Source:** BIS (Bank for International Settlements)
**Dataset:** Central Bank Policy Rates (SDMX format)
**DC Topic:** Economy
**Rows in Sample:** 30

---

## Input Files Used

1. **Prompt Template:** `tools/improved_pvmap_prompt.txt`
2. **Schema Examples:** `input/bis/scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt`
3. **Sampled Data:** `input/bis/sampled_data.csv`
4. **Metadata Config:** `input/bis/central_bank_policy_rate_metadata.csv`

---

## Data Structure Analysis

### Column Identification

The BIS data uses SDMX (Statistical Data and Metadata eXchange) format with the following columns:

| Column | Header | Sample Values | Purpose |
|--------|--------|---------------|---------|
| 1 | STRUCTURE | dataflow | Constant - SDMX structure type |
| 2 | STRUCTURE_ID | BIS:WS_CBPOL(1.0): Central bank policy rates | Constant - Dataset identifier |
| 3 | ACTION | I | Constant - Insert action |
| 4 | FREQ:Frequency | M: Monthly, D: Daily | Measurement frequency |
| 5 | REF_AREA:Reference area | AR: Argentina, GB: United Kingdom | Country (ISO 2-letter code) |
| 6 | TIME_PERIOD:Time period or range | 1993-04, 2009-09-08 | Observation date |
| 7 | OBS_VALUE:Observation Value | 0.63, 0.5 | Policy rate value |
| 8 | UNIT_MEASURE:Unit of measure | 368: Per cent per year | Unit (always percent per year) |
| 9 | UNIT_MULT:Unit Multiplier | 0: Units | Multiplier (always units) |
| 10 | TIME_FORMAT:Time Format | (empty) | Not used |
| 11 | COMPILATION:Compilation | (long text) | Methodology notes |
| 12 | DECIMALS:Decimals | 4: Four | Decimal precision |
| 13 | SOURCE_REF:Publication Source | Central Bank of Argentina | Data source |
| 14 | SUPP_INFO_BREAKS | (text) | Supplementary info |
| 15 | TITLE:Title | Central bank policy rates - Argentina - Monthly | Full title |
| 16 | OBS_STATUS:Observation Status | A: Normal value | Data quality status |
| 17 | OBS_CONF:Observation confidentiality | F: Free | Confidentiality |
| 18 | OBS_PRE_BREAK | (empty) | Pre-break values |

### Metadata Configuration

From `central_bank_policy_rate_metadata.csv`:
- **header_rows:** 1
- **output_columns:** `observationAbout,observationDate,variableMeasured,value,unit,observationPeriod`

---

## Mapping Decisions

### 1. Geographic Entity (observationAbout)

**Column:** `REF_AREA:Reference area`
**Format:** `XX: Country Name` (e.g., "AR: Argentina", "GB: United Kingdom")

**Decision:** Use regex to extract ISO 2-letter country code and map to Data Commons country DCID.

```csv
REF_AREA:Reference area,#Regex,"(?P<CountryCode>[A-Z]+): (?P<CountryName>.*)",observationAbout,country/{CountryCode}
```

**Reasoning:**
- Data Commons uses `country/XX` format for country DCIDs
- ISO 2-letter codes (AR, GB, etc.) are standard and map directly
- Using regex to extract just the code portion before the colon

### 2. Temporal Information (observationDate)

**Column:** `TIME_PERIOD:Time period or r...
```

## Diff Excerpt

```diff
+ populationType: dcid:CentralBank
+ measuredProperty: dcid:interestRate
+ statType: dcid:measuredValue
  value: {Number}


- 
+ property1: dcid:value1
+ property2: dcid:value2
+ property3: dcid:value3
+ property4: dcid:value4
+ property5: dcid:value5


- 
+ unit: dcid:PercentPerAnnum


  observationDate: {Data}


- 
+ observationStatus: dcid:NormalValue


+ 
- measurementQualifier: dcid:Daily
- observationPeriod: dcid:P1D


  


- observationAbout: {Data}
+ observationAbout: dcid:country/{CountryCode}


+ 
- populationType: dcid:FinancialInstrument
- measuredProperty: dcid:interestRate
- instrumentType: dcid:CountryCentralBankPolicyRate


- 
+ measurementQualifier: dcid:Daily
+ observationPeriod: dcid:P1D


- 
+ measurementQualifier: dcid:Monthly

```

## Generation Logs

No generation logs found.
