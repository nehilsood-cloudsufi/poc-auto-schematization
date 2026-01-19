# brfss_nchs_asthma_prevalence - Analysis

**Generated**: 2026-01-19T13:36:09.869972

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 98.9% | - |
| PV Accuracy | 7.9% | 🔴 Poor |
| Precision | 7.6% | - |
| Recall | 7.9% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 88 |
| Nodes Auto-Generated | 88 |
| Nodes Matched | 0 |
| Nodes With Diff | 87 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 5 |
| PVs Modified | 0 |
| PVs Deleted | 58 |
| PVs Added | 61 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - race: 18
  - ethnicity: 13
  - measuredProperty: 6
  - statType: 5
  - value: 5
  - unit: 3
  - age: 1
  - p1: 1
  - p6: 1
  - populationType: 1
  - healthOutcome: 1
  - observationAbout: 1
  - measurementDenominator: 1
  - scalingFactor: 1

### Properties Added (Extra in LLM output)
  - observationAbout: 52
  - income: 5
  - populationType: 1
  - measuredProperty: 1
  - medicalCondition: 1
  - prop: 1

## Generation Notes

```markdown
# brfss_nchs_asthma_prevalence - PVMAP Generation Notes

Generated: 2026-01-16T12:17:46.476730

Total attempts: 1

---

Looking at this BRFSS asthma data, I can see:

**Data Pattern**: This is **Pattern A (Flat Data)** - each row is a complete observation with columns for place, income level, prevalence percentage, year, and life stage.

**Key Observations**:
1. Place column "State" contains state abbreviations (AL, etc.) and "U.S. Totalf" (with footer marker)
2. Income levels are the constraint categories with special characters (commas, dollar signs)
3. "Prevalence (Percent)" is the value column
4. Year and life_stage are temporal/demographic attributes
5. Data contains footnote markers (superscript 'f' in "U.S. Totalf")

**Limitations**:
- The "U.S. Totalf" value has a footnote marker - mapping to `country/USA`
- State abbreviations need to be mapped to geoIds (I'll provide common examples, but you may need to complete the list)
- Income range keys contain commas and special characters - **must be quoted**
- Columns like "Sample Sizec", "Standard Error", "95% CId" are not being mapped (only prevalence)
- The "|| ||" column appears to be a separator and will be ignored

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5
year,observationDate,{Data}
State:U.S. Totalf,observationAbout,country/USA
State:AL,observationAbout,geoId/01
State:AK,observationAbout,geoId/02
State:AZ,observationAbout,geoId/04
State:AR,observationAbout,geoId/05
State:CA,observationAbout,geoId/06
State:CO,observationAbout,geoId/08
State:CT,observationAbout,geoId/09
State:DE,observationAbout,geoId/10
State:DC,observationAbout,geoId/11
State:FL,observationAbout,geoId/12
State:GA,observationAbout,geoId/13
State:HI,observationAbout,geoId/15
State:ID,observationAbout,geoId/16
State:IL,observationAbout,geoId/17
State:IN,observationAbout,geoId/18
State:IA,observationAbout,geoId/19
State:KS,observationAbout,geoId/20
State:KY,observationAbout,geoId/21
State:LA,observationAbout,geoId/22
State:ME,observationAbout,geoId/23
State:MD,observationAbout,geoId/24
State:MA,observationAbout,geoId/25
State:MI,observationAbout,geoId/26
State:MN,observationAbout,geoId/27
State:MS,observationAbout,geoId/28
State:MO,observationAbout,geoId/29
State:MT,observationAbout,geoId/30
State:NE,observationAbout,geoId/31
State:NV,observationAbout,geoId/32
State:NH,observationAbout,geoId/33
State:NJ,observationAbout,geoId/34
State:NM,observationAbout,geoId/35
State:NY,observationAbout,geoId/36
State:NC,observationAbout,geoId/37
State:ND,observationAbout,geoId/38
State:OH,observationAbout,geoId/39
State:OK,observationAbout,geoId/40
State:OR,observationAbout,geoId/41
State:PA,observationAbout,geoId/42
State:RI,observationAbout,geoId/44
State:SC,observationAbout,geoId/45
State:SD,observationAbout,geoId/46
State:TN,observationAbout,geoId/47
State:TX,observationAbout,geoId/48
State:UT,observationAbout,geoId/49
State:VT,observationAbout,geoId/50
State:VA,observationAbout,geoId/51
State:WA,observationAbout,geoId/53
State:WV...
```

## Diff Excerpt

```diff
- 
+ observationAbout: dcid:geoId/28


- 
+ income: dcid:USDollar_75000Onwards


+ 
- ethnicity: dcid:NotHispanicOrLatino
- race: dcid:WhiteAlone


+ 
- measuredProperty: dcid:percent
- statType: dcid:measuredValue
- unit: dcid:Percent
- value: {Number}


- race: dcid:TwoOrMoreRaces
+ 


- 
+ observationAbout: dcid:geoId/26


- 
+ observationAbout: dcid:geoId/36


+ 
- ethnicity: dcid:NotHispanicOrLatino
- race: dcid:BlackOrAfricanAmericanAlone


- 
+ observationAbout: dcid:geoId/23


+ 
- ethnicity: dcid:NotHispanicOrLatino
- race: dcid:CDC_OtherRace


+ populationType: dcid:Person
- measuredProperty: dcid:percent
?                        --- ^


```

## Generation Logs

- `logs/brfss_nchs_asthma_prevalence/generation_20260116_121720.log`
