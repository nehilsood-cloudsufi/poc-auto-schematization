# census_v2_saipe - Analysis

**Generated**: 2026-01-19T13:36:09.876094

## Status: NO_EVAL_RESULTS

**Reason**: I0116 12:16:13.037533 8294473856 stat_var_processor.py:2950] Error Counters: ['error-process-format=352']

## Generation Notes

```markdown
# census_v2_saipe - PVMAP Generation Notes

Generated: 2026-01-16T12:16:12.261079

Total attempts: 3

---

Looking at the errors, the issue is clear: the processor cannot resolve the `observationAbout` place because the `#Format` expression is trying to reference `{Number:05d}` twice in the same row, but there's no captured `Number` variable when processing the `State FIPS Code` column.

The problem is in this mapping:
```csv
State FIPS Code,StateFips,{Number:02d}
District ID,#Format,"observationAbout=geoId/{StateFips}{Number:05d}"
```

The `District ID` row tries to use `{StateFips}` (which is set correctly) but then `{Number:05d}` refers to the current cell's number. However, when the processor encounters cells in the `State FIPS Code` or other columns, it doesn't have the proper context.

The fix is to properly capture both values as intermediate variables and then use them together:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6
State FIPS Code,StateFips,{Number:02d}
District ID,DistrictID,{Number:05d},#Format,"observationAbout=geoId/{StateFips}{DistrictID}"
Year,observationDate,{Data}
Estimated Total Population,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
Estimated Population 5-17,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,age,Years5To17
Estimated number of relevant children 5 to 17 years old in poverty who are related to the householder,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,age,Years5To17,povertyStatus,BelowPovertyLevelInThePast12Months
```

```

## Generation Logs

- `logs/census_v2_saipe/generation_20260116_120940.log`
- `logs/census_v2_saipe/generation_20260116_121142.log`
- `logs/census_v2_saipe/generation_20260116_121533.log`
