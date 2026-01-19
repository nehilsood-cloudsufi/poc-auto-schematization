# opendataforafrica_kenya_census - Analysis

**Generated**: 2026-01-19T13:36:09.912563

## Status: NO_EVAL_RESULTS

**Reason**: I0116 17:10:23.500788 8294473856 stat_var_processor.py:2950] Error Counters: ['error-input-ignore-node-diff=1']

## Generation Notes

```markdown
# opendataforafrica_kenya_census - PVMAP Generation Notes

Generated: 2026-01-16T17:10:22.206793

Total attempts: 3

---

Looking at the data and the error logs, the critical issue is **missing `observationAbout`** - all validation warnings show "No place in SVObs" which causes 0 output rows.

Analyzing the input data:
- `REGIONID_COUNTY` contains `KE` (Kenya country code) and `KE-300-MO` (Mombasa county code)
- This is the **location column** that must map to `observationAbout`
- `SEX`, `AREA`, and `HOUSEHOLD` are **dimension properties** (categorical constraints)
- `OBS_VALUE` is the measurement column

The data structure shows:
- `T` = Total (no constraint)
- `M` = Male, `F` = Female, `I` = Intersex
- `U` = Urban, `R` = Rural
- County-level data for different regions of Kenya

```csv
key,property,value,p2,v2,p3,v3,p4,v4
REGIONID_COUNTY:KE,observationAbout,country/KEN
REGIONID_COUNTY:KE-300-MO,observationAbout,wikidataId/Q3070
TIME_PERIOD,observationDate,{Data}
OBS_VALUE,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
SEX:T,gender,
SEX:M,gender,Male
SEX:F,gender,Female
SEX:I,gender,Intersex
AREA:T,placeOfResidenceClassification,
AREA:U,placeOfResidenceClassification,Urban
AREA:R,placeOfResidenceClassification,Rural
HOUSEHOLD:T,householdType,
```

**Key fixes:**
1. **Added `observationAbout` mappings** for `REGIONID_COUNTY` values (KE → country/KEN, KE-300-MO → Mombasa)
2. **Mapped dimension columns** (`SEX`, `AREA`, `HOUSEHOLD`) as constraints with empty values for "Total"
3. **Complete StatVar properties** on `OBS_VALUE` column
4. Used `placeOfResidenceClassification` for urban/rural split (standard DC property)
5. `HOUSEHOLD:T` mapped with empty value (total households, no constraint)

```

## Generation Logs

- `logs/opendataforafrica_kenya_census/generation_20260116_144544.log`
- `logs/opendataforafrica_kenya_census/generation_20260116_165001.log`
- `logs/opendataforafrica_kenya_census/generation_20260116_170936.log`
