# southkorea_statistics_demographics - Analysis

**Generated**: 2026-01-19T13:36:09.920836

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 97.7% | - |
| PV Accuracy | 4.1% | 🔴 Poor |
| Precision | 37.5% | - |
| Recall | 4.1% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 43 |
| Nodes Auto-Generated | 43 |
| Nodes Matched | 0 |
| Nodes With Diff | 42 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 3 |
| PVs Modified | 0 |
| PVs Deleted | 71 |
| PVs Added | 5 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - value: 20
  - observationDate: 16
  - populationType: 15
  - nativity: 7
  - gender: 6
  - residenceType: 2
  - measuredProperty: 2
  - householdType: 1
  - p1: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - value: 1
  - observationAbout: 1
  - property: 1
  - variableMeasured: 1
  - observationDate: 1

## Generation Notes

```markdown
# southkorea_statistics_demographics - PVMAP Generation Notes

Generated: 2026-01-16T14:53:44.366958

Total attempts: 1

---

```csv
key,property,value,p2,v2,p3,v3,p4,v4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured,#Regex,"^dcid:(?P<StatVar>.+)$",variableMeasured,dcid:{StatVar}
```

**CHECKLIST:**
- [x] Keys exactly match input (case-sensitive)
- [x] Special char keys are double-quoted (none needed)
- [x] **Every value column** has: `value,{Number}`, `populationType`, `measuredProperty`, `statType` - **N/A**: StatVar already fully specified in `variableMeasured` column
- [x] `observationDate` format: YYYY, YYYY-MM, or YYYY-MM-DD - Uses existing YYYY format
- [x] `observationAbout` uses valid DCID (geoId/, country/, wikidataId/, Earth) - Already contains `dcid:country/KOR` format
- [x] No dynamic place construction - explicit mappings only - Uses existing DCID values
- [x] #Regex uses named groups `(?P<Name>...)` - Extracts StatVar from `dcid:` prefix
- [x] Note any data limitations in response

**NOTES:**
1. This is a **pre-processed StatVarObservation format** - all properties are already in Data Commons format
2. The `observationAbout` column contains complete DCIDs (e.g., `dcid:country/KOR`)
3. The `variableMeasured` column contains complete StatVar DCIDs (e.g., `dcid:Count_Person_Male_Native`)
4. The regex extracts the StatVar from the `dcid:` prefix to ensure proper formatting
5. `unit` and `scalingFactor` columns are empty in the data, so they're passed through as-is
6. No additional StatVar properties needed since `variableMeasured` already fully specifies the statistical variable

```

## Diff Excerpt

```diff
+ 
- populationType: dcid:Household
- householdType: dcid:InstitutionalHousehold
- value: {Number}


- observationDate: 2022
+ 


  


+ 
- populationType: dcid:HousingUnit
- residenceType: dcid:RowHouse
- value: {Number}


- observationDate: 2028
+ 


- observationDate: 2024
+ 


+ 
- populationType: dcid:Person
- gender: dcid:Female
- value: {Number}


- value: 1
+ 


- observationDate: 2018
+ 


+ 
- populationType: dcid:HousingUnit
- residenceType: dcid:Apartment
- value: {Number}


- observationDate: 2020
+ 


```

## Generation Logs

- `logs/southkorea_statistics_demographics/generation_20260116_145332.log`
