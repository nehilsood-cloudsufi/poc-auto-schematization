# Auto-Schematization Evaluation Benchmark Comparison

**Generated**: 2026-01-21

This report compares the auto-generated PVMAP outputs from **Gemini (Base)**, **Claude CLI**, and **Gemini 3 Pro** models across benchmark datasets.

---

## Summary Statistics

| Metric | Gemini (Base) | Claude CLI | Gemini 3 Pro |
|--------|---------------|------------|--------------|
| Total Datasets Evaluated | 49 | 49 | 49 |
| Average Node Accuracy | 4.6% | 11.5% | 11.7% |
| Average Node Coverage | 45.8% | 60.1% | 60.1% |
| Average PV Accuracy | 8.1% | 19.2% | 20.5% |

---

## Node Accuracy Comparison

Node Accuracy = (Nodes Matched / Ground Truth Nodes) × 100

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| bis_bis_central_bank_policy_rate | 0.0 | **14.3** | 14.3 |
| brazil_sidra_ibge | **4.7** | 4.7 | 4.7 |
| brazil_visdata_FoodBasketDistribution | 0.0 | 0.0 | 0.0 |
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 | 0.0 |
| brfss_nchs_asthma_prevalence | 0.0 | 21.1 | **26.1** |
| ccd_enrollment | 0.0 | **2.6** | 0.0 |
| cdc_social_vulnerability_index | 0.0 | 0.0 | **2.4** |
| census_v2_sahie | 0.0 | **19.4** | 22.2 |
| census_v2_saipe | 0.0 | 0.0 | **14.3** |
| child_birth | 0.0 | 0.0 | 0.0 |
| commerce_eda | 0.0 | 0.0 | **1.6** |
| crdc_import_crdc_harassment_or_bullying | 0.0 | 0.0 | 0.0 |
| crdc_instructional_wifi_devices | 0.0 | 0.0 | 0.0 |
| database_on_indian_economy_india_rbi_state_statistics | 0.0 | **1.2** | 1.2 |
| doctoratedegreeemployment | 16.1 | **19.4** | 16.1 |
| fao_currency_and_exchange_rate | 0.0 | 0.0 | 0.0 |
| fbi_fbigovcrime | 0.0 | 0.0 | 0.0 |
| finland_census | 0.0 | 0.0 | 0.0 |
| google_sustainability_financial_incentives | 0.0 | 0.0 | 0.0 |
| india_ndap | **6.7** | 0.0 | 0.0 |
| india_ndap_india_nss_health_ailments | **25.0** | 0.0 | 0.0 |
| india_nfhs | 0.0 | **0.1** | 0.0 |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 0.0 |
| inpe_fire | 0.0 | 0.0 | **12.5** |
| ipeds | 0.0 | 0.0 | 0.0 |
| ireland_census | 0.0 | 0.0 | 0.0 |
| mexico_subnational_population_statistics_mexico_census_aa2 | 0.0 | 0.0 | 0.0 |
| ncses_median_annual_salary | **8.1** | 8.1 | 8.1 |
| ncses_ncses_demographics_seh_import | 7.3 | 10.5 | **18.4** |
| ncses_research_doctorate_recipients | 0.0 | 0.0 | 0.0 |
| ntia_internet_use_survey | 0.0 | 0.0 | 0.0 |
| nyu_diabetes_texas | 0.0 | 0.0 | 0.0 |
| oecd_regional_education | 5.6 | **5.6** | 5.6 |
| oecd_wastewater_treatment | 0.0 | **7.7** | 7.7 |
| opendataforafrica_ethiopia_statistics | 4.4 | **87.0** | 87.0 |
| opendataforafrica_kenya_census | 11.8 | **28.6** | 28.6 |
| opendataforafrica_rwanda_census | 0.0 | 0.0 | 0.0 |
| school_algebra1 | 0.0 | 0.0 | 0.0 |
| school_finance | 0.0 | 0.0 | 0.0 |
| school_retention | 0.0 | 0.0 | 0.0 |
| southkorea_statistics_education | 0.0 | 0.0 | 0.0 |
| southkorea_statistics_employment | 0.0 | 0.0 | 0.0 |
| southkorea_statistics_health | 0.0 | **2.9** | 2.9 |
| statistics_new_zealand_new_zealand_census | 0.0 | 0.0 | 0.0 |
| uae_bayanat | 0.0 | 0.0 | 0.0 |
| undata | 88.8 | **89.9** | 89.9 |
| us_bachelors_degree_data | 0.0 | 0.0 | 0.0 |
| us_bls_bls_ces | 0.2 | 0.4 | **0.8** |
| us_bls_bls_ces_state | 0.3 | 0.3 | **0.5** |
| us_bls_cpi_category | 0.0 | 0.0 | 0.0 |
| us_bls_us_cpi | 0.0 | 0.0 | **1.9** |
| us_cdc_single_race | 0.0 | 0.0 | **3.9** |
| us_census | **14.6** | 14.6 | 14.6 |
| us_census_us_monthly_retail_sales | 0.0 | **0.8** | 0.0 |
| us_crash_fars_crashdata | **5.9** | 4.4 | 3.7 |
| us_federal_reserve_h15_interest_rates | 0.0 | 0.0 | 0.0 |
| us_steam_degrees_data | **11.5** | 11.5 | 11.5 |
| us_urban_school_teachers | 0.0 | 0.0 | 0.0 |
| usa_dol | 0.0 | 0.0 | 0.0 |
| usa_dol_minimum_wage | 0.0 | 0.0 | 0.0 |
| world_bank_commodity_market | 7.4 | 0.0 | 0.0 |
| zurich_bev_3240_wiki | 0.0 | **25.0** | 25.0 |
| zurich_bev_3903_age10_wiki | 6.7 | 0.0 | **6.7** |
| zurich_bev_3903_hel_wiki | 0.0 | **12.5** | 12.5 |
| zurich_bev_3903_sex_wiki | 0.0 | **50.0** | 16.7 |
| zurich_bev_4031_hel_wiki | 0.0 | **16.7** | 16.7 |
| zurich_bev_4031_sex_wiki | 0.0 | **50.0** | 50.0 |
| zurich_bev_4031_wiki | 0.0 | 0.0 | **25.0** |
| zurich_wir_2552_wiki | 0.0 | **10.0** | 10.0 |

---

## Node Coverage Comparison

Node Coverage = (Auto-Generated Nodes / Ground Truth Nodes) × 100

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| bis_bis_central_bank_policy_rate | 100.0 | 100.0 | **114.3** |
| brazil_sidra_ibge | **37.2** | 18.6 | 18.6 |
| brazil_visdata_FoodBasketDistribution | 50.0 | 87.5 | **100.0** |
| brazil_visdata_brazil_rural_development_program | 55.6 | **233.3** | 38.9 |
| brfss_nchs_asthma_prevalence | 20.0 | 63.2 | **269.6** |
| ccd_enrollment | 50.0 | **76.3** | 0.0 |
| cdc_social_vulnerability_index | 88.1 | **190.5** | 69.0 |
| census_v2_sahie | 38.9 | **86.1** | 75.0 |
| census_v2_saipe | 85.7 | **114.3** | 100.0 |
| child_birth | 0.0 | 0.0 | 0.0 |
| commerce_eda | 1.3 | 0.0 | **7.8** |
| crdc_import_crdc_harassment_or_bullying | 5.0 | 1.3 | 1.3 |
| crdc_instructional_wifi_devices | 0.0 | 0.0 | 0.0 |
| database_on_indian_economy_india_rbi_state_statistics | 4.9 | **14.5** | 14.5 |
| doctoratedegreeemployment | **61.3** | 54.8 | 51.6 |
| fao_currency_and_exchange_rate | 3.3 | 2.3 | 2.3 |
| fbi_fbigovcrime | 6.7 | **14.0** | 8.7 |
| finland_census | 0.0 | 0.0 | 0.0 |
| google_sustainability_financial_incentives | 0.0 | 0.0 | 0.0 |
| india_ndap | 23.3 | **30.0** | 30.0 |
| india_ndap_india_nss_health_ailments | 34.4 | 56.8 | **62.2** |
| india_nfhs | 38.5 | 4.1 | **24.0** |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 0.0 |
| inpe_fire | 43.8 | 0.0 | **93.8** |
| ipeds | 0.0 | 0.0 | 0.0 |
| ireland_census | 0.0 | 0.0 | 0.0 |
| mexico_subnational_population_statistics_mexico_census_aa2 | 0.0 | 0.0 | 0.0 |
| ncses_median_annual_salary | 10.8 | **13.5** | 13.5 |
| ncses_ncses_demographics_seh_import | 9.8 | **76.3** | 63.2 |
| ncses_research_doctorate_recipients | 0.0 | 0.0 | 0.0 |
| ntia_internet_use_survey | 0.0 | 0.0 | 0.0 |
| nyu_diabetes_texas | 0.0 | 0.0 | 0.0 |
| oecd_regional_education | 33.3 | 27.8 | 27.8 |
| oecd_wastewater_treatment | 92.3 | 100.0 | **107.7** |
| opendataforafrica_ethiopia_statistics | 36.3 | 0.5 | 0.5 |
| opendataforafrica_kenya_census | 47.1 | 171.4 | **185.7** |
| opendataforafrica_rwanda_census | 0.0 | 0.0 | 0.0 |
| school_algebra1 | 0.0 | 0.0 | 0.0 |
| school_finance | 0.0 | 0.0 | 0.0 |
| school_retention | 0.0 | 0.0 | 0.0 |
| southkorea_statistics_education | 0.0 | 0.0 | **188.5** |
| southkorea_statistics_employment | 20.5 | **23.3** | 17.9 |
| southkorea_statistics_health | 0.0 | **20.6** | 20.6 |
| statistics_new_zealand_new_zealand_census | 0.0 | 0.0 | 0.0 |
| uae_bayanat | 0.0 | 0.0 | 0.0 |
| undata | **98.9** | 7.9 | 10.1 |
| us_bachelors_degree_data | 0.0 | 0.0 | 0.0 |
| us_bls_bls_ces | 1.1 | 3.6 | **4.0** |
| us_bls_bls_ces_state | 1.1 | 0.3 | 0.4 |
| us_bls_cpi_category | **43.6** | 4.6 | 0.9 |
| us_bls_us_cpi | 5.6 | 37.0 | **103.7** |
| us_cdc_single_race | 17.1 | 13.2 | **19.7** |
| us_census | **28.1** | 15.7 | 16.9 |
| us_census_us_monthly_retail_sales | 37.5 | **56.2** | 12.5 |
| us_crash_fars_crashdata | 11.8 | **11.8** | 6.6 |
| us_federal_reserve_h15_interest_rates | 0.0 | 0.0 | 0.0 |
| us_steam_degrees_data | 13.5 | **17.3** | 17.3 |
| us_urban_school_teachers | 31.4 | 0.0 | **40.0** |
| usa_dol | 0.0 | 0.0 | 0.0 |
| usa_dol_minimum_wage | 90.5 | **90.5** | 90.5 |
| world_bank_commodity_market | **98.9** | 91.5 | 78.7 |
| zurich_bev_3240_wiki | 100.0 | **100.0** | 100.0 |
| zurich_bev_3903_age10_wiki | 33.3 | **100.0** | 100.0 |
| zurich_bev_3903_hel_wiki | 75.0 | **75.0** | 75.0 |
| zurich_bev_3903_sex_wiki | 66.7 | **100.0** | 100.0 |
| zurich_bev_4031_hel_wiki | 100.0 | **100.0** | 100.0 |
| zurich_bev_4031_sex_wiki | 66.7 | **100.0** | 100.0 |
| zurich_bev_4031_wiki | 100.0 | **100.0** | 100.0 |
| zurich_wir_2552_wiki | 100.0 | **100.0** | 100.0 |

---

## PV Accuracy Comparison

PV Accuracy = PVs Matched / (PVs Matched + PVs Modified + PVs Deleted) × 100

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| bis_bis_central_bank_policy_rate | 0.0 | 18.2 | **36.4** |
| brazil_sidra_ibge | **2.3** | 2.3 | 2.3 |
| brazil_visdata_FoodBasketDistribution | 2.9 | 0.0 | 0.0 |
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 | 0.0 |
| brfss_nchs_asthma_prevalence | 1.5 | **23.3** | 19.1 |
| ccd_enrollment | 23.2 | **31.9** | 0.0 |
| cdc_social_vulnerability_index | 4.9 | **28.3** | 14.6 |
| census_v2_sahie | 8.0 | **34.8** | 34.1 |
| census_v2_saipe | 35.7 | 50.0 | **53.3** |
| child_birth | 0.0 | 0.0 | 0.0 |
| commerce_eda | 0.0 | 0.0 | **6.7** |
| crdc_import_crdc_harassment_or_bullying | 0.0 | 0.0 | 0.0 |
| crdc_instructional_wifi_devices | 0.0 | 0.0 | 0.0 |
| database_on_indian_economy_india_rbi_state_statistics | 0.0 | 0.3 | **6.4** |
| doctoratedegreeemployment | 10.0 | **29.6** | 18.3 |
| fao_currency_and_exchange_rate | 0.0 | 0.0 | 0.0 |
| fbi_fbigovcrime | 0.0 | **8.2** | 6.6 |
| finland_census | 0.0 | 0.0 | 0.0 |
| google_sustainability_financial_incentives | 0.0 | 0.0 | 0.0 |
| india_ndap | **9.1** | 9.1 | 6.1 |
| india_ndap_india_nss_health_ailments | **21.6** | 0.0 | 0.0 |
| india_nfhs | 14.2 | 5.3 | **21.6** |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 0.0 |
| inpe_fire | 0.0 | 0.0 | **40.5** |
| ipeds | 0.0 | 0.0 | 0.0 |
| ireland_census | 0.0 | 0.0 | 0.0 |
| mexico_subnational_population_statistics_mexico_census_aa2 | 0.0 | 0.0 | 0.0 |
| ncses_median_annual_salary | **5.4** | 5.4 | 5.4 |
| ncses_ncses_demographics_seh_import | **3.9** | 6.2 | 8.1 |
| ncses_research_doctorate_recipients | 0.0 | 0.0 | 0.0 |
| ntia_internet_use_survey | 0.0 | 0.0 | 0.0 |
| nyu_diabetes_texas | 0.0 | 0.0 | 0.0 |
| oecd_regional_education | 5.3 | 2.6 | 2.6 |
| oecd_wastewater_treatment | 0.0 | **10.7** | 3.6 |
| opendataforafrica_ethiopia_statistics | 22.5 | **64.4** | 64.4 |
| opendataforafrica_kenya_census | 9.1 | **30.0** | 30.0 |
| opendataforafrica_rwanda_census | 0.0 | 0.0 | 0.0 |
| school_algebra1 | 0.0 | 0.0 | 0.0 |
| school_finance | 0.0 | 0.0 | 0.0 |
| school_retention | 0.0 | 0.0 | 0.0 |
| southkorea_statistics_education | 0.0 | 0.0 | 0.0 |
| southkorea_statistics_employment | 3.3 | 0.0 | 0.0 |
| southkorea_statistics_health | 0.0 | **1.5** | 1.5 |
| statistics_new_zealand_new_zealand_census | 0.0 | 0.0 | 0.0 |
| uae_bayanat | 0.0 | 0.0 | 0.0 |
| undata | **87.1** | 88.3 | 88.3 |
| us_bachelors_degree_data | 0.0 | 0.0 | 0.0 |
| us_bls_bls_ces | 0.0 | **0.4** | 0.4 |
| us_bls_bls_ces_state | 0.1 | **0.2** | 0.2 |
| us_bls_cpi_category | 0.0 | 0.0 | 0.0 |
| us_bls_us_cpi | 0.0 | 0.0 | **1.1** |
| us_cdc_single_race | 1.2 | 0.6 | **6.4** |
| us_census | **8.8** | 5.7 | 4.6 |
| us_census_us_monthly_retail_sales | **17.5** | 1.0 | 1.0 |
| us_crash_fars_crashdata | **2.1** | 1.0 | 1.2 |
| us_federal_reserve_h15_interest_rates | 0.0 | 0.0 | 0.0 |
| us_steam_degrees_data | **7.1** | 7.1 | 7.1 |
| us_urban_school_teachers | 2.1 | 0.0 | **8.2** |
| usa_dol | 0.0 | 0.0 | 0.0 |
| usa_dol_minimum_wage | 0.0 | **89.0** | 89.0 |
| world_bank_commodity_market | 3.7 | **35.5** | 32.7 |
| zurich_bev_3240_wiki | 0.0 | 33.3 | **50.0** |
| zurich_bev_3903_age10_wiki | 11.8 | 11.8 | **17.6** |
| zurich_bev_3903_hel_wiki | 0.0 | **30.0** | 30.0 |
| zurich_bev_3903_sex_wiki | 12.5 | **62.5** | 37.5 |
| zurich_bev_4031_hel_wiki | 0.0 | 25.0 | **37.5** |
| zurich_bev_4031_sex_wiki | 0.0 | 50.0 | **62.5** |
| zurich_bev_4031_wiki | 0.0 | 16.7 | **50.0** |
| zurich_wir_2552_wiki | 17.9 | 42.9 | **75.0** |

---

## Top Performers

### Best Node Accuracy (>50%)
- **undata** (Claude CLI & Gemini 3 Pro): 89.9%, Gemini Base: 88.8%
- **opendataforafrica_ethiopia_statistics** (Claude CLI & Gemini 3 Pro): 87.0%, Gemini Base: 4.4%
- **zurich_bev_3903_sex_wiki** (Claude CLI): 50.0%
- **zurich_bev_4031_sex_wiki** (Claude CLI & Gemini 3 Pro): 50.0%

### Key Observations
1. **Claude CLI and Gemini 3 Pro perform similarly** on average Node Accuracy (~11-12%), while **Gemini Base is lower** (4.6%)
2. **Gemini 3 Pro has highest PV Accuracy** (20.5%) followed by Claude CLI (19.2%), Gemini Base much lower (8.1%)
3. **Claude CLI and Gemini 3 Pro have higher Node Coverage** (60.1%) vs Gemini Base (45.8%)
4. **undata** is the standout performer across all models
5. **Claude CLI excels on Zurich datasets** with several 50%+ accuracies
6. **Gemini Base shows weaker performance overall** compared to Claude CLI and Gemini 3 Pro

---

**Legend:**
- **Node Accuracy**: Percentage of ground truth nodes exactly matched
- **Node Coverage**: Ratio of auto-generated nodes to ground truth nodes (>100% = over-generation)
- **PV Accuracy**: Percentage of property-values correctly matched
- **Bold** indicates best result for that dataset
- `0.0` in Claude CLI or Gemini 3 Pro columns may indicate dataset was not evaluated for that model
