# us_hbcu_data - Analysis

**Generated**: 2026-01-19T13:36:09.941449

## Status: NO_EVAL_RESULTS

**Reason**: I0116 17:26:32.682914 8294473856 stat_var_processor.py:2920] Processing data ['/Users/nehilsood/work/poc-auto-schematization/input_new/us_hbcu_data/test_data/combined_input.csv'] into /Users/nehilsood

## Generation Notes

```markdown
# us_hbcu_data - PVMAP Generation Notes

Generated: 2026-01-16T17:26:31.871544

Total attempts: 3

---

Looking at the errors, the critical issue is clear: **ALL observations are missing `observationAbout`** (the geographic/organizational entity being measured). The logs show repeated warnings:

```
No place in SVObs
Unable to resolve SVObs place
```

This is HBCU enrollment data - the observations are about **United States** as a whole (aggregated national statistics for HBCUs). The data doesn't have place columns because it's already national-level data.

Additionally, I notice:
1. Row labels like "Total enrollment, fall 2022", "Males, Black", "Females" need to be parsed
2. Need to extract year from row labels (2022, 2010, 2000, 1990)
3. Need special handling for the footnote `\1\` in "Doctor's\1\" which caused CSV parsing issues in previous attempt

```csv
key,property,value,p2,v2,p3,v3,p4,v4,p5,v5
Total,observationAbout,country/USA,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,institutionCategory,HistoricallyBlackCollegeOrUniversity
Public,institutionControl,Public,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,institutionCategory,HistoricallyBlackCollegeOrUniversity,observationAbout,country/USA
Private,institutionControl,Private,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,institutionCategory,HistoricallyBlackCollegeOrUniversity,observationAbout,country/USA
4-year,institutionLevel,FourYear,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,institutionCategory,HistoricallyBlackCollegeOrUniversity,observationAbout,country/USA
2-year,institutionLevel,TwoYear,value,{Number},populationType,Student,measuredProperty,count,statType,measuredValue,institutionCategory,HistoricallyBlackCollegeOrUniversity,observationAbout,country/USA
"Selected statistics:Number of institutions, fall 2022",#Regex,"fall (?P<Year>[0-9]{4})",observa...
```

## Generation Logs

- `logs/us_hbcu_data/generation_20260116_151710.log`
- `logs/us_hbcu_data/generation_20260116_165002.log`
- `logs/us_hbcu_data/generation_20260116_172516.log`
