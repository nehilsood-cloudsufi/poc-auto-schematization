# census_v2_sahie - Analysis

**Generated**: 2026-01-14T14:56:48.860728

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 33.3% | 🟠 Needs Work |
| Node Coverage | 88.9% | - |
| PV Accuracy | 39.4% | 🟠 Needs Work |
| Precision | 60.9% | - |
| Recall | 39.4% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 36 |
| Nodes Auto-Generated | 37 |
| Nodes Matched | 12 |
| Nodes With Diff | 20 |
| Nodes Missing (LLM missed) | 8 |
| Nodes Extra (LLM added) | 5 |
| PVs Matched | 37 |
| PVs Modified | 2 |
| PVs Deleted | 55 |
| PVs Added | 25 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - observationAbout: 10
  - statType: 5
  - value: 5
  - measuredProperty: 5
  - populationType: 5
  - age: 5
  - measurementMethod: 5
  - familyIncome: 5
  - race: 4
  - healthInsurance: 4

### Properties Added (Extra in LLM output)
  - income: 5
  - GLOBAL: 4
  - statType: 3
  - measuredProperty: 3
  - healthInsurance: 2
  - value: 2
  - populationType: 2
  - p6: 1
  - prop: 1
  - p4: 1

### Properties Modified (Different values)
  - observationDate: 1
  - age: 1

## Generation Notes

```markdown
# census_v2_sahie - PVMAP Generation Notes

Generated: 2026-01-14T00:14:02.738768

Total attempts: 3

---

Looking at the error logs, the key issue is: **"No place in SVObs"** - the `#Format` directive is not working correctly because it's trying to use `{Data}` from the `countyfips` column, but when `countyfips=000`, this represents **state-level data**, not county-level.

The data has:
- `statefips=01`, `countyfips=000` → This is Alabama state-level (should be `geoId/01`)
- The current PVMAP tries to format as `geoId/01{Data:03d}` where Data comes from countyfips, resulting in `geoId/01000` (invalid)

**Solution**: Use `statefips` to create the place DCID directly, since all rows in this sample have `countyfips=000` (state-level only).

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
year,observationDate,{Data},observationPeriod,P1Y
version,#ignore,skip
statefips,#Format,"observationAbout=geoId/{Data:02d}"
countyfips,#ignore,skip
geocat,#ignore,skip
agecat:0,GLOBAL,age
agecat:1,age,Years0To18
racecat:0,GLOBAL,race
racecat:1,race,WhiteAlone
racecat:2,race,BlackOrAfricanAmericanAlone
racecat:3,race,HispanicOrLatino
sexcat:0,GLOBAL,gender
sexcat:1,gender,Male
sexcat:2,gender,Female
iprcat:0,GLOBAL,income
iprcat:1,income,USDollarUpto138FPL
iprcat:2,income,USDollar138To400FPL
iprcat:3,income,USDollar400To500FPL
iprcat:4,income,USDollar138To400And500OrMoreFPL
iprcat:5,income,USDollar500OrMoreFPL
NIPR,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
nipr_moe,#ignore,skip
NUI,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,healthInsurance,NoHealthInsurance
nui_moe,#ignore,skip
NIC,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,healthInsurance,WithHealthInsurance
nic_moe,#ignore,skip
PCTUI,value,{Number},populationType,Person,measuredProperty,percent,statType,measuredValue,healthInsurance,NoHealthInsurance
pctui_moe,#ignore,skip
PCTIC,value,{Number},populationType,Person,measuredProperty,percent,statType,measuredValue,healthInsurance,WithHealthInsurance
pctic_moe,#ignore,skip
PCTELIG,value,{Number},populationType,Person,measuredProperty,percent,statType,measuredValue,healthInsurance,EligibleForHealthInsurance
pctelig_moe,#ignore,skip
PCTLIIC,value,{Number},populationType,Person,measuredProperty,percent,statType,measuredValue,healthInsurance,EligibleLowIncomeWithInsurance
pctliic_moe,#ignore,skip
state_name,#ignore,skip
county_name,#ignore,skip
```

**Key fixes:**
1. **`statefips`** now uses `#Format,"observationAbout=geoId/{Data:02d}"` to create state-level DCIDs (e.g., `geoId/01`)
2. **`countyfips`** is now ignored since all rows are state-level (`000`)
3. **`GLOBAL` properties** used for categorical columns (`agecat`, `racecat`, `sexcat`, `iprcat`) - when value is `0`, no constraint is applied
4. **All `_moe` columns ignored** (margin of error - not observations)
5. **Each value column** has complete properties: `value,{Number},populationType,P
```

## Diff Excerpt

```diff
  


- race: dcid:AmericanIndianAndAlaskaNativeAlone
+ 


+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- statType: dcid:marginOfError
- healthInsurance: dcid:WithHealthInsurance
- observationAbout: dcid:geoId/{Fips}
- value: {Number}


  populationType: dcid:Person
  measuredProperty: dcid:percent
  statType: dcid:measuredValue
  healthInsurance: dcid:NoHealthInsurance
- observationAbout: dcid:geoId/{Fips}
  value: {Number}


  populationType: dcid:Person
  measuredProperty: dcid:count
  statType: dcid:measuredValue
  healthInsurance: dcid:WithHealthInsurance
- observationAbout: dcid:geoId/{Fips}
  value: {Number}

```

## Generation Logs

- `logs/census_v2_sahie/generation_20260114_001245.log`
- `logs/census_v2_sahie/generation_20260113_235918.log`
- `logs/census_v2_sahie/generation_20260113_235517.log`
- `logs/census_v2_sahie/generation_20260113_235009.log`
