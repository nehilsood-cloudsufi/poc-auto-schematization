# Evaluation Benchmark Comparison

**Generated**: 2026-01-19 13:37:00

This report compares our auto-generated PVMAP evaluation results against the benchmark results from the reference document.

---

## Executive Summary

### Final Statistics

**Dataset Coverage:**
- **Total Benchmark Datasets:** 49
- **Total New Iteration Datasets:** 69
- **Datasets Compared:** 40 (overlap between both evaluations)
- **Benchmark Datasets Not in New Iteration:** 9
- **New Datasets Not in Benchmark:** 29

**Performance Summary:**
- **PV Accuracy Improved:** 26 datasets (65.0%)
- **Average PV Accuracy:** 7.9% (benchmark) → 19.2% (new iteration)
- **Average Precision:** 21.7% (benchmark) → 29.5% (new iteration)
- **Average Recall:** 7.9% (benchmark) → 19.2% (new iteration)

### Dataset Coverage

| Metric | Benchmark | New Iteration |
|--------|-----------|---------------|
| **Total Datasets** | 49 | 69 |
| **Datasets Compared** | 40 | 40 |
| **Not in Other Set** | 9 | 29 |

### Average Performance Metrics

| Metric | Benchmark Avg | New Iteration Avg |
|--------|---------------|-------------------|
| **Node Accuracy %** | 5.4 | 14.8 |
| **Node Coverage %** | 50.4 | 72.0 |
| **PV Accuracy %** | 7.9 | 19.2 |
| **Precision %** | 21.7 | 29.5 |
| **Recall %** | 7.9 | 19.2 |

### Improvement Statistics

| Metric | Improved | Declined | No Change |
|--------|----------|----------|-----------|
| **Node Accuracy** | 17 (42.5%) | 13 (32.5%) | 10 |
| **Node Coverage** | 19 (47.5%) | 14 (35.0%) | 7 |
| **PV Accuracy** | 26 (65.0%) | 10 (25.0%) | 4 |
| **Precision** | 25 (62.5%) | 13 (32.5%) | 2 |
| **Recall** | 26 (65.0%) | 10 (25.0%) | 4 |

### Best Improvements

- **Node Accuracy**: bis_bis_central_bank_policy_rate (+228.6%)
- **PV Accuracy**: bis_bis_central_bank_policy_rate (+73.1%)
- **Precision**: ncses_ncses_demographics_seh_import (+60.9%)
- **Recall**: bis_bis_central_bank_policy_rate (+73.1%)

### Largest Declines

- **Node Accuracy**: india_ndap_india_nss_health_ailments (-25.0%)
- **PV Accuracy**: opendataforafrica_ethiopia_statistics (-22.5%)
- **Precision**: brazil_sidra_ibge (-68.2%)
- **Recall**: opendataforafrica_ethiopia_statistics (-22.5%)

---

## Detailed Comparison Table

| Dataset | Benchmark Node Acc % | New Node Acc % | Benchmark Node Cov % | New Node Cov % | Benchmark PV % | New PV % | Benchmark Precision % | New Precision % | Benchmark Recall % | New Recall % |
|---------|---------------------|----------------|---------------------|---------------|---------------|---------|----------------------|----------------|-------------------|--------------|
| bis_bis_central_bank_policy_rate | 0.0 | 228.6 | 100.0 | 285.7 | 0.0 | 73.1 | 11.9 | 61.3 | 0.0 | 73.1 |
| zurich_wir_2552_wiki | 0.0 | 10.0 | 100.0 | 100.0 | 17.9 | 64.3 | 25.5 | 55.1 | 17.9 | 64.3 |
| world_bank_commodity_market | 7.4 | 0.0 | 98.9 | 76.6 | 3.7 | 48.8 | 7.6 | 22.9 | 3.7 | 48.8 |
| inpe_fire | 0.0 | 12.5 | 43.8 | 45.8 | 0.0 | 44.3 | 21.4 | 46.6 | 0.0 | 44.3 |
| zurich_bev_4031_sex_wiki | 0.0 | 33.3 | 66.7 | 83.3 | 0.0 | 37.5 | 30.0 | 26.1 | 0.0 | 37.5 |
| bev_3240_wiki | 0.0 | 0.0 | 100.0 | 75.0 | 0.0 | 33.3 | 33.3 | 60.0 | 0.0 | 33.3 |
| zurich_bev_3240_wiki | 0.0 | 25.0 | 100.0 | 100.0 | 0.0 | 33.3 | 33.3 | 50.0 | 0.0 | 33.3 |
| zurich_bev_4031_wiki | 0.0 | 25.0 | 100.0 | 100.0 | 0.0 | 33.3 | 10.3 | 50.0 | 0.0 | 33.3 |
| census_v2_sahie | 0.0 | 33.3 | 38.9 | 88.9 | 8.0 | 39.4 | 33.3 | 60.9 | 8.0 | 39.4 |
| zurich_bev_3903_sex_wiki | 0.0 | 16.7 | 66.7 | 66.7 | 12.5 | 37.5 | 18.2 | 41.7 | 12.5 | 37.5 |
| zurich_bev_4031_hel_wiki | 0.0 | 16.7 | 100.0 | 100.0 | 0.0 | 25.0 | 16.7 | 41.7 | 0.0 | 25.0 |
| zurich_bev_3903_hel_wiki | 0.0 | 0.0 | 75.0 | 50.0 | 0.0 | 20.0 | 12.0 | 36.4 | 0.0 | 20.0 |
| us_education_new_york_education | 0.0 | 6.4 | 56.4 | 53.2 | 16.2 | 33.3 | 4.7 | 44.4 | 16.2 | 33.3 |
| oecd_wastewater_treatment | 0.0 | 7.7 | 92.3 | 38.5 | 0.0 | 12.5 | 4.7 | 39.1 | 0.0 | 12.5 |
| ncses_ncses_demographics_seh_import | 7.3 | 44.7 | 9.8 | 105.3 | 3.9 | 14.6 | 3.7 | 64.6 | 3.9 | 14.6 |
| cdc_social_vulnerability_index | 0.0 | 2.4 | 88.1 | 33.3 | 4.9 | 15.5 | 6.4 | 24.5 | 4.9 | 15.5 |
| doctoratedegreeemployment | 16.1 | 12.9 | 61.3 | 61.3 | 10.0 | 20.0 | 44.8 | 34.7 | 10.0 | 20.0 |
| fbi_fbigovcrime | 0.0 | 0.0 | 6.7 | 5.3 | 0.0 | 8.7 | 14.5 | 25.8 | 0.0 | 8.7 |
| us_urban_school_teachers | 0.0 | 2.9 | 31.4 | 31.4 | 2.1 | 8.9 | 17.5 | 32.8 | 2.1 | 8.9 |
| ireland_census | 11.8 | 0.0 | 47.1 | 93.8 | 9.1 | 15.4 | 13.9 | 18.2 | 9.1 | 15.4 |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 4.9 | 98.1 | 0.0 | 3.5 | 11.1 | 33.3 | 0.0 | 3.5 |
| undata | 88.8 | 91.0 | 98.9 | 95.5 | 87.1 | 90.3 | 75.5 | 92.4 | 87.1 | 90.3 |
| india_ndap | 6.7 | 3.3 | 23.3 | 10.0 | 9.1 | 12.1 | 33.3 | 29.4 | 9.1 | 12.1 |
| us_bls_us_cpi | 0.0 | 0.0 | 5.6 | 98.7 | 0.0 | 2.2 | 0.0 | 2.1 | 0.0 | 2.2 |
| us_cdc_single_race | 0.0 | 0.0 | 17.1 | 2.0 | 1.2 | 3.0 | 18.8 | 13.9 | 1.2 | 3.0 |
| us_bls_bls_ces | 0.2 | 0.4 | 1.1 | 1.3 | 0.0 | 0.4 | 2.4 | 6.6 | 0.0 | 0.4 |
| zurich_bev_3903_age10_wiki | 6.7 | 0.0 | 33.3 | 26.7 | 11.8 | 11.8 | 36.4 | 20.0 | 11.8 | 11.8 |
| us_bls_bls_ces_state | 0.3 | 0.3 | 1.1 | 0.5 | 0.1 | 0.1 | 25.9 | 56.0 | 0.1 | 0.1 |
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 | 55.6 | 92.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| us_bls_cpi_category | 0.0 | 0.0 | 43.6 | 99.5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| us_crash_fars_crashdata | 5.9 | 3.7 | 11.8 | 10.3 | 2.1 | 0.7 | 21.8 | 39.1 | 2.1 | 0.7 |
| brazil_sidra_ibge | 4.7 | 0.0 | 37.2 | 98.5 | 2.3 | 0.0 | 68.2 | 0.0 | 2.3 | 0.0 |
| ccd_enrollment | 0.0 | 15.8 | 50.0 | 65.8 | 23.2 | 20.4 | 5.3 | 47.2 | 23.2 | 20.4 |
| brazil_visdata_FoodBasketDistribution | 0.0 | 0.0 | 50.0 | 95.5 | 2.9 | 0.0 | 19.0 | 0.0 | 2.9 | 0.0 |
| oecd_regional_education | 5.6 | 0.0 | 33.3 | 95.7 | 5.3 | 0.0 | 13.3 | 0.0 | 5.3 | 0.0 |
| ncses_median_annual_salary | 8.1 | 0.0 | 10.8 | 97.4 | 5.4 | 0.0 | 15.8 | 0.0 | 5.4 | 0.0 |
| singapore_census | 11.8 | 0.0 | 47.1 | 99.0 | 9.1 | 0.0 | 13.9 | 0.0 | 9.1 | 0.0 |
| southkorea_statistics_health | 4.4 | 0.0 | 36.3 | 99.6 | 22.5 | 3.7 | 53.2 | 0.5 | 22.5 | 3.7 |
| india_ndap_india_nss_health_ailments | 25.0 | 0.0 | 34.4 | 5.4 | 21.6 | 0.0 | 35.7 | 3.1 | 21.6 | 0.0 |
| opendataforafrica_ethiopia_statistics | 4.4 | 0.0 | 36.3 | 95.2 | 22.5 | 0.0 | 53.2 | 0.0 | 22.5 | 0.0 |

---

## Improved Datasets by Metric

### PV Accuracy Improvements (26 datasets)

| Dataset | Benchmark PV % | New PV % | Improvement |
|---------|----------------|----------|-------------|
| bis_bis_central_bank_policy_rate | 0.0 | 73.1 | +73.1 |
| zurich_wir_2552_wiki | 17.9 | 64.3 | +46.4 |
| world_bank_commodity_market | 3.7 | 48.8 | +45.1 |
| inpe_fire | 0.0 | 44.3 | +44.3 |
| zurich_bev_4031_sex_wiki | 0.0 | 37.5 | +37.5 |
| bev_3240_wiki | 0.0 | 33.3 | +33.3 |
| zurich_bev_3240_wiki | 0.0 | 33.3 | +33.3 |
| zurich_bev_4031_wiki | 0.0 | 33.3 | +33.3 |
| census_v2_sahie | 8.0 | 39.4 | +31.4 |
| zurich_bev_3903_sex_wiki | 12.5 | 37.5 | +25.0 |
| zurich_bev_4031_hel_wiki | 0.0 | 25.0 | +25.0 |
| zurich_bev_3903_hel_wiki | 0.0 | 20.0 | +20.0 |
| us_education_new_york_education | 16.2 | 33.3 | +17.1 |
| oecd_wastewater_treatment | 0.0 | 12.5 | +12.5 |
| ncses_ncses_demographics_seh_import | 3.9 | 14.6 | +10.7 |

### Node Accuracy Improvements (17 datasets)

| Dataset | Benchmark Node % | New Node % | Improvement |
|---------|-----------------|------------|-------------|
| bis_bis_central_bank_policy_rate | 0.0 | 228.6 | +228.6 |
| ncses_ncses_demographics_seh_import | 7.3 | 44.7 | +37.4 |
| zurich_bev_4031_sex_wiki | 0.0 | 33.3 | +33.3 |
| census_v2_sahie | 0.0 | 33.3 | +33.3 |
| zurich_bev_3240_wiki | 0.0 | 25.0 | +25.0 |
| zurich_bev_4031_wiki | 0.0 | 25.0 | +25.0 |
| zurich_bev_3903_sex_wiki | 0.0 | 16.7 | +16.7 |
| zurich_bev_4031_hel_wiki | 0.0 | 16.7 | +16.7 |
| ccd_enrollment | 0.0 | 15.8 | +15.8 |
| inpe_fire | 0.0 | 12.5 | +12.5 |
| zurich_wir_2552_wiki | 0.0 | 10.0 | +10.0 |
| oecd_wastewater_treatment | 0.0 | 7.7 | +7.7 |
| us_education_new_york_education | 0.0 | 6.4 | +6.4 |
| us_urban_school_teachers | 0.0 | 2.9 | +2.9 |
| cdc_social_vulnerability_index | 0.0 | 2.4 | +2.4 |

---

## Declined Datasets by Metric

### PV Accuracy Declines (10 datasets)

| Dataset | Benchmark PV % | New PV % | Decline |
|---------|----------------|----------|---------|
| opendataforafrica_ethiopia_statistics | 22.5 | 0.0 | -22.5 |
| india_ndap_india_nss_health_ailments | 21.6 | 0.0 | -21.6 |
| southkorea_statistics_health | 22.5 | 3.7 | -18.8 |
| singapore_census | 9.1 | 0.0 | -9.1 |
| ncses_median_annual_salary | 5.4 | 0.0 | -5.4 |
| oecd_regional_education | 5.3 | 0.0 | -5.3 |
| brazil_visdata_FoodBasketDistribution | 2.9 | 0.0 | -2.9 |
| ccd_enrollment | 23.2 | 20.4 | -2.8 |
| brazil_sidra_ibge | 2.3 | 0.0 | -2.3 |
| us_crash_fars_crashdata | 2.1 | 0.7 | -1.4 |

---

## Dataset Name Mappings

| New Iteration Name | Benchmark Name |
|--------------------|----------------|
| bis_bis_central_bank_policy_rate | bis_central_bank_policy_rate |
| brazil_visdata_FoodBasketDistribution | FoodBasketDistribution |
| brazil_visdata_brazil_rural_development_program | brazil_rural_development_program |
| ccd_enrollment | enrollment |
| cdc_social_vulnerability_index | social_vulnerability_index |
| census_v2_sahie | sahie |
| fbi_fbigovcrime | fbigovcrime |
| india_ndap | ndap |
| india_ndap_india_nss_health_ailments | IndiaNSS_HealthAilments |
| india_rbistatedomesticproduct | india_rbi_state_statistics |
| ireland_census | kenya_census |
| ncses_ncses_demographics_seh_import | demographics |
| oecd_regional_education | regional_education |
| oecd_wastewater_treatment | wastewater_treatment |
| opendataforafrica_ethiopia_statistics | ethiopia_statistics |
| singapore_census | kenya_census |
| southkorea_statistics_health | ethiopia_statistics |
| us_bls_bls_ces | bls_ces |
| us_bls_bls_ces_state | bls_ces_state |
| us_bls_cpi_category | cpi_category |
| us_bls_us_cpi | us_cpi |
| us_cdc_single_race | single_race |
| us_crash_fars_crashdata | fars_crashdata |
| us_education_new_york_education | education |
| us_urban_school_teachers | teachers |
| world_bank_commodity_market | commodity_market |
| zurich_bev_3240_wiki | bev_3240_wiki |
| zurich_bev_3903_age10_wiki | bev_3903_age10_wiki |
| zurich_bev_3903_hel_wiki | bev_3903_hel_wiki |
| zurich_bev_3903_sex_wiki | bev_3903_sex_wiki |
| zurich_bev_4031_hel_wiki | bev_4031_hel_wiki |
| zurich_bev_4031_sex_wiki | bev_4031_sex_wiki |
| zurich_bev_4031_wiki | bev_4031_wiki |
| zurich_wir_2552_wiki | wir_2552_wiki |

---

## Datasets Not in Benchmark

The following datasets in our evaluation were not found in the benchmark document:

- bis: 25.0% PV Accuracy
- brfss_nchs_asthma_prevalence: 7.9% PV Accuracy
- child_birth: 18.2% PV Accuracy
- crdc_import_crdc_harassment_or_bullying: 0.0% PV Accuracy
- crdc_instructional_wifi_devices: 23.1% PV Accuracy
- fao_currency_and_exchange_rate: 0.5% PV Accuracy
- finland_census: 16.4% PV Accuracy
- google_sustainability_financial_incentives: 0.4% PV Accuracy
- ipeds: 16.7% PV Accuracy
- mexico_subnational_population_statistics_mexico_census_aa2: 0.0% PV Accuracy
- ncses_research_doctorate_recipients: 0.0% PV Accuracy
- ntia_internet_use_survey: 0.0% PV Accuracy
- nyu_diabetes_texas: 4.1% PV Accuracy
- oecd_quarterly_gdp: 7.7% PV Accuracy
- school_algebra1: 15.7% PV Accuracy
- school_finance: 11.8% PV Accuracy
- school_retention: 0.0% PV Accuracy
- southkorea_statistics_demographics: 4.1% PV Accuracy
- southkorea_statistics_education: 4.8% PV Accuracy
- southkorea_statistics_employment: 0.0% PV Accuracy
- statistics_new_zealand_new_zealand_census: 24.3% PV Accuracy
- uae_bayanat: 0.0% PV Accuracy
- us_bachelors_degree_data: 2.7% PV Accuracy
- us_federal_reserve_h15_interest_rates: 0.0% PV Accuracy
- us_nces: 2.2% PV Accuracy
- us_newyork_ny_diabetes: 53.8% PV Accuracy
- us_urban_school_covid_directional_indicators: 7.1% PV Accuracy
- us_urban_school_maths_and_science_enrollment: 4.2% PV Accuracy
- usa_dol: 0.0% PV Accuracy

---

## Benchmark Datasets Not in Our Evaluation

The following datasets from the benchmark were not found in our evaluation:

- commerce_eda: 0.0% PV Accuracy (benchmark)
- crdc_import: 0.0% PV Accuracy (benchmark)
- employment: 3.3% PV Accuracy (benchmark)
- fao_currency_statvar: 0.0% PV Accuracy (benchmark)
- health: 25.8% PV Accuracy (benchmark)
- india_nfhs: 14.2% PV Accuracy (benchmark)
- minimum_wage: 0.0% PV Accuracy (benchmark)
- nces_stem_degrees_import: 7.1% PV Accuracy (benchmark)
- nchs_brfss_asthma: 1.5% PV Accuracy (benchmark)
- saipe: 35.7% PV Accuracy (benchmark)
- us_census_pep_asrh: 8.8% PV Accuracy (benchmark)
- us_monthly_retail_sales: 17.5% PV Accuracy (benchmark)

---

*Comparison generated on 2026-01-19 13:37:00*
