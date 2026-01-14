# finland_census - Analysis

**Generated**: 2026-01-14T14:56:48.863477

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 15.0% | - |
| PV Accuracy | 16.4% | 🔴 Poor |
| Precision | 64.3% | - |
| Recall | 16.4% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 434 |
| Nodes Auto-Generated | 65 |
| Nodes Matched | 0 |
| Nodes With Diff | 65 |
| Nodes Missing (LLM missed) | 369 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 110 |
| PVs Modified | 41 |
| PVs Deleted | 521 |
| PVs Added | 84 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 329
  - value: 61
  - measurementDenominator: 26
  - observationDate: 26
  - measuredProperty: 14
  - populationType: 14
  - statType: 13
  - unit: 10
  - placeOfResidenceClassification: 10
  - languageSpokenAtHome: 5

### Properties Added (Extra in LLM output)
  - observationAbout: 29
  - value: 29
  - residenceType: 7
  - statType: 6
  - measurementMethod: 4
  - religion: 3
  - unit: 3
  - nativity: 2
  - prop: 1

### Properties Modified (Different values)
  - observationDate: 35
  - placeOfBirth: 2
  - age: 1
  - populationType: 1
  - statType: 1

## Generation Notes

```markdown
# finland_census - PVMAP Generation Notes

Generated: 2026-01-13T21:14:35.891704

Total attempts: 2

---

Looking at this input data, I need to understand its structure:

1. **Row 1**: Title row (skip)
2. **Row 3**: Column headers with years (1990-2024)
3. **Column A**: Empty in header row
4. **Column B onwards**: Year values (1990, 1991, ..., 2024)
5. **Rows 4+**: Row labels in Column A, with numeric values across the years

This is a **Pattern B: Wide Data** structure where:
- Each year column represents a different observation date
- Each row represents a different metric
- The row labels describe what's being measured

Let me create the PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
1990,observationDate,1990-12-31,,,,,,,,,,,,
1991,observationDate,1991-12-31,,,,,,,,,,,,
1992,observationDate,1992-12-31,,,,,,,,,,,,
1993,observationDate,1993-12-31,,,,,,,,,,,,
1994,observationDate,1994-12-31,,,,,,,,,,,,
1995,observationDate,1995-12-31,,,,,,,,,,,,
1996,observationDate,1996-12-31,,,,,,,,,,,,
1997,observationDate,1997-12-31,,,,,,,,,,,,
1998,observationDate,1998-12-31,,,,,,,,,,,,
1999,observationDate,1999-12-31,,,,,,,,,,,,
2000,observationDate,2000-12-31,,,,,,,,,,,,
2001,observationDate,2001-12-31,,,,,,,,,,,,
2002,observationDate,2002-12-31,,,,,,,,,,,,
2003,observationDate,2003-12-31,,,,,,,,,,,,
2004,observationDate,2004-12-31,,,,,,,,,,,,
2005,observationDate,2005-12-31,,,,,,,,,,,,
2006,observationDate,2006-12-31,,,,,,,,,,,,
2007,observationDate,2007-12-31,,,,,,,,,,,,
2008,observationDate,2008-12-31,,,,,,,,,,,,
2009,observationDate,2009-12-31,,,,,,,,,,,,
2010,observationDate,2010-12-31,,,,,,,,,,,,
2011,observationDate,2011-12-31,,,,,,,,,,,,
2012,observationDate,2012-12-31,,,,,,,,,,,,
2013,observationDate,2013-12-31,,,,,,,,,,,,
2014,observationDate,2014-12-31,,,,,,,,,,,,
2015,observationDate,2015-12-31,,,,,,,,,,,,
2016,observationDate,2016-12-31,,,,,,,,,,,,
2017,observationDate,2017-12-31,,,,,,,,,,,,
2018,observationDate,2018-12-31,,,,,,,,,,,,
2019,observationDate,2019-12-31,,,,,,,,,,,,
2020,observationDate,2020-12-31,,,,,,,,,,,,
2021,observationDate,2021-12-31,,,,,,,,,,,,
2022,observationDate,2022-12-31,,,,,,,,,,,,
2023,observationDate,2023-12-31,,,,,,,,,,,,
2024,observationDate,2024-12-31,,,,,,,,,,,,
Increase of population,value,{Number},observationAbout,country/FIN,populationType,Person,measuredProperty,count,statType,measuredValue,measurementMethod,PopulationIncrease
"Increase of population, %",value,{Number},observationAbout,country/FIN,populationType,Person,measuredProperty,count,statType,measuredValue,measurementMethod,PopulationIncreaseRate,unit,Percent
"Share of persons aged under 15, %",value,{Number},observationAbout,country/FIN,populationType,Person,measuredProperty,count,statType,measuredValue,age,Years0To14,unit,Percent
"Share of persons aged 15 to 64, %",value,{Number},observationAbout,country/FIN,populationType,Person,measuredProperty,count,statType,measuredValue,age,Years15To64,unit,Percent
"Share of persons aged 65 
```

## Diff Excerpt

```diff
- observationAbout: dcid:wikidataId/Q211020
+ 


- observationAbout: dcid:wikidataId/Q1016922
+ 


- observationAbout: dcid:wikidataId/Q935867
+ 


- observationAbout: dcid:wikidataId/Q176201
+ 


- observationAbout: dcid:wikidataId/Q1886842
+ 


  populationType: dcid:Person
  measuredProperty: dcid:count
  statType: dcid:measuredValue
- measurementDenominator: dcid:Count_Person
- religiousOrientation: dcid:FIN_OtherReligiousGroup
+ observationAbout: dcid:country/FIN
+ religion: dcid:OtherReligion
  unit: dcid:Percent
+ value: {Number}


```

## Generation Logs

No generation logs found.
