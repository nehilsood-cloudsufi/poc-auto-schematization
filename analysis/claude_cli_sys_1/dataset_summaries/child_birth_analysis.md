# child_birth - Analysis

**Generated**: 2026-01-19T13:36:09.876840

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 94.1% | - |
| PV Accuracy | 18.2% | 🔴 Poor |
| Precision | 14.8% | - |
| Recall | 18.2% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 17 |
| Nodes Auto-Generated | 17 |
| Nodes Matched | 0 |
| Nodes With Diff | 16 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 4 |
| PVs Modified | 0 |
| PVs Deleted | 18 |
| PVs Added | 23 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - populationType: 3
  - measuredProperty: 3
  - statType: 3
  - observationPeriod: 2
  - medicalStatus: 1
  - p1: 1
  - age: 1
  - Year: 1
  - Month: 1
  - observationDate: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - populationType: 3
  - measuredProperty: 3
  - statType: 3
  - eventType: 3
  - observationDate: 2
  - observationPeriod: 2
  - observationAbout: 1
  - p5: 1
  - p6: 1
  - prop: 1
  - Year: 1
  - Month: 1
  - age: 1

## Generation Notes

```markdown
# child_birth - PVMAP Generation Notes

Generated: 2026-01-16T13:00:58.461573

Total attempts: 3

---

Looking at the error, the processor produced 0 output rows with `warning-missing-property-key = 6930`, which means the keys in the PVMAP don't match the actual column headers or cell values in the input data.

Let me analyze the input data structure:

**Input columns:** `State,Year,Month,Period,Indicator,Data Value`

The data is in **Pattern D: Flat Data with Constraint Column** format where:
- Each row is a complete observation
- `Indicator` column contains the metric type (different indicators need different mappings)
- `Period` column contains the time period type (Monthly vs 12 Month-ending)

**Critical issues to fix:**
1. Keys must EXACTLY match column headers: `State`, `Year`, `Month`, `Period`, `Indicator`, `Data Value` (note the space in "Data Value")
2. Need explicit mapping for "UNITED STATES" → country/USA
3. Need to handle month names → numbers
4. Need different `observationPeriod` for "Monthly" vs "12 Month-ending"
5. Need different StatVar properties for each Indicator type

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
State:UNITED STATES,observationAbout,country/USA
Year,Year,{Number}
Month,#Regex,"(?P<Mon>January|February|March|April|May|June|July|August|September|October|November|December)",Month,{Mon}
Data Value,value,{Number}
Period:Monthly,observationPeriod,P1M,observationDate,{Year}-{Month}
Period:12 Month-ending,observationPeriod,P12M,observationDate,{Year}-{Month}
Indicator:Number of Live Births,populationType,Person,measuredProperty,count,statType,measuredValue,eventType,Birth
Indicator:Number of Deaths,populationType,Person,measuredProperty,count,statType,measuredValue,eventType,Death
Indicator:Number of Infant Deaths,populationType,Person,measuredProperty,count,statType,measuredValue,eventType,Death,age,Years0To1
```

**Key fixes:**
- `State:UNITED STATES` explicitly maps to `country/USA` (full name requires explicit mapping)
- `Data Value` (with space) matches the actual column header
- `Month` uses regex to capture full month names and store as intermediate variable
- `Period:Monthly` and `Period:12 Month-ending` set both `observationPeriod` AND construct `observationDate` from `{Year}-{Month}`
- Each Indicator value maps to appropriate StatVar properties with `eventType` constraint
- Infant deaths add `age,Years0To1` constraint to differentiate from total deaths

```

## Diff Excerpt

```diff
+ 
- populationType: dcid:BirthEvent
- measuredProperty: dcid:count
- statType: dcid:measuredValue
- medicalStatus: dcid:LiveBirth


- 
+ observationAbout: dcid:country/USA


- p1: dcid:v1
  p2: dcid:v2
  p3: dcid:v3
  p4: dcid:v4
+ p5: dcid:v5
+ p6: dcid:v6
+ prop: dcid:value


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ eventType: dcid:Death


+ 
- populationType: dcid:MortalityEvent
- measuredProperty: dcid:count
- statType: dcid:measuredValue
- age: dcid:YearsUpto1


- observationPeriod: dcid:P1Y
+ 


- Year: {Data}
+ Year: {Number}


- observationPeriod: dcid:P1M
+ 


- 
+ observationDate: {Year}-{Month}
+ observationPeriod: dcid:P12M


```

## Generation Logs

- `logs/child_birth/generation_20260116_130003.log`
