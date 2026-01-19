# crdc_instructional_wifi_devices - Analysis

**Generated**: 2026-01-19T13:36:09.880879

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 90.0% | - |
| PV Accuracy | 23.1% | 🟠 Needs Work |
| Precision | 8.8% | - |
| Recall | 23.1% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 10 |
| Nodes Auto-Generated | 10 |
| Nodes Matched | 0 |
| Nodes With Diff | 9 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 3 |
| PVs Modified | 0 |
| PVs Deleted | 10 |
| PVs Added | 31 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - value: 4
  - educationalInstitutionType: 2
  - p1: 1
  - statType: 1
  - populationType: 1
  - internetSubscriptionType: 1

### Properties Added (Extra in LLM output)
  - populationType: 5
  - statType: 5
  - measuredProperty: 4
  - unit: 4
  - value: 4
  - juvenileJusticeFacility: 2
  - p3: 1
  - p4: 1
  - p5: 1
  - p6: 1
  - p7: 1
  - property: 1
  - location: 1

## Generation Notes

```markdown
# crdc_instructional_wifi_devices - PVMAP Generation Notes

Generated: 2026-01-16T14:18:19.909037

Total attempts: 2

---

Looking at the error logs, the issue is clear: **all observations are missing `observationDate`**. The processor is dropping every row because `observationDate` is required but not being set.

The problem in the previous PVMAP was that `YEAR` column mappings didn't include `observationDate`. The column header `YEAR` needs to map to `observationDate,{Data}`, and all the value columns need their complete StatVar properties.

Here's the corrected PVMAP:

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
LEA_STATE,#Format,"observationAbout=geoId/{Data}"
YEAR,observationDate,{Data}
JJ:Yes,juvenileJusticeFacility,Yes
JJ:No,juvenileJusticeFacility,No
SCH_INTERNET_FIBER,value,{Data},unit,BooleanValue,populationType,School,measuredProperty,hasInternetFiber,statType,measuredValue
SCH_INTERNET_WIFI,value,{Data},unit,BooleanValue,populationType,School,measuredProperty,hasInternetWiFi,statType,measuredValue
SCH_INTERNET_SCHDEV,value,{Data},unit,BooleanValue,populationType,School,measuredProperty,hasInternetSchoolDevices,statType,measuredValue
SCH_INTERNET_STUDDEV,value,{Data},unit,BooleanValue,populationType,School,measuredProperty,hasInternetStudentDevices,statType,measuredValue
SCH_INTERNET_WIFIENDEV,value,{Number},populationType,WiFiEnabledDevice,measuredProperty,count,statType,measuredValue,location,School
```

**Key fixes:**
1. ✅ `YEAR` now maps to `observationDate,{Data}` (applies to all rows)
2. ✅ All value columns have complete StatVar properties (`populationType`, `measuredProperty`, `statType`)
3. ✅ Boolean columns include `unit,BooleanValue`
4. ✅ `LEA_STATE` uses `#Format` to create state geoIds (AL → geoId/AL)
5. ✅ `JJ` (juvenile justice facility) mapped as constraint
6. ✅ Device count column uses numeric value with proper properties

**Data note:** Negative values like `-13` in the data will be automatically skipped as non-numeric.

```

## Diff Excerpt

```diff
- p1: dcid:v1
  p2: dcid:v2
+ p3: dcid:v3
+ p4: dcid:v4
+ p5: dcid:v5
+ p6: dcid:v6
+ p7: dcid:v7
+ property: dcid:value


- statType: dcid:measuredValue
+ 


- value: {Number}
+ populationType: dcid:School
+ measuredProperty: dcid:hasInternetSchoolDevices
+ statType: dcid:measuredValue
+ unit: dcid:BooleanValue
+ value: {Data}


- educationalInstitutionType: dcid:JuvenileJusticeFacility
+ juvenileJusticeFacility: dcid:Yes


  observationDate: {Data}


- value: {Number}
+ populationType: dcid:School
+ measuredProperty: dcid:hasInternetFiber
+ statType: dcid:measuredValue
+ unit: dcid:BooleanValue
+ value: {Data}


- populationType: dcid:School
+ populationType: dcid:WiFiEnabledDevice
  measuredProperty: dcid:count
- internetSubscriptionType: dcid:WifiEnabledDevice
+ statType: dcid:measuredValue
+ location: dcid:School
  value: {Number}


- value: {Number}
+ populationType: dcid:School
+ measuredProperty: dcid:hasInternetWiFi
+ statType: dcid:measuredValue

```

## Generation Logs

- `logs/crdc_instructional_wifi_devices/generation_20260116_141744.log`
