# school_finance - Analysis

**Generated**: 2026-01-19T13:36:09.916283

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 93.8% | - |
| PV Accuracy | 11.8% | 🔴 Poor |
| Precision | 18.2% | - |
| Recall | 11.8% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 16 |
| Nodes Auto-Generated | 16 |
| Nodes Matched | 0 |
| Nodes With Diff | 15 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 4 |
| PVs Modified | 0 |
| PVs Deleted | 30 |
| PVs Added | 18 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - populationType: 6
  - measuredProperty: 6
  - expenditureType: 5
  - value: 4
  - facultyType: 3
  - unit: 3
  - statType: 1
  - observationDate: 1
  - measurementQualifier: 1

### Properties Added (Extra in LLM output)
  - populationType: 2
  - measuredProperty: 2
  - statType: 2
  - scalingFactor: 2
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1
  - p6: 1
  - p7: 1
  - p8: 1
  - property: 1
  - StateDcid: 1
  - observationDate: 1

## Generation Notes

```markdown
# school_finance - PVMAP Generation Notes

Generated: 2026-01-16T14:49:10.172191

Total attempts: 1

---

Based on the input data, I need to create a PV map that transforms school finance data into Data Commons format. Let me analyze the structure:

**Data Structure:**
- **Year**: Observation date (already numeric)
- **LEA_STATE**: State code (AL = Alabama)
- **LEAID**: Local Education Agency ID
- **LEA_NAME**: District name
- **SCHID**: School ID
- **SCH_NAME**: School name
- **COMBOKEY**: Composite key (LEAID + SCHID)
- **JJ**: Some flag/indicator
- **FTE_TEACHERS_FIN**: Number of full-time equivalent teachers (the observation location)
- **TEACH_AMOUNT**: Total teacher salaries in dollars (value)
- **AVG_TEACH_SALARY**: Average teacher salary (value)
- **Incomplete**: Flag for incomplete data

**Key Observations:**
1. Two value columns: `TEACH_AMOUNT` (total salaries) and `AVG_TEACH_SALARY` (average salary)
2. Schools are the observation entities - need to construct DCIDs using COMBOKEY
3. State code needs conversion to geoId format
4. FTE_TEACHERS_FIN appears to be associated count, not the observation subject

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7,p8,v8
year,observationDate,{Data}
LEA_STATE:AL,StateDcid,geoId/01
COMBOKEY,#Format,observationAbout=nces/{Data}
TEACH_AMOUNT,value,{Number},populationType,PublicSchoolTeacher,measuredProperty,salary,statType,measuredValue,unit,USDollar,scalingFactor,1
AVG_TEACH_SALARY,value,{Number},populationType,PublicSchoolTeacher,measuredProperty,salary,statType,mean,unit,USDollar,scalingFactor,1
```

**Notes:**
- Using `nces/` DCID scheme for schools based on COMBOKEY (standard format for US education data)
- State code mapped to `geoId/01` (Alabama)
- `TEACH_AMOUNT` represents total measured salary values
- `AVG_TEACH_SALARY` represents mean salary (statType=mean)
- Both use `PublicSchoolTeacher` as populationType based on the US public school finance context
- `FTE_TEACHERS_FIN` not mapped as it's likely metadata about teacher counts, not an observation property
- Empty `Incomplete` values will be auto-skipped

**Data Limitations:**
- Only Alabama state code present in sample; additional state mappings needed for complete dataset
- School DCID scheme assumed to be `nces/{COMBOKEY}` - may need validation with actual Data Commons schema

```

## Diff Excerpt

```diff
  


- 
+ p2: dcid:v2
+ p3: dcid:v3
+ p4: dcid:v4
+ p5: dcid:v5
+ p6: dcid:v6
+ p7: dcid:v7
+ p8: dcid:v8
+ property: dcid:value


- 
+ StateDcid: dcid:geoId/01


- populationType: dcid:EconomicActivity
+ populationType: dcid:PublicSchoolTeacher
- measuredProperty: dcid:expenditure
?                        ^^^^^^^^^ ^

+ measuredProperty: dcid:salary
?                        ^^^^ ^

- statType: dcid:meanValue
?                    -----

+ statType: dcid:mean
+ scalingFactor: 1
- expenditureType: dcid:Salaries
- facultyType: dcid:Teacher
  unit: dcid:USDollar
  value: {Number}


+ 
- populationType: dcid:EconomicActivity
- measuredProperty: dcid:expenditure
- expenditureType: dcid:Salaries
- unit: dcid:USDollar
- value: {Number}


- populationType: dcid:EconomicActivity
+ populationType: dcid:PublicSchoolTeacher
- measuredProperty: dcid:expenditure
?                        ^^^^^^^^^ ^


```

## Generation Logs

- `logs/school_finance/generation_20260116_144852.log`
