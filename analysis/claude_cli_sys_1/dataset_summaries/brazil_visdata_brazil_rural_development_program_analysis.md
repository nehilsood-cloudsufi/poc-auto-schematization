# brazil_visdata_brazil_rural_development_program - Analysis

**Generated**: 2026-01-19T13:36:09.868658

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 92.9% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 14 |
| Nodes Auto-Generated | 14 |
| Nodes Matched | 0 |
| Nodes With Diff | 13 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 24 |
| PVs Added | 19 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - name: 4
  - alternateName: 4
  - value: 4
  - gender: 3
  - observationDate: 1
  - p1: 1
  - p2: 1
  - prop: 1
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - benefitProgram: 1
  - observationAbout: 1

### Properties Added (Extra in LLM output)
  - populationType: 2
  - measuredProperty: 2
  - statType: 2
  - beneficiaryProgram: 2
  - familyType: 2
  - property: 1
  - property2: 1
  - property3: 1
  - property4: 1
  - property5: 1
  - property6: 1
  - observationAbout: 1
  - observationDate: 1
  - value: 1

## Generation Notes

```markdown
# brazil_visdata_brazil_rural_development_program - PVMAP Generation Notes

Generated: 2026-01-16T14:15:23.072021

Total attempts: 1

---

Looking at the input data, I can see this is **already in Data Commons format** with:
- Place identifiers with `dcid:` prefix
- Dates in YYYY-MM format
- Values (numeric)
- Variable measured with `dcid:` prefix (StatVar identifiers)

The data uses `variableMeasured` which contains complete StatVar DCIDs, so we don't need to construct StatVar properties from scratch.

## Key Observations:
1. **observationAbout** - Already has `dcid:` prefix, needs cleaning
2. **observationDate** - Already in correct format (YYYY-MM)
3. **value** - Numeric values ready to use
4. **variableMeasured** - Contains full StatVar DCIDs that encode:
   - `Count_Person_BrazilRuralDevelopmentProgram_IndigenousFamily`
   - `Count_Person_BrazilRuralDevelopmentProgram_FarmingFamily`

Since `variableMeasured` is provided but the instruction says "NEVER map variableMeasured", I need to extract the StatVar properties from these identifiers and map them properly.

## Analysis of StatVars:
- **populationType**: Person
- **measuredProperty**: count  
- **statType**: measuredValue
- **Constraints**: 
  - beneficiaryProgram: BrazilRuralDevelopmentProgram
  - familyType: IndigenousFamily OR FarmingFamily

```csv
key,property,value,property2,value2,property3,value3,property4,value4,property5,value5,property6,value6
observationAbout,#Regex,"dcid:(?P<DCID>.*)",observationAbout,{DCID}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured:dcid:Count_Person_BrazilRuralDevelopmentProgram_IndigenousFamily,populationType,Person,measuredProperty,count,statType,measuredValue,beneficiaryProgram,BrazilRuralDevelopmentProgram,familyType,IndigenousFamily
variableMeasured:dcid:Count_Person_BrazilRuralDevelopmentProgram_FarmingFamily,populationType,Person,measuredProperty,count,statType,measuredValue,beneficiaryProgram,BrazilRuralDevelopmentProgram,familyType,FarmingFamily
```

**Notes:**
- The `observationAbout` column uses regex to strip the `dcid:` prefix and extract the actual DCID
- The `variableMeasured` values map to complete StatVar definitions with all required properties
- Empty `observationPeriod` and `unit` columns are left unmapped (processor will handle empty values)

```

## Diff Excerpt

```diff
- observationDate: {Data}
+ 


- p1: dcid:v1
- p2: dcid:v2
- prop: dcid:val
+ property: dcid:value
?     ++++          ++

+ property2: dcid:value2
+ property3: dcid:value3
+ property4: dcid:value4
+ property5: dcid:value5
+ property6: dcid:value6


+ 
- name: "Number of women beneficiaries of the Rural Development Program"
- alternateName: "Nº de mulheres beneficiárias do Programa Fomento Rural@pt"
- gender: dcid:Female
- value: {Number}


- 
+ populationType: dcid:Person
+ measuredProperty: dcid:count
+ statType: dcid:measuredValue
+ beneficiaryProgram: dcid:BrazilRuralDevelopmentProgram
+ familyType: dcid:FarmingFamily


- 
+ observationAbout: {DCID}


+ 
- populationType: dcid:Person
- measuredProperty: dcid:count
- statType: dcid:measuredValue
- benefitProgram: dcid:Brazil_RuralDevelopmentProgram
- observationAbout: {Data}


+ 
- name: "Number of men benefiting from the Rural Development Program"
- alternateName: "Nº de homens beneficiários do Programa Fomento Rural@pt"
- gender: dcid:Male
- value: {Number}


```

## Generation Logs

- `logs/brazil_visdata_brazil_rural_development_program/generation_20260116_141507.log`
