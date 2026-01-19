# who_covid19 - Analysis

**Generated**: 2026-01-19T13:36:09.950023

## Status: NO_EVAL_RESULTS

**Reason**: Unknown - check logs for details

## Generation Notes

```markdown
# who_covid19 - PVMAP Generation Notes

Generated: 2026-01-14T00:13:26.552938

Total attempts: 2

---

Looking at the error logs, I can see the issue: the processor found 1,917 "warning-unresolved-value-ref" warnings and 17,574 "warning-missing-property-key" warnings, resulting in 0 output rows.

The problem is that my previous PVMAP tried to reference variables across different columns that aren't available in the same lookup context. Let me create a correct PVMAP:

```csv
key,prop,value,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6,p7,v7
COUNTRY,observationAbout,country/{Data}
DATE,observationDate,{Data}
YEAR,Year,{Number}
QUARTER,Quarter,{Number}
GROUP,VaccineGroup,{Data}
COVID_VACCINE_ADM_1D,value,{Number},populationType,Vaccination,measuredProperty,count,statType,measuredValue,measurementQualifier,AdministeredFirstDose,diseasePreventedByVaccine,COVID_19
COVID_VACCINE_COV_1D,value,{Number},populationType,Person,measuredProperty,percent,statType,measuredValue,measurementQualifier,CoverageFirstDose,diseasePreventedByVaccine,COVID_19
POPULATION,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
ad_chronic,vaccineTargetPopulation,AdultsWithChronicConditions
hcw,vaccineTargetPopulation,HealthcareWorkers
```

**Key changes from previous attempt:**

1. **Removed cross-column variable references** - The processor cannot reference `{Year}` and `{Quarter}` from DATE column lookups because those variables are only available in their own row context
2. **Simplified date mapping** - Used `DATE,observationDate,{Data}` directly since dates are already in YYYY-MM-DD format
3. **Fixed value columns** - Each value column (COVID_VACCINE_ADM_1D, COVID_VACCINE_COV_1D, POPULATION) now has all required StatVar properties
4. **Added vaccine-specific properties**:
   - `diseasePreventedByVaccine,COVID_19` to indicate these are COVID vaccinations
   - `measurementQualifier` to distinguish between administered doses vs coverage percentage
5. **Mapped GROUP values** to `vac...
```

## Generation Logs

- `logs/who_covid19/generation_20260113_234106.log`
- `logs/who_covid19/generation_20260114_001245.log`
- `logs/who_covid19/generation_20260115_134545.log`
