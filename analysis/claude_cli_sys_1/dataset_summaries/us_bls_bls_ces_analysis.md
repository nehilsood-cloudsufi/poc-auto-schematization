# us_bls_bls_ces - Analysis

**Generated**: 2026-01-19T13:36:09.930887

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.4% | 🔴 Poor |
| Node Coverage | 1.3% | - |
| PV Accuracy | 0.4% | 🔴 Poor |
| Precision | 6.6% | - |
| Recall | 0.4% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 525 |
| Nodes Auto-Generated | 23 |
| Nodes Matched | 2 |
| Nodes With Diff | 5 |
| Nodes Missing (LLM missed) | 519 |
| Nodes Extra (LLM added) | 17 |
| PVs Matched | 8 |
| PVs Modified | 0 |
| PVs Deleted | 2166 |
| PVs Added | 113 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - measurementMethod: 508
  - name: 508
  - industry: 492
  - statType: 120
  - unit: 120
  - measurementQualifier: 120
  - measuredProperty: 120
  - workCategory: 79
  - establishmentOwnership: 46
  - gender: 21
  - Month: 12
  - workStatus: 6
  - residentStatus: 4
  - Year: 1
  - observationDate: 1
  - value: 1
  - p1: 1
  - p9: 1
  - p8: 1
  - populationType: 1
  - employmentStatus: 1
  - observationPeriod: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - statType: 20
  - measuredProperty: 20
  - populationType: 20
  - observationAbout: 14
  - value: 13
  - observationDate: 13
  - naics: 7
  - observationPeriod: 3
  - unit: 1
  - industryType: 1
  - prop: 1

## Generation Notes

```markdown
# us_bls_bls_ces - PVMAP Generation Notes

Generated: 2026-01-13T21:18:00.214469

Total attempts: 3

---

Looking at the error, the processor dropped all observations due to "unresolved-date" (8 observations dropped). This means the `observationDate` mapping is not working correctly.

Let me analyze the input data structure:

1. The data has header rows (Years, empty row)
2. Row 4 has column headers: "Series ID" followed by month-year combinations (Jan 2015, Feb 2015, etc.)
3. Rows 5-8 contain Series IDs in column 1 and numeric values in subsequent columns
4. The `mapped_rows,1` and `mapped_columns,3` config indicates row 1 is a header and first 3 columns are mapped

The issue is that:
1. The date format "Jan 2015", "Feb 2015" etc. needs proper parsing
2. Series IDs need to be mapped to proper observation properties
3. The processor needs all required properties properly mapped

Let me create a corrected PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
Series ID,#ignore,skip
CEU0000000001,observationAbout,geoId/US,populationType,BLSWorker,measuredProperty,count,statType,measuredValue,naics,NAICS,unit,Count
CES0000000001,observationAbout,geoId/US,populationType,BLSWorker,measuredProperty,count,statType,measuredValue
CEU0500000001,observationAbout,geoId/US,naics,NAICS/05,populationType,BLSWorker,measuredProperty,count,statType,measuredValue
CES0500000001,observationAbout,geoId/US,naics,NAICS/05,populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Jan 2015,#Regex,"^(?P<Mon>[A-Za-z]+) (?P<Yr>[0-9]+)$",observationDate,2015-01,observationPeriod,P1M,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Feb 2015,observationDate,2015-02,observationPeriod,P1M,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Mar 2015,observationDate,2015-03,observationPeriod,P1M,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Apr 2015,observationDate,2015-04,observationAbout,country/USA,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
May 2015,observationDate,2015-05,observationAbout,country/USA,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Jun 2015,observationDate,2015-06,observationAbout,country/USA,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Jul 2015,observationDate,2015-07,observationAbout,Earth,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Aug 2015,observationDate,2015-08,observationAbout,Earth,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Sep 2015,observationDate,2015-09,observationAbout,Earth,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Oct 2015,observationDate,2015-10,observationAbout,Earth,value,{Number},populationType,BLSWorker,measuredProperty,count,statType,measuredValue
Nov 2015,observa...
```

## Diff Excerpt

```diff
+ 
- name: "All employees","publishing industries"
- industry: dcid:NAICS/513
- measurementMethod: dcid:BLSSeasonallyAdjusted


- Month: 9
+ 


- Month: 8
+ 


+ 
- name: "Average weekly earnings of production and nonsupervisory employees","dcid:construction"
- measuredProperty: dcid:earnings
- measurementQualifier: dcid:Weekly
- statType: dcid:meanValue
- industry: dcid:NAICS/23
- measurementMethod: dcid:BLSSeasonallyAdjusted
- unit: dcid:USDollar
- workCategory: dcid:ProductionAndNonsupervisory


+ 
- name: "All employees","waste management and remediation services"
- industry: dcid:NAICS/562
- measurementMethod: dcid:BLSSeasonallyUnadjusted


+ 
- name: "All employees","support activities for mining"
- industry: dcid:NAICS/213
- measurementMethod: dcid:BLSSeasonallyAdjusted


+ 
- name: "All employees","building material and garden equipment and supplies dealers"
- industry: dcid:NAICS/444
- measurementMethod: dcid:BLSSeasonallyUnadjusted


+ 
- name: "Average hourly earnings of production and nonsupervisory employees","dcid:utilities"
- measuredProperty: dcid:earnings
- measurementQualifier: dcid:Hourly
- statType: dcid:meanValue
- industry: dcid:NAICS/22
- measurementMethod: dcid:BLSSeasonallyAdjusted

```

## Generation Logs

- `logs/us_bls_bls_ces/generation_20260113_211549.log`
