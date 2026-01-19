# ipeds - Analysis

**Generated**: 2026-01-19T13:36:09.898201

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 95.8% | - |
| PV Accuracy | 16.7% | 🔴 Poor |
| Precision | 0.9% | - |
| Recall | 16.7% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 24 |
| Nodes Auto-Generated | 24 |
| Nodes Matched | 0 |
| Nodes With Diff | 23 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 1 |
| PVs Modified | 0 |
| PVs Deleted | 5 |
| PVs Added | 107 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - GLOBAL: 1
  - observationDate: 1
  - populationType: 1
  - measuredProperty: 1
  - measurementDenominator: 1

### Properties Added (Extra in LLM output)
  - name: 16
  - populationType: 16
  - measuredProperty: 16
  - statType: 16
  - value: 15
  - attendanceStatus: 12
  - adjustment: 2
  - inclusion: 2
  - exclusion: 2
  - unit: 2
  - retentionStatus: 2
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1
  - property: 1
  - observationDate: 1

## Generation Notes

```markdown
# ipeds - PVMAP Generation Notes

Generated: 2026-01-16T17:03:26.018917

Total attempts: 1

---

Looking at this IPEDS (Integrated Postsecondary Education Data System) dataset, I can see it contains higher education institution statistics with graduation rates, retention rates, and student-faculty ratios.

**Analysis:**
- This is **raw data**, not pre-formatted Data Commons data (no `variableMeasured` column with DCIDs)
- `UNITID` is the institution identifier (observationAbout)
- `Year` is the observation date
- Multiple columns contain different metrics (graduation rates, retention rates, student-faculty ratios)
- Columns starting with `X` appear to be data quality flags (R=Reported, A=Not applicable, Z=Zero, P=Preliminary)
- Need to map each metric column with full StatVar properties

**Key mappings needed:**
- UNITID → observationAbout (IPEDS institution IDs use format `ipeds/XXXXX`)
- Year → observationDate
- Each rate/count column needs complete StatVar properties

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5
UNITID,#Format,"observationAbout=ipeds/{Number}"
Year,observationDate,{Data}
GRCOHRT,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,name,"Graduation cohort count"
UGENTERN,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,name,"Undergraduate entering cohort count"
PGRCOHRT,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,name,"Graduate cohort count"
RRFTCT,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,FullTime,name,"Full-time retention count"
RRFTEX,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,FullTime,exclusion,Exclusions,name,"Full-time exclusions count"
RRFTIN,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,FullTime,inclusion,Inclusions,name,"Full-time inclusions count"
RRFTCTA,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,FullTime,adjustment,Adjusted,name,"Full-time adjusted cohort count"
RET_NMF,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,FullTime,retentionStatus,Retained,name,"Full-time retained student count"
RET_PCF,value,{Number},populationType,Student,measuredProperty,retentionRate,statType,measuredValue,attendanceStatus,FullTime,unit,Percent,name,"Full-time retention rate"
RRPTCT,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,PartTime,name,"Part-time retention count"
RRPTEX,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,PartTime,exclusion,Exclusions,name,"Part-time exclusions count"
RRPTIN,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,attendanceStatus,PartTime,inclusion,Inclusions,name,"Part-time inclu...
```

## Diff Excerpt

```diff
- GLOBAL: dcid:property
+ p2: dcid:v2
+ p3: dcid:v3
+ p4: dcid:v4
+ p5: dcid:v5
+ property: dcid:value


- 
+ name: "Part-time adjusted cohort count"
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ adjustment: dcid:Adjusted
+ attendanceStatus: dcid:PartTime
+ value: {Number}


- 
+ name: "Full-time inclusions count"
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ attendanceStatus: dcid:FullTime
+ inclusion: dcid:Inclusions
+ value: {Number}


- 
+ name: "Full-time retention count"
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ attendanceStatus: dcid:FullTime
+ value: {Number}


- 
+ name: "Graduation cohort count"
+ populationType: dcid:Student
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ value: {Number}


- observationDate: {Number}
?                   ^^^^^^

+ observationDate: {Data}
?                   ^^^^

```

## Generation Logs

- `logs/ipeds/generation_20260116_165000.log`
- `logs/ipeds/generation_20260116_165349.log`
- `logs/ipeds/generation_20260116_170300.log`
