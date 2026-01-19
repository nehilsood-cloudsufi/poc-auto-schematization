# fbi_fbigovcrime - Analysis

**Generated**: 2026-01-19T13:36:09.885943

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 5.3% | - |
| PV Accuracy | 8.7% | 🔴 Poor |
| Precision | 25.8% | - |
| Recall | 8.7% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 150 |
| Nodes Auto-Generated | 12 |
| Nodes Matched | 0 |
| Nodes With Diff | 8 |
| Nodes Missing (LLM missed) | 142 |
| Nodes Extra (LLM added) | 4 |
| PVs Matched | 16 |
| PVs Modified | 0 |
| PVs Deleted | 167 |
| PVs Added | 46 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - StateName: 102
  - observationDate: 31
  - value: 10
  - populationType: 10
  - crimeType: 10
  - observationAbout: 1
  - p1: 1
  - observationPeriod: 1
  - CityName: 1

### Properties Added (Extra in LLM output)
  - measuredProperty: 9
  - observationDate: 9
  - statType: 9
  - populationType: 5
  - value: 5
  - crimeType: 4
  - p7: 1
  - p8: 1
  - p6: 1
  - prop: 1
  - State: 1

## Generation Notes

```markdown
# fbi_fbigovcrime - PVMAP Generation Notes

Generated: 2026-01-13T23:43:33.214891

Total attempts: 1

---

Looking at this FBI Crime Statistics data, I need to create a PV map that transforms it into Data Commons format. Let me analyze the structure:

**Data Pattern**: This is a **wide data format** with multiple value columns (each crime type is a separate column). Each row represents a city's crime statistics for a specific year (2023, based on the title).

**Key observations**:
1. Place: City_Name + State combination (e.g., "Abbeville" in "ALABAMA State")
2. Date: 2023 (from table title)
3. Multiple crime type columns (Violent crime, Murder, Rape, etc.)
4. Each column needs StatVar properties for crime classification

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7,p8,v8
State,State,{Data},,,,,,,,,,,,,,
City_Name,#Format,"observationAbout=geoId/{State}__{Data}",,,,,,,,,,,,,,,
Population,value,{Number},observationDate,2023,populationType,Person,measuredProperty,count,statType,measuredValue,,,,,,
Violent
crime,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,ViolentCrime,,,,
Murder and
nonnegligent
manslaughter,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,MurderAndNonnegligentManslaughter,,,,
Rape,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,ForcibleRape,,,,
Robbery,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,Robbery,,,,
Aggravated
assault,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,AggravatedAssault,,,,
Property
crime,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,PropertyCrime,,,,
Burglary,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,Burglary,,,,
Larceny-
theft,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,LarcenyTheft,,,,
Motor
vehicle
theft,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,MotorVehicleTheft,,,,
Arson,value,{Number},observationDate,2023,populationType,CriminalActivities,measuredProperty,count,statType,measuredValue,crimeType,Arson,,,,
```

**Key design decisions**:

1. **Place resolution**: Using `#Format` with `{State}__{Data}` pattern to create a composite key (e.g., `geoId/ALABAMA State__Abbeville`). This may need adjustment based on your place resolution file.

2. **Date**: Hardcoded to "2023" based on table title. If processing multiple years, you'd need a Year column.

3. **Crime types**: Each crime colum...
```

## Diff Excerpt

```diff
- observationDate: 2037
+ 


- StateName: {Key}
+ 


+ 
- populationType: dcid:CriminalActivities
- crimeType: dcid:MotorVehicleTheft
- value: {Number}


- StateName: {Key}
+ 


- StateName: {Key}
+ 


- StateName: {Key}
+ 


- observationAbout: "{CityName} {StateName}"
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ observationDate: 2023
+ value: {Number}


- StateName: {Key}
+ 


- StateName: {Key}
+ 


- observationDate: 2033
+ 


- StateName: {Key}
+ 



```

## Generation Logs

- `logs/fbi_fbigovcrime/generation_20260113_232931.log`
- `logs/fbi_fbigovcrime/generation_20260113_234312.log`
