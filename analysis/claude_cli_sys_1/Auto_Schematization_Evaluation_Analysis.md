# Auto-Schematization Evaluation Analysis

**Generated**: 2026-01-19 13:36:09

---

## Executive Summary

This report analyzes the evaluation results of auto-generated Property-Value Maps (PVMAPs) against human-created ground truth mappings across 82 datasets.

### Key Statistics

| Metric | Value |
|--------|-------|
| **Total Datasets Evaluated** | 82 |
| **Complete Evaluations** | 69 |
| **Missing/Failed Evaluations** | 13 |
| **Average Node Accuracy** | 9.4% |
| **Average PV Accuracy** | 14.7% |
| **Average Precision** | 23.2% |
| **Average Recall** | 14.7% |

### Best & Worst Performers

| Category | Dataset | PV Accuracy |
|----------|---------|-------------|
| **Best** | undata | 90.3% |
| **Worst** | brazil_sidra_ibge | 0.0% |

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
| bis_bis_central_bank_policy_rate | 228.6 | 285.7 | 73.1 | 61.3 | 73.1 |
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
| statistics_new_zealand_new_zealand_census | 4.2 | 100.0 | 24.3 | 33.9 | 24.3 |
| crdc_instructional_wifi_devices | 0.0 | 90.0 | 23.1 | 8.8 | 23.1 |
| ccd_enrollment | 15.8 | 65.8 | 20.4 | 47.2 | 20.4 |
| doctoratedegreeemployment | 12.9 | 61.3 | 20.0 | 34.7 | 20.0 |
| zurich_bev_3903_hel_wiki | 0.0 | 50.0 | 20.0 | 36.4 | 20.0 |
| child_birth | 0.0 | 94.1 | 18.2 | 14.8 | 18.2 |
| ipeds | 0.0 | 95.8 | 16.7 | 0.9 | 16.7 |
| finland_census | 0.0 | 15.0 | 16.4 | 64.3 | 16.4 |
| school_algebra1 | 0.0 | 37.2 | 15.7 | 29.9 | 15.7 |
| cdc_social_vulnerability_index | 2.4 | 33.3 | 15.5 | 24.5 | 15.5 |
| ireland_census | 0.0 | 93.8 | 15.4 | 18.2 | 15.4 |
| ncses_ncses_demographics_seh_import | 44.7 | 105.3 | 14.6 | 64.6 | 14.6 |
| oecd_wastewater_treatment | 7.7 | 38.5 | 12.5 | 39.1 | 12.5 |
| india_ndap | 3.3 | 10.0 | 12.1 | 29.4 | 12.1 |
| school_finance | 0.0 | 93.8 | 11.8 | 18.2 | 11.8 |
| zurich_bev_3903_age10_wiki | 0.0 | 26.7 | 11.8 | 20.0 | 11.8 |
| us_urban_school_teachers | 2.9 | 31.4 | 8.9 | 32.8 | 8.9 |
| fbi_fbigovcrime | 0.0 | 5.3 | 8.7 | 25.8 | 8.7 |
| brfss_nchs_asthma_prevalence | 0.0 | 98.9 | 7.9 | 7.6 | 7.9 |
| oecd_quarterly_gdp | 0.0 | 97.0 | 7.7 | 3.4 | 7.7 |
| us_urban_school_covid_directional_indicators | 0.0 | 33.3 | 7.1 | 6.7 | 7.1 |
| southkorea_statistics_education | 0.0 | 98.9 | 4.8 | 2.6 | 4.8 |
| us_urban_school_maths_and_science_enrollment | 0.0 | 7.0 | 4.2 | 36.3 | 4.2 |
| nyu_diabetes_texas | 0.0 | 4.7 | 4.1 | 28.1 | 4.1 |
| southkorea_statistics_demographics | 0.0 | 97.7 | 4.1 | 37.5 | 4.1 |
| southkorea_statistics_health | 0.0 | 99.6 | 3.7 | 0.5 | 3.7 |
| india_rbistatedomesticproduct | 0.0 | 98.1 | 3.5 | 33.3 | 3.5 |
| us_cdc_single_race | 0.0 | 2.0 | 3.0 | 13.9 | 3.0 |
| us_bachelors_degree_data | 0.0 | 99.2 | 2.7 | 2.7 | 2.7 |
| us_bls_us_cpi | 0.0 | 98.7 | 2.2 | 2.1 | 2.2 |
| us_nces | 0.0 | 97.8 | 2.2 | 17.6 | 2.2 |
| us_crash_fars_crashdata | 3.7 | 10.3 | 0.7 | 39.1 | 0.7 |
| fao_currency_and_exchange_rate | 0.0 | 99.7 | 0.5 | 23.1 | 0.5 |
| google_sustainability_financial_incentives | 0.0 | 99.7 | 0.4 | 3.1 | 0.4 |
| us_bls_bls_ces | 0.4 | 1.3 | 0.4 | 6.6 | 0.4 |
| us_bls_bls_ces_state | 0.3 | 0.5 | 0.1 | 56.0 | 0.1 |
| brazil_sidra_ibge | 0.0 | 98.5 | 0.0 | 0.0 | 0.0 |
| brazil_visdata_FoodBasketDistribution | 0.0 | 95.5 | 0.0 | 0.0 | 0.0 |
| brazil_visdata_brazil_rural_development_program | 0.0 | 92.9 | 0.0 | 0.0 | 0.0 |
| crdc_import_crdc_harassment_or_bullying | 0.0 | 99.7 | 0.0 | 0.0 | 0.0 |
| india_ndap_india_nss_health_ailments | 0.0 | 5.4 | 0.0 | 3.1 | 0.0 |
| mexico_subnational_population_statistics_mexico_census_aa2 | 0.0 | 98.6 | 0.0 | 0.0 | 0.0 |
| ncses_median_annual_salary | 0.0 | 97.4 | 0.0 | 0.0 | 0.0 |
| ncses_research_doctorate_recipients | 0.0 | 97.6 | 0.0 | 0.0 | 0.0 |
| ntia_internet_use_survey | 0.0 | 99.4 | 0.0 | 0.0 | 0.0 |
| oecd_regional_education | 0.0 | 95.7 | 0.0 | 0.0 | 0.0 |
| opendataforafrica_ethiopia_statistics | 0.0 | 95.2 | 0.0 | 0.0 | 0.0 |
| school_retention | 0.0 | 99.8 | 0.0 | 0.0 | 0.0 |
| singapore_census | 0.0 | 99.0 | 0.0 | 0.0 | 0.0 |
| southkorea_statistics_employment | 0.0 | 97.9 | 0.0 | 0.0 | 0.0 |
| uae_bayanat | 0.0 | 94.7 | 0.0 | 0.0 | 0.0 |
| us_bls_cpi_category | 0.0 | 99.5 | 0.0 | 0.0 | 0.0 |
| us_federal_reserve_h15_interest_rates | 0.0 | 91.7 | 0.0 | 0.0 | 0.0 |
| usa_dol | 0.0 | 98.6 | 0.0 | 0.0 | 0.0 |

*Note: Asterisk (*) indicates node accuracy exceeded 100% due to more matched nodes than ground truth nodes (calculation anomaly).*

---

## Datasets Without Evaluation Results

- **census_v2_saipe**: no_eval_results - I0116 12:16:13.037533 8294473856 stat_var_processor.py:2950] Error Counters: ['error-process-format=
- **commerce_eda**: no_eval_results - Unknown - check logs for details
- **database_on_indian_economy_india_rbi_state_statistics**: no_eval_results - 2026-01-16 17:00:56,251 - INFO - Added error feedback to prompt
- **fema**: no_eval_results - Unknown - check logs for details
- **gdp_by_county_metro_and_other_areas**: no_eval_results - 2026-01-16 17:02:32,468 - INFO - Added error feedback to prompt
- **india_nfhs**: no_eval_results - Unknown - check logs for details
- **nyu_diabetes_tennessee**: no_eval_results - 2026-01-16 17:04:28,354 - INFO - Added error feedback to prompt
- **opendataforafrica_kenya_census**: no_eval_results - I0116 17:10:23.500788 8294473856 stat_var_processor.py:2950] Error Counters: ['error-input-ignore-no
- **opendataforafrica_rwanda_census**: no_eval_results - Unknown - check logs for details
- **us_census**: no_eval_results - 2026-01-16 17:24:56,842 - INFO - Added error feedback to prompt
- **us_hbcu_data**: no_eval_results - I0116 17:26:32.682914 8294473856 stat_var_processor.py:2920] Processing data ['/Users/nehilsood/work
- **us_steam_degrees_data**: no_eval_results - 2026-01-16 17:27:02,853 - INFO - Added error feedback to prompt
- **who_covid19**: no_eval_results - Unknown - check logs for details


---

## Failure Pattern Analysis

### Common Missing Properties (pvs-deleted)

The following properties are most frequently missing from auto-generated PVMAPs:

| Property | Total Deletions |
|----------|----------------|
| name | 2679 |
| observationAbout | 2336 |
| industry | 2263 |
| value | 2192 |
| populationType | 1682 |
| gender | 1294 |
| schoolGradeLevel | 874 |
| measuredProperty | 827 |
| race | 753 |
| statType | 574 |
| unit | 548 |
| studentStatus | 533 |
| measurementMethod | 522 |
| measurementQualifier | 502 |
| observationDate | 483 |


### Common Extra Properties (pvs-added)

Properties frequently added by LLM but not in ground truth:

| Property | Total Additions |
|----------|----------------|
| statType | 653 |
| measuredProperty | 639 |
| populationType | 585 |
| observationAbout | 308 |
| value | 196 |
| observationDate | 195 |
| gender | 158 |
| age | 143 |
| medicalCondition | 141 |
| courseContent | 123 |
| gradeLevel | 121 |
| observationPeriod | 107 |
| unit | 103 |
| courseStatus | 60 |
| race | 39 |


---

## Individual Dataset Reports

Detailed analysis for each dataset is available in the `dataset_summaries/` directory:

- [bev_3240_wiki](dataset_summaries/bev_3240_wiki_analysis.md)
- [bis](dataset_summaries/bis_analysis.md)
- [bis_bis_central_bank_policy_rate](dataset_summaries/bis_bis_central_bank_policy_rate_analysis.md)
- [brazil_sidra_ibge](dataset_summaries/brazil_sidra_ibge_analysis.md)
- [brazil_visdata_FoodBasketDistribution](dataset_summaries/brazil_visdata_FoodBasketDistribution_analysis.md)
- [brazil_visdata_brazil_rural_development_program](dataset_summaries/brazil_visdata_brazil_rural_development_program_analysis.md)
- [brfss_nchs_asthma_prevalence](dataset_summaries/brfss_nchs_asthma_prevalence_analysis.md)
- [ccd_enrollment](dataset_summaries/ccd_enrollment_analysis.md)
- [cdc_social_vulnerability_index](dataset_summaries/cdc_social_vulnerability_index_analysis.md)
- [census_v2_sahie](dataset_summaries/census_v2_sahie_analysis.md)
- [census_v2_saipe](dataset_summaries/census_v2_saipe_analysis.md)
- [child_birth](dataset_summaries/child_birth_analysis.md)
- [commerce_eda](dataset_summaries/commerce_eda_analysis.md)
- [crdc_import_crdc_harassment_or_bullying](dataset_summaries/crdc_import_crdc_harassment_or_bullying_analysis.md)
- [crdc_instructional_wifi_devices](dataset_summaries/crdc_instructional_wifi_devices_analysis.md)
- [database_on_indian_economy_india_rbi_state_statistics](dataset_summaries/database_on_indian_economy_india_rbi_state_statistics_analysis.md)
- [doctoratedegreeemployment](dataset_summaries/doctoratedegreeemployment_analysis.md)
- [fao_currency_and_exchange_rate](dataset_summaries/fao_currency_and_exchange_rate_analysis.md)
- [fbi_fbigovcrime](dataset_summaries/fbi_fbigovcrime_analysis.md)
- [fema](dataset_summaries/fema_analysis.md)
- [finland_census](dataset_summaries/finland_census_analysis.md)
- [gdp_by_county_metro_and_other_areas](dataset_summaries/gdp_by_county_metro_and_other_areas_analysis.md)
- [google_sustainability_financial_incentives](dataset_summaries/google_sustainability_financial_incentives_analysis.md)
- [india_ndap](dataset_summaries/india_ndap_analysis.md)
- [india_ndap_india_nss_health_ailments](dataset_summaries/india_ndap_india_nss_health_ailments_analysis.md)
- [india_nfhs](dataset_summaries/india_nfhs_analysis.md)
- [india_rbistatedomesticproduct](dataset_summaries/india_rbistatedomesticproduct_analysis.md)
- [inpe_fire](dataset_summaries/inpe_fire_analysis.md)
- [ipeds](dataset_summaries/ipeds_analysis.md)
- [ireland_census](dataset_summaries/ireland_census_analysis.md)
- [mexico_subnational_population_statistics_mexico_census_aa2](dataset_summaries/mexico_subnational_population_statistics_mexico_census_aa2_analysis.md)
- [ncses_median_annual_salary](dataset_summaries/ncses_median_annual_salary_analysis.md)
- [ncses_ncses_demographics_seh_import](dataset_summaries/ncses_ncses_demographics_seh_import_analysis.md)
- [ncses_research_doctorate_recipients](dataset_summaries/ncses_research_doctorate_recipients_analysis.md)
- [ntia_internet_use_survey](dataset_summaries/ntia_internet_use_survey_analysis.md)
- [nyu_diabetes_tennessee](dataset_summaries/nyu_diabetes_tennessee_analysis.md)
- [nyu_diabetes_texas](dataset_summaries/nyu_diabetes_texas_analysis.md)
- [oecd_quarterly_gdp](dataset_summaries/oecd_quarterly_gdp_analysis.md)
- [oecd_regional_education](dataset_summaries/oecd_regional_education_analysis.md)
- [oecd_wastewater_treatment](dataset_summaries/oecd_wastewater_treatment_analysis.md)
- [opendataforafrica_ethiopia_statistics](dataset_summaries/opendataforafrica_ethiopia_statistics_analysis.md)
- [opendataforafrica_kenya_census](dataset_summaries/opendataforafrica_kenya_census_analysis.md)
- [opendataforafrica_rwanda_census](dataset_summaries/opendataforafrica_rwanda_census_analysis.md)
- [school_algebra1](dataset_summaries/school_algebra1_analysis.md)
- [school_finance](dataset_summaries/school_finance_analysis.md)
- [school_retention](dataset_summaries/school_retention_analysis.md)
- [singapore_census](dataset_summaries/singapore_census_analysis.md)
- [southkorea_statistics_demographics](dataset_summaries/southkorea_statistics_demographics_analysis.md)
- [southkorea_statistics_education](dataset_summaries/southkorea_statistics_education_analysis.md)
- [southkorea_statistics_employment](dataset_summaries/southkorea_statistics_employment_analysis.md)
- [southkorea_statistics_health](dataset_summaries/southkorea_statistics_health_analysis.md)
- [statistics_new_zealand_new_zealand_census](dataset_summaries/statistics_new_zealand_new_zealand_census_analysis.md)
- [uae_bayanat](dataset_summaries/uae_bayanat_analysis.md)
- [undata](dataset_summaries/undata_analysis.md)
- [us_bachelors_degree_data](dataset_summaries/us_bachelors_degree_data_analysis.md)
- [us_bls_bls_ces](dataset_summaries/us_bls_bls_ces_analysis.md)
- [us_bls_bls_ces_state](dataset_summaries/us_bls_bls_ces_state_analysis.md)
- [us_bls_cpi_category](dataset_summaries/us_bls_cpi_category_analysis.md)
- [us_bls_us_cpi](dataset_summaries/us_bls_us_cpi_analysis.md)
- [us_cdc_single_race](dataset_summaries/us_cdc_single_race_analysis.md)
- [us_census](dataset_summaries/us_census_analysis.md)
- [us_crash_fars_crashdata](dataset_summaries/us_crash_fars_crashdata_analysis.md)
- [us_education_new_york_education](dataset_summaries/us_education_new_york_education_analysis.md)
- [us_federal_reserve_h15_interest_rates](dataset_summaries/us_federal_reserve_h15_interest_rates_analysis.md)
- [us_hbcu_data](dataset_summaries/us_hbcu_data_analysis.md)
- [us_nces](dataset_summaries/us_nces_analysis.md)
- [us_newyork_ny_diabetes](dataset_summaries/us_newyork_ny_diabetes_analysis.md)
- [us_steam_degrees_data](dataset_summaries/us_steam_degrees_data_analysis.md)
- [us_urban_school_covid_directional_indicators](dataset_summaries/us_urban_school_covid_directional_indicators_analysis.md)
- [us_urban_school_maths_and_science_enrollment](dataset_summaries/us_urban_school_maths_and_science_enrollment_analysis.md)
- [us_urban_school_teachers](dataset_summaries/us_urban_school_teachers_analysis.md)
- [usa_dol](dataset_summaries/usa_dol_analysis.md)
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

*Report generated on 2026-01-19 13:36:09*
