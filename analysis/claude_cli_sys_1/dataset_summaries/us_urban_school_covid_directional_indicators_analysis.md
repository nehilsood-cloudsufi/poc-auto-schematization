# us_urban_school_covid_directional_indicators - Analysis

**Generated**: 2026-01-19T13:36:09.945717

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 33.3% | - |
| PV Accuracy | 7.1% | 🔴 Poor |
| Precision | 6.7% | - |
| Recall | 7.1% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 6 |
| Nodes Auto-Generated | 7 |
| Nodes Matched | 0 |
| Nodes With Diff | 2 |
| Nodes Missing (LLM missed) | 4 |
| Nodes Extra (LLM added) | 5 |
| PVs Matched | 1 |
| PVs Modified | 0 |
| PVs Deleted | 13 |
| PVs Added | 14 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - instructionMode: 4
  - value: 4
  - statType: 1
  - populationType: 1
  - medicalCondition: 1
  - measuredProperty: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - juvenileJusticeFacility: 2
  - statType: 1
  - populationType: 1
  - value: 1
  - measuredProperty: 1
  - observationAbout: 1
  - p3: 1
  - p4: 1
  - p2: 1
  - p5: 1
  - prop: 1
  - p6: 1
  - StateCode: 1

## Generation Notes

```markdown
# us_urban_school_covid_directional_indicators - PVMAP Generation Notes

Generated: 2026-01-14T00:50:45.371713

Total attempts: 1

---

I'll analyze the input data and generate a PV map for this education dataset.

Looking at the data structure:
- **LEA_STATE** and **LEA_STATE_NAME**: State identifiers (2-letter code and full name)
- **LEAID**: Local Education Agency ID (district identifier)
- **LEA_NAME**: District name
- **SCHID**: School ID
- **SCH_NAME**: School name
- **COMBOKEY**: Composite key (LEAID + SCHID)
- **JJ**: Binary indicator (Yes/No) - appears to be a flag for juvenile justice facilities
- **SCH_DIND_INSTRUCTIONTYPE**: Instruction type code (A = appears to be standard)
- **SCH_DIND_REMOTETYPE, SCH_DIND_REMOTEAMOUNT, SCH_DIND_REMOTEPERCT**: Remote instruction metrics (-9 indicates not applicable/no data)
- **YEAR**: Observation year

The data appears to be a directory/roster of schools rather than measurements. However, since this is from the Civil Rights Data Collection, the observation could be about school existence/enrollment status for a given year.

**Key decisions:**
1. **observationAbout**: Use COMBOKEY or SCHID for school-level granularity. Since COMBOKEY is explicitly provided, I'll use it with a prefix pattern.
2. **observationDate**: Map from YEAR column
3. **StatVar properties**: This appears to be about school enrollment or school characteristics
4. **JJ flag**: Maps to a constraint (juvenile justice facility status)

**Limitations noted:**
- The `-9` values in remote instruction columns indicate missing data and will be skipped (expected behavior)
- This data structure is more of a directory/roster than measurements with explicit values, so I'm interpreting presence as a binary observation

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
LEA_STATE,StateCode,{Data}
YEAR,observationDate,{Data}
COMBOKEY,observationAbout,crdc/school/{Data}
JJ:Yes,juvenileJusticeFacility,Yes
JJ:No,juvenileJusticeFacility,No
SCH_DIND_INSTRUCTIONTYPE,value,1,populationType,School,measuredProperty,count,statType,measuredValue
```

**Notes:**
1. **observationAbout**: Using `crdc/school/{Data}` with COMBOKEY as the school identifier, following Civil Rights Data Collection conventions
2. **JJ constraint**: Maps Yes/No values to `juvenileJusticeFacility` property to distinguish between regular and juvenile justice schools
3. **StatVar properties**: On SCH_DIND_INSTRUCTIONTYPE column since it's present for all schools. Using `value=1` to indicate school existence in the dataset (count of schools)
4. **Missing data**: Columns with `-9` values (remote instruction metrics) are not mapped - these cells will be skipped automatically
5. **State information**: Captured as intermediate variable `StateCode` but not directly used (could be used for validation but school ID is sufficient for observationAbout)

This PV map treats each row as an observation of a school's existence/enrollment status for that year, with the juvenile justice facility statu...
```

## Diff Excerpt

```diff
- 
+ populationType: dcid:School
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ value: 1


- populationType: dcid:PublicSchool
- measuredProperty: dcid:count
- statType: dcid:measuredValue
- medicalCondition: dcid:COVID19
  observationDate: {Data}


+ 
- instructionMode: dcid:InstructionInRemote
- value: 1


+ 
- instructionMode: dcid:InstructionInPerson
- value: 1


- 
+ observationAbout: dcid:crdc/school/{Data}


+ 
- instructionMode: dcid:InstructionInHybrid
- value: 1


+ 
- instructionMode: dcid:NoEffect
- value: 1


- 
+ p2: dcid:v2
+ p3: dcid:v3
+ p4: dcid:v4
+ p5: dcid:v5
+ p6: dcid:v6
+ prop: dcid:value


- observationAbout: {Data}
+ StateCode: {Data}


```

## Generation Logs

- `logs/us_urban_school_covid_directional_indicators/generation_20260114_003501.log`
- `logs/us_urban_school_covid_directional_indicators/generation_20260114_005023.log`
