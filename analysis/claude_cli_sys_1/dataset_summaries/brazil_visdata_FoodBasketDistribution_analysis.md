# brazil_visdata_FoodBasketDistribution - Analysis

**Generated**: 2026-01-19T13:36:09.867520

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 95.5% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 22 |
| Nodes Auto-Generated | 22 |
| Nodes Matched | 0 |
| Nodes With Diff | 21 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 31 |
| PVs Added | 41 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - name: 5
  - alternateName: 5
  - value: 5
  - foodBasketStatus: 4
  - populationType: 3
  - unit: 2
  - p1: 1
  - prop: 1
  - householdType: 1
  - observationAbout: 1
  - observationDate: 1
  - measurementDenominator: 1
  - measuredProperty: 1

### Properties Added (Extra in LLM output)
  - populationType: 8
  - measuredProperty: 8
  - statType: 8
  - measurementMethod: 8
  - property: 1
  - property2: 1
  - property3: 1
  - property4: 1
  - observationAbout: 1
  - value: 1
  - observationDate: 1
  - scalingFactor: 1
  - unit: 1

## Generation Notes

```markdown
# brazil_visdata_FoodBasketDistribution - PVMAP Generation Notes

Generated: 2026-01-16T14:14:02.371406

Total attempts: 1

---

```csv
key,property,value,property2,value2,property3,value3,property4,value4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number}
variableMeasured:dcid:CumulativeCount_FoodBasket_NationalConfederationOfAgricultureSENAR,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,NationalConfederationOfAgricultureSENAR
variableMeasured:dcid:CumulativeCount_FoodBasket_OrganizationOfCooperativesOfBrazil,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,OrganizationOfCooperativesOfBrazil
variableMeasured:dcid:CumulativeCount_FoodBasket_NationalAssociationOfGarlicOrOnionProducers,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,NationalAssociationOfGarlicOrOnionProducers
variableMeasured:dcid:CumulativeCount_FoodBasket_BancoDoBrasilFoundation,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,BancoDoBrasilFoundation
variableMeasured:dcid:CumulativeCount_FoodBasket_CortevaAgriscience,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,CortevaAgriscience
variableMeasured:dcid:CumulativeCount_FoodBasket_NutrelliAlimentosECongelattos,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,NutrelliAlimentosECongelattos
variableMeasured:dcid:CumulativeCount_FoodBasket_SaoPauloWarehouseAndWarehouseCompanyCEAGESP,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,SaoPauloWarehouseAndWarehouseCompanyCEAGESP
variableMeasured:dcid:CumulativeCount_FoodBasket_DivineCaldoBrazil,populationType,FoodBasket,measuredProperty,cumulativeCount,statType,measuredValue,measurementMethod,DivineCaldoBrazil
unit,unit,{Data}
scalingFactor,scalingFactor,{Data}
```

**CHECKLIST:**
- [x] Keys exactly match input (case-sensitive)
- [x] Special char keys are double-quoted (none needed)
- [x] **Every value column** has: `value,{Number}`, `populationType`, `measuredProperty`, `statType`
- [x] `observationDate` format: YYYY-MM (already in correct format)
- [x] `observationAbout` uses valid DCID (country/BRA already provided)
- [x] No dynamic place construction - explicit mappings only (using {Data} for already-provided DCIDs)
- [x] #Regex uses named groups (not needed)
- [x] Note any data limitations in response

**NOTES:**
- The `observationAbout`, `observationDate`, `value` columns already contain properly formatted data that can be used directly with `{Data}` and `{Number}` placeholders
- The `variableMeasured` column contains DCID values that encode the measurement organization - these are mapped to `measurementMethod` properties for each distinct organization
- The StatVar properties (...
```

## Diff Excerpt

```diff
- 
+ populationType: dcid:FoodBasket
+ measuredProperty: dcid:cumulativeCount
+ statType: dcid:measuredValue
+ measurementMethod: dcid:DivineCaldoBrazil


- p1: dcid:v1
- prop: dcid:val
+ property: dcid:value
?     ++++          ++

+ property2: dcid:value2
+ property3: dcid:value3
+ property4: dcid:value4


- 
+ populationType: dcid:FoodBasket
+ measuredProperty: dcid:cumulativeCount
+ statType: dcid:measuredValue
+ measurementMethod: dcid:NationalAssociationOfGarlicOrOnionProducers


+ 
- populationType: dcid:FoodBasket
- householdType: dcid:ExtractiveFamily
- observationAbout: dcid:country/BRA
- observationDate: {Data}


- 
+ observationAbout: {Data}


+ 
- name: "Number of food baskets destined for extractive families"
- alternateName: "Qtde de cestas de alimentos destinadas a famílias extrativista@pt"
- foodBasketStatus: dcid:DestinedFoodBasket
- value: {Number}


- 
+ value: {Number}


- 
+ populationType: dcid:FoodBasket
+ measuredProperty: dcid:cumulativeCount
+ statType: dcid:measuredValue

```

## Generation Logs

- `logs/brazil_visdata_FoodBasketDistribution/generation_20260116_141346.log`
