# ntia_internet_use_survey - Analysis

**Generated**: 2026-01-19T13:36:09.905180

## Quality Summary

| Metric | Value | Rating |
|--------|-------|--------|
| Node Accuracy | 0.0% | 🔴 Poor |
| Node Coverage | 99.4% | - |
| PV Accuracy | 0.0% | 🔴 Poor |
| Precision | 0.0% | - |
| Recall | 0.0% | - |

## Raw Metrics

| Metric | Value |
|--------|-------|
| Nodes Ground Truth | 181 |
| Nodes Auto-Generated | 181 |
| Nodes Matched | 0 |
| Nodes With Diff | 180 |
| Nodes Missing (LLM missed) | 0 |
| Nodes Extra (LLM added) | 0 |
| PVs Matched | 0 |
| PVs Modified | 0 |
| PVs Deleted | 627 |
| PVs Added | 12 |

## Property Analysis

### Properties Deleted (Missing in LLM output)
  - name: 86
  - measuredProperty: 86
  - observationAbout: 86
  - value: 86
  - DescriptionVar: 54
  - isInternetUser: 46
  - observationDate: 26
  - internetUsageLocation: 21
  - internetUsagePurpose: 16
  - populationType: 8
  - internetSubscriptionType: 8
  - electronicGadgetUsed: 7
  - reasonNotUsingInternetAtHome: 6
  - factorForInternetService: 6
  - householderAge: 6
  - householderEducationalAttainment: 6
  - householderGender: 6
  - householderRace: 6
  - householderWorkStatus: 6
  - income: 5
  - Race: 5
  - Age: 5
  - armedForcesStatus: 4
  - EducationalAttainment: 4
  - placeOfResidenceClassification: 3
  - EmploymentStatus: 3
  - Gender: 2
  - ethnicity: 2
  - schoolEnrollment: 2
  - educationalAttainment: 2
  - employmentStatus: 2
  - gender: 2
  - race: 2
  - veteranStatus: 2
  - disabilityStatus: 2
  - institutionalization: 2
  - age: 2
  - prop: 1
  - computerUsageLocation: 1
  - hasComputer: 1
  - residenceType: 1

### Properties Added (Extra in LLM output)
  - observationDate: 1
  - p2: 1
  - p3: 1
  - p4: 1
  - property: 1
  - populationType: 1
  - measuredProperty: 1
  - statType: 1
  - householdStatus: 1
  - placeOfResidenceClassification: 1
  - value: 1
  - observationAbout: 1

## Generation Notes

```markdown
# ntia_internet_use_survey - PVMAP Generation Notes

Generated: 2026-01-16T14:37:47.261978

Total attempts: 1

---

```csv
key,property,value,p2,v2,p3,v3,p4,v4
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
value,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue,householdStatus,NonInstitutionalized,placeOfResidenceClassification,Household
```

**Analysis:**

1. **Pre-structured data**: The input is already in flat observation format with DCIDs explicitly provided
2. **Column mappings**:
   - `observationAbout` → already contains valid DCIDs (country/USA, geoId/01, etc.)
   - `observationDate` → already in YYYY-MM format
   - `value` → numeric counts with full StatVar properties
   - `variableMeasured` → **IGNORED** (processor auto-constructs this from properties)

3. **StatVar properties** (decoded from `dcid:Count_Household_NonInstitutionalized`):
   - `populationType`: Person
   - `measuredProperty`: count
   - `statType`: measuredValue
   - `householdStatus`: NonInstitutionalized
   - `placeOfResidenceClassification`: Household

4. **No transformations needed**: All columns contain correctly formatted values that can be passed through directly using `{Data}` and `{Number}` placeholders

**Checklist:**
- [x] Keys match input columns exactly
- [x] No special characters requiring quoting
- [x] Value column has all required properties
- [x] observationDate already in valid format
- [x] observationAbout already contains valid DCIDs
- [x] No dynamic place construction needed
- [x] variableMeasured column appropriately ignored

```

## Diff Excerpt

```diff
+ 
- name: "{DescriptionVar}, Urban"
- measuredProperty: dcid:count
- observationAbout: dcid:country/USA
- placeOfResidenceClassification: dcid:Urban
- value: {Number}


- 
+ observationDate: {Data}


- observationDate: 2030-11
+ 


+ 
- name: "{DescriptionVar}"
- measuredProperty: dcid:count
- observationAbout: dcid:geoId/11
- value: {Number}


+ 
- DescriptionVar: "Main Reason for Household Not Online at Home: No/Inadequate Computer"
- isInternetUser: dcid:True
- reasonNotUsingInternetAtHome: dcid:InternetInadequateComputer


+ 
- name: "{DescriptionVar}"
- measuredProperty: dcid:count
- observationAbout: dcid:geoId/56
- value: {Number}


+ 
- name: "{DescriptionVar}"
- measuredProperty: dcid:count
- observationAbout: dcid:geoId/31
- value: {Number}


+ 
- DescriptionVar: "Mobility is Most Important Factor for Home Internet Service"
- factorForInternetService: dcid:FactorForHomeInternetMobility
- internetUsageLocation: dcid:Home
- isInternetUser: dcid:True



```

## Generation Logs

- `logs/ntia_internet_use_survey/generation_20260116_143736.log`
