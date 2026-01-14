# us_bls_bls_ces_state - Analysis

**Generated**: 2026-01-14T14:56:48.872080

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.3% | 🔴 Poor |
| Node Coverage | 0.5% | - |
| PV Accuracy | 0.1% | 🔴 Poor |
| Precision | 56.0% | - |
| Recall | 0.1% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 1992 |
| Nodes Auto-Generated | 7 |
| Nodes Matched | 5 |
| Nodes With Diff | 5 |
| Nodes Missing (LLM missed) | 1982 |
| Nodes Extra (LLM added) | 2 |
| PVs Matched | 12 |
| PVs Modified | 2 |
| PVs Deleted | 8260 |
| PVs Added | 11 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - name: 1917
  - industry: 1771
  - observationAbout: 1347
  - populationType: 1295
  - unit: 366
  - measurementQualifier: 366
  - statType: 366
  - measuredProperty: 365
  - establishmentOwnership: 239
  - workCategory: 202

### Properties Added (Extra in LLM output)
  - naics: 2
  - populationType: 2
  - observationDate: 1
  - measuredProperty: 1
  - unit: 1
  - measurementMethod: 1
  - statType: 1
  - prop: 1
  - observationAbout: 1

### Properties Modified (Different values)
  - measuredProperty: 1
  - Year: 1

## Generation Notes

```markdown
# us_bls_bls_ces_state - PVMAP Generation Notes

Generated: 2026-01-13T21:18:13.815154

Total attempts: 1

---

Looking at the input data, this is **Pattern A: Flat Data** where each row represents a complete observation.

**Data Structure:**
- `series_type`: Always "SMU" (State Metropolitan Unit)
- `state_id`: State identifier (50=Vermont, 24=Maryland)
- `series_id_value`: Metric identifier (800000001, 3100000030)
- `year`: Year of observation
- `period`: Month code (M01-M12)
- `value`: The measurement

**Key mappings needed:**
1. Extract state DCID from state_id
2. Combine year and period into observationDate
3. Map series_id_value to appropriate StatVar properties
4. Extract numeric value

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
state_id,observationAbout,geoId/{Data},,,,,,,,,,,
year,Year,{Number},,,,,,,,,,,
period,#Regex,"M(?P<Month>[0-9]+)",observationDate,{Year}-{Month},,,,,,,,,,
value,value,{Number},measurementMethod,BLSSeasonallyAdjusted,statType,measuredValue,unit,Thousand,,,,,
series_id_value:800000001,populationType,BLSWorker,measuredProperty,count,naics,NAICS/10-12,,,,,,,
series_id_value:3100000030,populationType,BLSWorker,measuredProperty,weeklyHours,naics,NAICS/31-33,,,,,,,
```

**Checklist:**
- [x] Keys exactly match input column headers or cell values
- [x] `value,{Number}` on value column
- [x] `observationDate` constructed from year + period
- [x] `observationAbout` mapped from state_id
- [x] `populationType`, `measuredProperty`, `statType` on series_id_value rows
- [x] All #Regex use named groups `(?P<Month>...)`
- [x] No separate empty-key row for StatVar properties

```

## Diff Excerpt

```diff
+ 
- name: "All Employees, In Thousands, Government"
- populationType: dcid:Person
- industry: dcid:NAICS/JOLTS_900000
- observationAbout: dcid:geoId/01101


+ 
- name: "All Employees, In Thousands, Insurance Carriers"
- populationType: dcid:Person
- industry: dcid:NAICS/5241
- observationAbout: dcid:geoId/25027


- observationAbout: dcid:geoId/49
+ 


+ 
- name: "Average Hourly Earnings of Production and Nonsupervisory Employees, In Dollars, Trade, Transportation, and Utilities"
- measuredProperty: dcid:earnings
- measurementQualifier: dcid:Hourly
- statType: dcid:meanValue
- industry: dcid:NAICS/1021
- unit: dcid:USDollar
- workCategory: dcid:ProductionAndNonsupervisory


+ 
- name: "All Employees, In Thousands, Trade, Transportation, and Utilities"

```

## Generation Logs

- `logs/us_bls_bls_ces_state/generation_20260113_211549.log`
