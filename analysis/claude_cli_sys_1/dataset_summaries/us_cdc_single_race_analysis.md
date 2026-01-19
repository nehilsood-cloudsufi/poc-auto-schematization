# us_cdc_single_race - Analysis

**Generated**: 2026-01-19T13:36:09.936145

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 2.0% | - |
| PV Accuracy | 3.0% | 🔴 Poor |
| Precision | 13.9% | - |
| Recall | 3.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 152 |
| Nodes Auto-Generated | 31 |
| Nodes Matched | 0 |
| Nodes With Diff | 3 |
| Nodes Missing (LLM missed) | 149 |
| Nodes Extra (LLM added) | 28 |
| PVs Matched | 5 |
| PVs Modified | 0 |
| PVs Deleted | 162 |
| PVs Added | 31 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - causeOfDeath: 137
  - Unit: 8
  - race: 6
  - gender: 2
  - value: 2
  - observationAbout: 2
  - observationDate: 1
  - observationPeriod: 1
  - p6: 1
  - p1: 1
  - p5: 1

### Properties Added (Extra in LLM output)
  - causeOfDeath: 19
  - race: 6
  - gender: 2
  - observationDate: 1
  - statType: 1
  - measuredProperty: 1
  - prop: 1

## Generation Notes

```markdown
# us_cdc_single_race - PVMAP Generation Notes

Generated: 2026-01-14T00:14:14.385232

Total attempts: 3

---

Looking at the errors, the main issue is that `#Format` on the `County Code` column is not being applied correctly. The processor expects `#Format` to set the `observationAbout` property directly, not as a transformation expression.

Additionally, I notice:
1. The data has complex ICD-10 codes in parentheses that need careful regex handling
2. Footer rows will cause parsing issues and should be noted
3. "Unreliable" values in numeric columns will be skipped (expected behavior)

Here's the corrected PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
Year,observationDate,{Data}
County Code,#Format,observationAbout=geoId/{Number:05d}
Sex:Female,gender,Female
Sex:Male,gender,Male
Single Race 6:American Indian or Alaska Native,race,AmericanIndianOrAlaskaNativeAlone
Single Race 6:Asian,race,AsianAlone
Single Race 6:Black or African American,race,BlackOrAfricanAmericanAlone
Single Race 6:White,race,WhiteAlone
Single Race 6:Native Hawaiian or Other Pacific Islander,race,NativeHawaiianOrOtherPacificIslanderAlone
Single Race 6:More than one race,race,TwoOrMoreRaces
"ICD-10 113 Cause List:#Malignant neoplasms (C00-C97)",#Regex,"^\#?(?P<desc>.*) \((?P<codes>[^)]+)\)$",causeOfDeath,ICD10/{codes}
"ICD-10 113 Cause List:Major cardiovascular diseases (I00-I78)",causeOfDeath,ICD10/I00-I78
"ICD-10 113 Cause List:#Diseases of heart (I00-I09,I11,I13,I20-I51)",causeOfDeath,ICD10/I00-I51
"ICD-10 113 Cause List:All other diseases (Residual)",causeOfDeath,AllOtherDiseasesResidual
"ICD-10 113 Cause List:#Accidents (unintentional injuries) (V01-X59,Y85-Y86)",causeOfDeath,ICD10/V01-X59_Y85-Y86
"ICD-10 113 Cause List:Nontransport accidents (W00-X59,Y86)",causeOfDeath,ICD10/W00-X59_Y86
"ICD-10 113 Cause List:#Septicemia (A40-A41)",causeOfDeath,ICD10/A40-A41
"ICD-10 113 Cause List:Malignant neoplasms of colon, rectum and anus (C18-C21)",causeOfDeath,ICD10/C18-C21
"ICD-10 113 Cause List:Malignant neoplasms of trachea, bronchus and lung (C33-C34)",causeOfDeath,ICD10/C33-C34
"ICD-10 113 Cause List:Malignant neoplasm of breast (C50)",causeOfDeath,ICD10/C50
"ICD-10 113 Cause List:Malignant neoplasms of lymphoid, hematopoietic and related tissue (C81-C96)",causeOfDeath,ICD10/C81-C96
"ICD-10 113 Cause List:All other and unspecified malignant neoplasms (C17,C23-C24,C26-C31,C37-C41,C44-C49,C51-C52,C57-C60,C62-C63,C66,C68-C69,C73-C80,C97)",causeOfDeath,ICD10/C17_C23-C97
"ICD-10 113 Cause List:#Diabetes mellitus (E10-E14)",causeOfDeath,ICD10/E10-E14
"ICD-10 113 Cause List:#Alzheimer disease (G30)",causeOfDeath,ICD10/G30
"ICD-10 113 Cause List:Ischemic heart diseases (I20-I25)",causeOfDeath,ICD10/I20-I25
"ICD-10 113 Cause List:Other forms of chronic ischemic heart disease (I20,I25)",causeOfDeath,ICD10/I20_I25
"ICD-10 113 Cause List:Atherosclerotic cardiovascular disease, so described (I25.0)",causeOfDeath,ICD10/I25.0
"ICD-10 113 Cause List:All other forms of chronic ischemic heart d...
```

## Diff Excerpt

```diff
+ 
- Unit: dcid:Per100000Persons
- race: dcid:White


- causeOfDeath: dcid:Asthma
+ 


- causeOfDeath: dcid:AlzheimersDisease
+ 


- causeOfDeath: dcid:Meningitis
+ 


- causeOfDeath: dcid:InfectionsOfKidney
+ 


- causeOfDeath: dcid:AcuteRheumaticFeverAndChronicRheumaticHeartDiseases
+ 


- causeOfDeath: dcid:OtherAndUnspecifiedNontransportAccidentsAndTheirSequelae
+ 


- causeOfDeath: dcid:Leukemia
+ 


- 
+ race: dcid:TwoOrMoreRaces


- causeOfDeath: dcid:ViralHepatitis
+ 


+ 
- Unit: dcid:Per100000Persons
- race: dcid:TwoOrMoreRaces


- causeOfDeath: dcid:MalignantNeoplasmsOfCorpusUteriAndUterus_PartUnspecified
+ 



```

## Generation Logs

- `logs/us_cdc_single_race/generation_20260114_000133.log`
- `logs/us_cdc_single_race/generation_20260114_000726.log`
- `logs/us_cdc_single_race/generation_20260114_001245.log`
