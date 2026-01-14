# us_crash_fars_crashdata - Analysis

**Generated**: 2026-01-14T14:56:48.873614

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 3.7% | 🔴 Poor |
| Node Coverage | 10.3% | - |
| PV Accuracy | 0.7% | 🔴 Poor |
| Precision | 39.1% | - |
| Recall | 0.7% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 136 |
| Nodes Auto-Generated | 11 |
| Nodes Matched | 5 |
| Nodes With Diff | 9 |
| Nodes Missing (LLM missed) | 122 |
| Nodes Extra (LLM added) | 1 |
| PVs Matched | 7 |
| PVs Modified | 2 |
| PVs Deleted | 927 |
| PVs Added | 14 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - value: 123
  - name: 122
  - measuredProperty: 121
  - populationType: 121
  - descriptionUrl: 79
  - description: 79
  - locationType: 51
  - ROUTE: 16
  - CONDITION: 15
  - weatherCondition: 15

### Properties Added (Extra in LLM output)
  - StateFips: 1
  - statType: 1
  - measurementMethod: 1
  - Month: 1
  - motoristFatalities: 1
  - observationDate: 1
  - observationPeriod: 1
  - nonMotoristFatalities: 1
  - vehiclesInvolved: 1
  - pedestrianInvolved: 1

### Properties Modified (Different values)
  - populationType: 1
  - Year: 1

## Generation Notes

```markdown
# us_crash_fars_crashdata - PVMAP Generation Notes

Generated: 2026-01-14T00:33:08.514351

Total attempts: 3

---

Looking at the error logs, the issue is clear: **"No place in SVObs"** appears for every observation. The problem is with how `observationAbout` is being constructed.

The current PVMAP attempts to use:
```csv
STATE,StateFips,{Number:02d}
COUNTY,#Format,"observationAbout=geoId/{Number:02d}{Number:03d}"
```

But this fails because:
1. `{Number:02d}` in the STATE row creates a **capitalized variable** `StateFips` - but the syntax is wrong
2. The COUNTY row tries to reference `{Number:02d}` which doesn't exist in context
3. The #Format directive cannot concatenate values from different columns this way

**The fix:** Use proper intermediate variable capture and concatenation:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4
STATE,StateFips,{Number:02d}
COUNTY,#Format,"observationAbout=geoId/{StateFips}{Number:03d}"
MONTH,Month,{Number:02d}
YEAR,Year,{Number}
DAY,observationDate,{Year}-{Month}-{Number:02d},observationPeriod,P1D
PEDS,pedestrianInvolved,{Number}
PERNOTMVIT,nonMotoristFatalities,{Number}
PERMVIT,motoristFatalities,{Number}
VE_TOTAL,vehiclesInvolved,{Number}
FATALS,value,{Number},populationType,MotorVehicleAccident,measuredProperty,count,statType,measuredValue,measurementMethod,FARSData
```

**Key changes:**
1. `STATE` row creates intermediate variable `StateFips` with proper formatting `{Number:02d}`
2. `COUNTY` row uses `#Format` to concatenate: `{StateFips}{Number:03d}` → creates `geoId/01115`, `geoId/28047`, etc.
3. All required properties (`value`, `observationDate`, `observationAbout`, `populationType`, `measuredProperty`, `statType`) are now present
4. Removed mappings for columns that don't need to be in the output (all the name/description columns)

```

## Diff Excerpt

```diff
  


+ 
- name: "Count of crash incident {LCRASH}"
- description: "Count of crash incident where location of the crash is {LCRASH} as it relates to its position within or outside the trafficway based on the First Harmful Event."
- populationType: dcid:VehicleCrashIncident
- measuredProperty: dcid:count
- LCRASH: "on road separator"
- descriptionUrl: "https://crashstats.nhtsa.dot.gov/Api/Public/ViewPublication/813417#page=69"
- locationType: dcid:RoadSeparator
- value: 1


+ 
- name: "Count of crash incident on {CLTWAY}"
- description: "Count of crash incident where the route signing of the trafficway on which the crash occurred is {CLTWAY}"
- populationType: dcid:VehicleCrashIncident
- measuredProperty: dcid:count
- CLTWAY: "county road"
- descriptionUrl: "https://crashstats.nhtsa.dot.gov/Api/Public/ViewPublication/813417#page=51"
- locationType: dcid:CountyRoad
- value: 1


+ 
- name: "Count of crash incident where {ORIENTATION}"
- description: "Count of crash incident where {ORIENTATION} of two motor vehicles in-transport when they are involved in the First Harmful Event of a collision crash"
- populationType: dcid:VehicleCrashIncident
- measuredProperty: dcid:count

```

## Generation Logs

- `logs/us_crash_fars_crashdata/generation_20260114_003158.log`
