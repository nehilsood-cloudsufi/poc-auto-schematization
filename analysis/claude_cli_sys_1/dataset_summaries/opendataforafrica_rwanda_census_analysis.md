# opendataforafrica_rwanda_census - Analysis

**Generated**: 2026-01-19T13:36:09.913474

## Status: NO_EVAL_RESULTS

**Reason**: Unknown - check logs for details

## Generation Notes

```markdown
# opendataforafrica_rwanda_census - PVMAP Generation Notes

Generated: 2026-01-16T14:47:50.210712

Total attempts: 1

---

Looking at this data, I can see it's already in a fully processed Data Commons format where:
- `observationAbout` is already populated with DCIDs (country/RWA)
- `observationDate` is already formatted correctly
- `variableMeasured` contains complete StatVar DCIDs (e.g., dcid:Count_Person_16OrMoreYears_InLaborForce_Male)
- `value` contains the numeric observations
- `observationPeriod` is already specified

This is **already processed output** from the Data Commons pipeline, not raw input data that needs transformation.

However, if the goal is to create a PV map that would regenerate this exact structure from the same data, here it is:

```csv
key,property,value,property2,value2,property3,value3,property4,value4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
observationPeriod,observationPeriod,{Data}
```

**Analysis:**

This is a **pass-through mapping** because:
1. All columns are already in Data Commons format
2. `variableMeasured` column contains complete StatVar DCIDs with all properties encoded
3. No transformation or decomposition is needed
4. The processor will simply copy values as-is

**Data Limitations:**
- This appears to be **already processed** data, not raw source data
- Normally, raw data would have human-readable column headers like "Male, 16+ years" instead of full DCIDs
- If this is the actual input, no schema inference is needed - it's already schematized

**If you have the original raw data** (before it was converted to this format), please provide that instead, and I can create a proper transformational PV map.

```

## Generation Logs

- `logs/opendataforafrica_rwanda_census/generation_20260116_144736.log`
