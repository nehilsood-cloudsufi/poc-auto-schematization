# statistics_new_zealand_new_zealand_census - Analysis

**Generated**: 2026-01-19T13:36:09.925532

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 4.2% | 🔴 Poor |
| Node Coverage | 100.0% | - |
| PV Accuracy | 24.3% | 🟠 Needs Work |
| Precision | 33.9% | - |
| Recall | 24.3% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 72 |
| Nodes Auto-Generated | 72 |
| Nodes Matched | 3 |
| Nodes With Diff | 69 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 37 |
| PVs Modified | 0 |
| PVs Deleted | 115 |
| PVs Added | 72 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 33
  - observationDate: 32
  - value: 32
  - populationType: 4
  - maritalStatus: 3
  - measuredProperty: 3
  - unit: 2
  - medicalStatus: 1
  - measurementDenominator: 1
  - gender: 1
  - scalingFactor: 1
  - statType: 1
  - ageGroupClassification: 1

### Properties Added (Extra in LLM output)
  - statType: 19
  - measuredProperty: 16
  - populationType: 10
  - maritalStatus: 3
  - natality: 3
  - unit: 3
  - migrationStatus: 3
  - mortality: 2
  - gender: 1
  - observationAbout: 1
  - observationDate: 1
  - value: 1
  - measurementQualifier: 1
  - p2: 1
  - p3: 1
  - p4: 1
  - p5: 1
  - p6: 1
  - p7: 1
  - property: 1
  - age: 1

## Generation Notes

```markdown
# statistics_new_zealand_new_zealand_census - PVMAP Generation Notes

Generated: 2026-01-16T15:02:54.332491

Total attempts: 1

---

Looking at this New Zealand demographic data, I can see it's a complex wide-format table with:
- Years as columns (1991, 1992, etc.)
- Multi-level row headers (categories and subcategories)
- Various demographic indicators
- Mix of numeric data and missing values (..)

Let me generate the PV map:

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
1991.0,observationDate,1991,value,{Number},observationAbout,country/NZL,populationType,Person,measuredProperty,count,statType,measuredValue
1992,observationDate,1992,value,{Number},observationAbout,country/NZL,populationType,Person,measuredProperty,count,statType,measuredValue
"Population(1):Estimated resident population, as at 31 December",populationType,Person,measuredProperty,count,statType,measuredValue
Population(1):Annual growth rate (percent),populationType,Person,measuredProperty,growthRate,statType,measuredValue,unit,Percent
"Population(1):Males ",populationType,Person,measuredProperty,count,statType,measuredValue,gender,Male
"Population(1):Females ",populationType,Person,measuredProperty,count,statType,measuredValue,gender,Female
Population(1):Median age (years),populationType,Person,measuredProperty,age,statType,medianValue,unit,Year
Population(1):Sex ratio (males per 100 females),populationType,Person,measuredProperty,sexRatio,statType,measuredValue,unit,MalesPer100Females
Births and deaths:Live births(2)(3),populationType,Person,measuredProperty,count,statType,measuredValue,natality,LiveBirth
Births and deaths:Deaths(3)(4),populationType,Person,measuredProperty,count,statType,measuredValue,mortality,Mortality
Births and deaths:Infant deaths,populationType,Person,measuredProperty,count,statType,measuredValue,mortality,InfantMortality,age,[0 Years]
Births and deaths:Natural increase (births minus deaths)(3),populationType,Person,measuredProperty,count,statType,measuredValue,natality,NaturalIncrease
International travel and migration(5)(6):Migrant arrivals,populationType,Person,measuredProperty,count,statType,measuredValue,migrationStatus,Arrival
International travel and migration(5)(6):Migrant departures,populationType,Person,measuredProperty,count,statType,measuredValue,migrationStatus,Departure
International travel and migration(5)(6):Net migration,populationType,Person,measuredProperty,count,statType,measuredValue,migrationStatus,NetMigration
Life expectancy at birth (years)(7):Males,populationType,Person,measuredProperty,lifeExpectancy,statType,measuredValue,unit,Year,gender,Male
Life expectancy at birth (years)(7):Females,populationType,Person,measuredProperty,lifeExpectancy,statType,measuredValue,unit,Year,gender,Female
Life expectancy at birth (years)(7):Difference (female minus male),populationType,Person,measuredProperty,lifeExpectancy,statType,measuredValue,unit,Year,measurementQualifier,FemaleMaleDifference
Fertility:Median age of women hav...
```

## Diff Excerpt

```diff
+ 
- observationAbout: dcid:country/NZL
- observationDate: 2006
- value: {Number}


  populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
  gender: dcid:Male


  populationType: dcid:Person
  measuredProperty: dcid:age
  statType: dcid:medianValue
  gender: dcid:Female
- maritalStatus: dcid:EverMarried__NewZealand_CivilUnion
?                     ----       ^^^^^^^^^^ --

+ maritalStatus: dcid:MarriedOrInCivilUnion
?                            ^^^

  unit: dcid:Year


  populationType: dcid:Person
  measuredProperty: dcid:lifeExpectancy
+ statType: dcid:measuredValue
  gender: dcid:Male
  unit: dcid:Year


+ 
- observationAbout: dcid:country/NZL
- observationDate: 2012
- value: {Number}


+ 
- observationAbout: dcid:country/NZL
- observationDate: 2009
- value: {Number}


+ 
- observationAbout: dcid:country/NZL
- observationDate: 1995
- value: {Number}



```

## Generation Logs

- `logs/statistics_new_zealand_new_zealand_census/generation_20260116_150228.log`
