# crdc_import_crdc_harassment_or_bullying - Analysis

**Generated**: 2026-01-19T13:36:09.879733

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.7% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 391 |
| Nodes Auto-Generated | 391 |
| Nodes Matched | 0 |
| Nodes With Diff | 390 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 2033 |
| PVs Added | 8 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - biasMotivation: 375
  - value: 375
  - crimeType: 189
  - disciplinaryAction: 186
  - gender: 186
  - targetedGender: 186
  - victimType: 186
  - offenderRace: 114
  - targetedRace: 114
  - disabilityStatus: 72
  - abilityToSpeakEnglish: 36
  - GLOBAL: 8
  - allegation: 3
  - observationDate: 1
  - populationType: 1
  - measuredProperty: 1

### Properties Added (Extra in LLM output)
  - observationDate: 1
  - variableMeasured: 1
  - value: 1
  - p2: 1
  - p3: 1
  - p4: 1
  - property: 1
  - observationAbout: 1

## Generation Notes

```markdown
# crdc_import_crdc_harassment_or_bullying - PVMAP Generation Notes

Generated: 2026-01-16T14:16:41.700827

Total attempts: 1

---

```csv
key,property,value,p2,v2,p3,v3,p4,v4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,variableMeasured,{Data}
```

---

## Analysis

This dataset is **already in Data Commons format** - it contains pre-constructed DCIDs in the `variableMeasured` column (e.g., `dcid:Count_Student_BiasMotivationGender_HarassmentOrBullying`). The data structure is:

- **observationAbout**: NCES school identifiers (e.g., `nces/010000201705`)
- **observationDate**: Year (e.g., `2021`)
- **value**: Numeric count (`0` in all sampled rows)
- **variableMeasured**: Complete StatVar DCIDs with all constraints already encoded

### Key Observations

1. **No StatVar construction needed**: The `variableMeasured` column already contains fully-qualified DCIDs with all properties and constraints (gender, race, bias motivation, victim type, offender characteristics) embedded in the DCID string.

2. **Pass-through mapping**: The PV map simply passes through all four columns as-is using `{Data}` placeholders.

3. **Data pattern**: This appears to be Civil Rights Data Collection (CRDC) harassment/bullying data with:
   - Population type: Student
   - Measured property: count
   - Stat type: measuredValue
   - Constraints encoded in DCID: gender (Male/Female), race/ethnicity, bias motivation (Gender/Disability), English proficiency, disability services, victim/offender characteristics

### Limitations

- All sampled values are `0` - cannot verify if numeric extraction works correctly for non-zero values
- NCES school identifiers assumed valid (format: `nces/[12-digit ID]`)
- No schema validation possible for the 90+ unique variableMeasured DCIDs in this dataset

```

## Diff Excerpt

```diff
+ 
- biasMotivation: dcid:Gender
- crimeType: dcid:HarassmentOrBullying
- disciplinaryAction: dcid:SuspendedOrExpelled
- gender: dcid:Female
- offenderRace: dcid:White
- value: {Number}


+ 
- biasMotivation: dcid:Gender
- targetedGender: dcid:Female
- targetedRace: dcid:Asian
- value: {Number}
- victimType: dcid:HarassedOrBullied


+ 
- biasMotivation: dcid:GenderOrRaceOrNationalOrigin
- disabilityStatus: dcid:DisabilityServedUnderDisabilitiesEducationAct
- targetedGender: dcid:Female
- value: {Number}
- victimType: dcid:HarassedOrBullied


+ 
- abilityToSpeakEnglish: dcid:LimitedEnglishProficiency
- biasMotivation: dcid:Gender
- targetedGender: dcid:Female
- value: {Number}
- victimType: dcid:HarassedOrBullied


+ 
- biasMotivation: dcid:Disability
- targetedGender: dcid:Female
- targetedRace: dcid:White
- value: {Number}
- victimType: dcid:HarassedOrBullied


+ 
- allegation: dcid:Alleged
- biasMotivation: dcid:Gender
- crimeType: dcid:HarassmentOrBullying
- value: {Number}


+ 
- abilityToSpeakEnglish: dcid:LimitedEnglishProficiency

```

## Generation Logs

- `logs/crdc_import_crdc_harassment_or_bullying/generation_20260116_141627.log`
