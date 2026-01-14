# Auto-Schematization Evaluation Analysis

**Generated**: 2026-01-14 14:58:14

---

## Executive Summary

This report analyzes the evaluation results of auto-generated Property-Value Maps (PVMAPs) against human-created ground truth mappings across 38 datasets.

### Key Statistics

| Metric | Value |
|--------|-------|
| **Total Datasets Evaluated** | 38 |
| **Complete Evaluations** | 35 |
| **Missing/Failed Evaluations** | 3 |
| **Average Node Accuracy** | 12.3% |
| **Average PV Accuracy** | 24.8% |
| **Average Precision** | 39.2% |
| **Average Recall** | 24.8% |

### Best & Worst Performers

| Category | Dataset | PV Accuracy |
|----------|---------|-------------|
| **Best** | undata | 90.3% |
| **Worst** | india_ndap_india_nss_health_ailments | 0.0% |

---

## Methodology

### Evaluation Approach

The evaluation uses a diff-based comparison approach that:
1. Parses both auto-generated and ground truth PVMAPs into MCF (Meta Content Format) nodes
2. Compares node keys (column headers/values) between the two maps
3. For matching keys, compares individual property-value pairs
4. Calculates accuracy metrics based on matches, differences, additions, and deletions

### Metrics Definitions

#### Node-Level Metrics

| Metric | Description |
|--------|-------------|
| **nodes-ground-truth** | Total keys in human-created pvmap (baseline) |
| **nodes-auto-generated** | Total keys in LLM-generated pvmap |
| **nodes-matched** | Keys with IDENTICAL property-values in both |
| **nodes-with-diff** | Keys in both but with DIFFERENT property-values |
| **nodes-missing-in-mcf2** | Keys in ground truth but NOT in LLM output (LLM missed) |
| **nodes-missing-in-mcf1** | Keys in LLM output but NOT in ground truth (extra keys) |

#### Property-Value (PV) Level Metrics

| Metric | Description |
|--------|-------------|
| **PVs-matched** | Property-value pairs that match EXACTLY |
| **pvs-modified** | Properties in both but with DIFFERENT values |
| **pvs-added** | Properties in LLM output but NOT in ground truth |
| **pvs-deleted** | Properties in ground truth but NOT in LLM output |

### Accuracy Calculations

```
Node Accuracy = (nodes-matched / nodes-ground-truth) × 100%
Node Coverage = ((nodes-matched + nodes-with-diff) / nodes-ground-truth) × 100%
PV Accuracy = PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%
Precision = (PVs-matched + pvs-modified) / (PVs-matched + pvs-modified + pvs-added) × 100%
Recall = PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%
```

### Quality Benchmarks

| Metric | Excellent | Good | Needs Work | Poor |
|--------|-----------|------|------------|------|
| Node Accuracy | >80% | 50-80% | 20-50% | <20% |
| PV Accuracy | >70% | 40-70% | 20-40% | <20% |
| pvs-deleted | 0 | 1-5 | 6-20 | >20 |
| nodes-missing-in-mcf2 | 0 | 1-3 | 4-10 | >10 |

---

## Complete Results Table

| Dataset | Node Acc % | Node Cov % | PV Acc % | Precision % | Recall % |
|---------|------------|------------|----------|-------------|----------|
| undata | 91.0 | 95.5 | 90.3 | 92.4 | 90.3 |
| bis_bis_central_bank_policy_rate | 100.0* | 285.7 | 73.1 | 61.3 | 73.1 |
| zurich_wir_2552_wiki | 10.0 | 100.0 | 64.3 | 55.1 | 64.3 |
| us_newyork_ny_diabetes | 25.0 | 100.0 | 53.8 | 57.1 | 53.8 |
| world_bank_commodity_market | 0.0 | 76.6 | 48.8 | 22.9 | 48.8 |
| inpe_fire | 12.5 | 45.8 | 44.3 | 46.6 | 44.3 |
| census_v2_sahie | 33.3 | 88.9 | 39.4 | 60.9 | 39.4 |
| zurich_bev_3903_sex_wiki | 16.7 | 66.7 | 37.5 | 41.7 | 37.5 |
| zurich_bev_4031_sex_wiki | 33.3 | 83.3 | 37.5 | 26.1 | 37.5 |
| bev_3240_wiki | 0.0 | 75.0 | 33.3 | 60.0 | 33.3 |
| us_education_new_york_education | 6.4 | 53.2 | 33.3 | 44.4 | 33.3 |
| zurich_bev_3240_wiki | 25.0 | 100.0 | 33.3 | 50.0 | 33.3 |
| zurich_bev_4031_wiki | 25.0 | 100.0 | 33.3 | 50.0 | 33.3 |
| bis | 28.6 | 57.1 | 25.0 | 22.2 | 25.0 |
| zurich_bev_4031_hel_wiki | 16.7 | 100.0 | 25.0 | 41.7 | 25.0 |
| ccd_enrollment | 15.8 | 65.8 | 20.4 | 47.2 | 20.4 |
| doctoratedegreeemployment | 12.9 | 61.3 | 20.0 | 34.7 | 20.0 |
| zurich_bev_3903_hel_wiki | 0.0 | 50.0 | 20.0 | 36.4 | 20.0 |
| finland_census | 0.0 | 15.0 | 16.4 | 64.3 | 16.4 |
| school_algebra1 | 0.0 | 37.2 | 15.7 | 29.9 | 15.7 |
| cdc_social_vulnerability_index | 2.4 | 33.3 | 15.5 | 24.5 | 15.5 |
| ncses_ncses_demographics_seh_import | 44.7 | 105.3 | 14.6 | 64.6 | 14.6 |
| oecd_wastewater_treatment | 7.7 | 38.5 | 12.5 | 39.1 | 12.5 |
| india_ndap | 3.3 | 10.0 | 12.1 | 29.4 | 12.1 |
| zurich_bev_3903_age10_wiki | 0.0 | 26.7 | 11.8 | 20.0 | 11.8 |
| us_urban_school_teachers | 2.9 | 31.4 | 8.9 | 32.8 | 8.9 |
| fbi_fbigovcrime | 0.0 | 5.3 | 8.7 | 25.8 | 8.7 |
| us_urban_school_covid_directional_indicators | 0.0 | 33.3 | 7.1 | 6.7 | 7.1 |
| us_urban_school_maths_and_science_enrollment | 0.0 | 7.0 | 4.2 | 36.3 | 4.2 |
| nyu_diabetes_texas | 0.0 | 4.7 | 4.1 | 28.1 | 4.1 |
| us_cdc_single_race | 0.0 | 2.0 | 3.0 | 13.9 | 3.0 |
| us_crash_fars_crashdata | 3.7 | 10.3 | 0.7 | 39.1 | 0.7 |
| us_bls_bls_ces | 0.4 | 1.3 | 0.4 | 6.6 | 0.4 |
| us_bls_bls_ces_state | 0.3 | 0.5 | 0.1 | 56.0 | 0.1 |
| india_ndap_india_nss_health_ailments | 0.0 | 5.4 | 0.0 | 3.1 | 0.0 |

*Note: Asterisk (*) indicates node accuracy exceeded 100% due to more matched nodes than ground truth nodes (calculation anomaly).*

---

## Datasets Without Evaluation Results

- **commerce_eda**: no_eval_results
- **india_nfhs**: no_eval_results
- **who_covid19**: no_diff_results_json

---

## Failure Pattern Analysis

### Common Missing Properties (pvs-deleted)

The following properties are most frequently missing from auto-generated PVMAPs:

| Property | Total Deletions |
|----------|----------------|
| name | 2555 |
| industry | 2263 |
| observationAbout | 2052 |
| populationType | 1551 |
| value | 740 |
| measuredProperty | 658 |
| statType | 546 |
| unit | 519 |
| measurementMethod | 518 |
| gender | 503 |
| measurementQualifier | 491 |
| race | 341 |
| schoolGradeLevel | 330 |
| establishmentOwnership | 285 |
| schoolSubject | 283 |


### Common Extra Properties (pvs-added)

Properties frequently added by LLM but not in ground truth:

| Property | Total Additions |
|----------|----------------|
| statType | 359 |
| measuredProperty | 348 |
| populationType | 299 |
| observationAbout | 164 |
| courseContent | 123 |
| gradeLevel | 121 |
| observationDate | 100 |
| value | 86 |
| unit | 79 |
| observationPeriod | 78 |
| courseStatus | 60 |
| causeOfDeath | 31 |
| p4 | 22 |
| gender | 22 |
| age | 21 |


---

## Failure Categories

Based on analysis of generation logs and diffs, failures fall into these categories:

### Category 1: Processor Limitations
Issues where the PVMAP syntax is correct but the processor doesn't support it:
- `#Format` directive not resolving `observationAbout`
- Global static properties not supported
- Complex regex patterns not matching correctly

### Category 2: Data Quality Issues
Issues caused by source data problems:
- Missing or malformed FIPS codes
- Inconsistent country code formats (ISO2 vs ISO3)
- Ambiguous column headers

### Category 3: Data Structure Issues
Issues where data format doesn't fit PVMAP model:
- Multi-row headers (crosstab format)
- Carry-forward values (state appears once for multiple rows)
- Wide data format requiring column-to-row transformation

### Category 4: Pipeline Configuration
Issues with dataset setup:
- Missing input data files
- Missing metadata.csv files
- Incorrect file paths

---

## Recommendations

### For Prompt Improvements (Limited Impact)

These may help marginally but won't fix core issues:

1. **Add clearer FIPS formatting examples** - Show how to pad FIPS codes to 5 digits
2. **Document `#Format` limitations** - Clarify that `#Format` doesn't work for `observationAbout`
3. **Add crosstab detection warnings** - Help LLM identify and flag unsupported formats
4. **Provide more country code examples** - Show ISO2, ISO3, and country name mappings

### For Processor/System Fixes (Required)

These require code changes:

1. **Support `#Format` for `observationAbout`**
   - Modify `property_value_mapper.py` to process `#Format` directives that set `observationAbout`

2. **Support global static properties**
   - Add syntax like `,observationAbout,country/USA` for datasets without place columns

3. **Better `#Regex` constraints**
   - Add option to restrict regex matching to specific columns
   - Prevent regex from matching numeric data values

### Per-Dataset Fixes Required

| Dataset | Category | Required Fix |
|---------|----------|--------------|
| census_v2_sahie | Processor | Add explicit geoId mappings for each state FIPS |
| us_cdc_single_race | Data Quality | Preprocess to add state prefix to county codes |
| ncses_ncses_demographics_seh_import | Data Structure | Restructure data to single header row, add place column |
| fbi_fbigovcrime | Data Structure | Handle carry-forward state values |
| us_bls_bls_ces | Data Structure | Map Series ID to proper employment properties |
| us_bls_bls_ces_state | Data Structure | Map Series ID and state codes |


---

## Individual Dataset Reports

Detailed analysis for each dataset is available in the `dataset_summaries/` directory:

- [bev_3240_wiki](dataset_summaries/bev_3240_wiki_analysis.md)
- [bis](dataset_summaries/bis_analysis.md)
- [bis_bis_central_bank_policy_rate](dataset_summaries/bis_bis_central_bank_policy_rate_analysis.md)
- [ccd_enrollment](dataset_summaries/ccd_enrollment_analysis.md)
- [cdc_social_vulnerability_index](dataset_summaries/cdc_social_vulnerability_index_analysis.md)
- [census_v2_sahie](dataset_summaries/census_v2_sahie_analysis.md)
- [commerce_eda](dataset_summaries/commerce_eda_analysis.md)
- [doctoratedegreeemployment](dataset_summaries/doctoratedegreeemployment_analysis.md)
- [fbi_fbigovcrime](dataset_summaries/fbi_fbigovcrime_analysis.md)
- [finland_census](dataset_summaries/finland_census_analysis.md)
- [india_ndap](dataset_summaries/india_ndap_analysis.md)
- [india_ndap_india_nss_health_ailments](dataset_summaries/india_ndap_india_nss_health_ailments_analysis.md)
- [india_nfhs](dataset_summaries/india_nfhs_analysis.md)
- [inpe_fire](dataset_summaries/inpe_fire_analysis.md)
- [ncses_ncses_demographics_seh_import](dataset_summaries/ncses_ncses_demographics_seh_import_analysis.md)
- [nyu_diabetes_texas](dataset_summaries/nyu_diabetes_texas_analysis.md)
- [oecd_wastewater_treatment](dataset_summaries/oecd_wastewater_treatment_analysis.md)
- [school_algebra1](dataset_summaries/school_algebra1_analysis.md)
- [undata](dataset_summaries/undata_analysis.md)
- [us_bls_bls_ces](dataset_summaries/us_bls_bls_ces_analysis.md)
- [us_bls_bls_ces_state](dataset_summaries/us_bls_bls_ces_state_analysis.md)
- [us_cdc_single_race](dataset_summaries/us_cdc_single_race_analysis.md)
- [us_crash_fars_crashdata](dataset_summaries/us_crash_fars_crashdata_analysis.md)
- [us_education_new_york_education](dataset_summaries/us_education_new_york_education_analysis.md)
- [us_newyork_ny_diabetes](dataset_summaries/us_newyork_ny_diabetes_analysis.md)
- [us_urban_school_covid_directional_indicators](dataset_summaries/us_urban_school_covid_directional_indicators_analysis.md)
- [us_urban_school_maths_and_science_enrollment](dataset_summaries/us_urban_school_maths_and_science_enrollment_analysis.md)
- [us_urban_school_teachers](dataset_summaries/us_urban_school_teachers_analysis.md)
- [who_covid19](dataset_summaries/who_covid19_analysis.md)
- [world_bank_commodity_market](dataset_summaries/world_bank_commodity_market_analysis.md)
- [zurich_bev_3240_wiki](dataset_summaries/zurich_bev_3240_wiki_analysis.md)
- [zurich_bev_3903_age10_wiki](dataset_summaries/zurich_bev_3903_age10_wiki_analysis.md)
- [zurich_bev_3903_hel_wiki](dataset_summaries/zurich_bev_3903_hel_wiki_analysis.md)
- [zurich_bev_3903_sex_wiki](dataset_summaries/zurich_bev_3903_sex_wiki_analysis.md)
- [zurich_bev_4031_hel_wiki](dataset_summaries/zurich_bev_4031_hel_wiki_analysis.md)
- [zurich_bev_4031_sex_wiki](dataset_summaries/zurich_bev_4031_sex_wiki_analysis.md)
- [zurich_bev_4031_wiki](dataset_summaries/zurich_bev_4031_wiki_analysis.md)
- [zurich_wir_2552_wiki](dataset_summaries/zurich_wir_2552_wiki_analysis.md)


---

## Appendix: Files Analyzed

### Source Directories

| Type | Path |
|------|------|
| Eval Results | `output/*/eval_results/*/diff_results.json` |
| Diff Details | `output/*/eval_results/*/diff.txt` |
| Generation Notes | `output/*/generation_notes.md` |
| Pipeline Logs | `logs/*/generation_*.log` |

### Generated Files

| Type | Path |
|------|------|
| This Report | `analysis/Auto_Schematization_Evaluation_Analysis.md` |
| Dataset Summaries | `analysis/dataset_summaries/*.md` |
| Raw Metrics JSON | `analysis/raw_data/all_metrics.json` |

---

*Report generated on 2026-01-14 14:58:14*
