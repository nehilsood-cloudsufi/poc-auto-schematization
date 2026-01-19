# us_crash_fars_crashdata - Analysis

**Generated**: 2026-01-19T13:36:09.938506

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
  - LCRASH: 14
  - crashType: 14
  - ORIENTATION: 14
  - mannerOfCollision: 14
  - INTER: 13
  - roadIntersectionType: 13
  - workZoneType: 12
  - CLTWAY: 9
  - lightCondition: 9
  - LIGHT: 9
  - SP: 8
  - jurisdiction: 8
  - SEPJUR: 8
  - crashInvolvement: 8
  - WRK: 6
  - ZONE: 6
  - vehicleOccupantType: 4
  - observationDate: 3
  - NH: 2
  - NATHIGH: 2
  - vehicleType: 2
  - vehicleStatus: 2
  - observationAbout: 2
  - causeOfDeath: 1
  - measurementMethod: 1
  - Prop: 1

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
  - prop: 1
  - p3: 1
  - p2: 1
  - p4: 1

### Properties Modified (Different values)
  - populationType: 1
  - Year: 1

## Generation Notes

```markdown
# us_crash_fars_crashdata - PVMAP Generation Notes

Generated: 2026-01-14T17:32:12.512632

Total attempts: 3

---

Looking at the error logs, the issue is clear: **all observations are missing the `observationAbout` property** - "No place in SVObs" appears hundreds of times.

The problem is in how I mapped the STATE column. The #Format directive is being treated as a property assignment, not as an instruction to format the observationAbout value.

The STATE column contains state FIPS codes (1, 28, 6, 48), which need to be zero-padded to 2 digits and prefixed with "geoId/".

Here's the corrected PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
STATE,#Format,"observationAbout=geoId/{Number:02d}"
COUNTY,#Format,"CountyFips={Number:03d}"
MONTH,Month,{Number}
DAY,Day,{Number}
YEAR,Year,{Number}
FATALS,observationDate,{Year}-{Month}-{Day},value,{Number},populationType,MotorVehicleAccident,measuredProperty,count,statType,measuredValue
Urban,areaType,Urban
Rural,areaType,Rural
Daylight,lightCondition,Daylight
Dark - Not Lighted,lightCondition,DarkNotLighted
Dark - Lighted,lightCondition,DarkLighted
"Dark - Unknown Lighting",lightCondition,DarkUnknownLighting
Dawn,lightCondition,Dawn
Dusk,lightCondition,Dusk
Clear,weatherCondition,Clear
Rain,weatherCondition,Rain
Sleet or Hail,weatherCondition,SleetOrHail
Snow,weatherCondition,Snow
Fog,weatherCondition,Fog
"Rain and Fog",weatherCondition,RainAndFog
Cloudy,weatherCondition,Cloudy
Blowing Sand or Snow,weatherCondition,BlowingSandOrSnow
Severe Crosswinds,weatherCondition,SevereCrosswinds
Blowing Snow,weatherCondition,BlowingSnow
Freezing Rain or Drizzle,weatherCondition,FreezingRainOrDrizzle
```

**Key fixes:**
1. **STATE mapping**: Changed to `#Format,"observationAbout=geoId/{Number:02d}"` to properly format state FIPS codes (1→geoId/01, 28→geoId/28, etc.)
2. **Date construction**: Capture Month, Day, Year as intermediate variables, then construct observationDate on the FATALS (value) column
3. **All StatVar properties** (`populationType`, `measuredProperty`, `statType`) are on the FATALS column header row
4. **Constraint properties** (areaType, lightCondition, weatherCondition) map from their respective cell values

This will now generate observations like:
- `observationAbout=geoId/01, observationDate=2021-02-12, value=2, variableMeasured=Count_MotorVehicleAccident_Urban_DarkNotLighted_Rain`

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
- ORIENTATION: "unknown orientation of collision"
- crashType: dcid:CollisionCrash
- descriptionUrl: "https://crashstats.nhtsa.dot.gov/Api/Public/ViewPublication/813417#page=63"
- mannerOfCollision: dcid:NHTSA_UnknownOrientation
- value: 1


- 
+ StateFips: {Number:02d}


+ 
- name: "Count of crash incident on {SEPJUR}"
- description: "Count of crash incident where location on the trafficway where the crash occurred is {SP} even though it may be patrolled by State, county or local police"
- populationType: dcid:VehicleCrashIncident
- measuredProperty: dcid:count
- SEPJUR: "national park service"
- SP: "national park service qualifies as a special jurisdiction"
- descriptionUrl: "https://crashstats.nhtsa.dot.gov/Api/Public/ViewPublication/813417#page=55"
- jurisdiction: dcid:NationalParkService

```

## Generation Logs

- `logs/us_crash_fars_crashdata/generation_20260114_003158.log`
- `logs/us_crash_fars_crashdata/generation_20260114_173103.log`
