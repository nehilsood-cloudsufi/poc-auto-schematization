# Enhanced Pipeline Benchmark Comparison

**Generated**: 2026-04-03T11:35:33.660844+00:00
**Branch**: `feature/nehil/feedback_integration`
**Commit**: `b8012e9`
**Flags**: `--prompt-version v3 --feedback-prompt-version v2 --use-llm-judge --enable-mcp --auto-approve --force-resample --force-schema-selection`

---

## Summary Statistics

| Metric | Gemini (Base) | Claude CLI | Gemini 3 Pro | Enhanced Pipeline |
|--------|--------|--------|--------|--------|
| Total Datasets Evaluated | 49 | 49 | 49 | 46 |
| Average Node Accuracy | 4.6% | 11.5% | 11.7% | 21.9% |
| Average Node Coverage | 45.8% | 60.1% | 60.1% | 47.3% |
| Average PV Accuracy | 8.1% | 19.2% | 20.5% | 21.3% |

---

## Node Accuracy Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % | Enhanced Pipeline % | Time (s) |
|---------|---------------|--------------|----------------|---------------------|----------|
| bis_bis_central_bank_policy_rate | 0.0 | **14.3** | **14.3** | 0.0 | 315.7 |
| brazil_sidra_ibge | **4.7** | **4.7** | **4.7** | **4.7** | 230.6 |
| brazil_visdata_FoodBasketDistribution | 0.0 | 0.0 | 0.0 | **28.6** | 243.8 |
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 | 0.0 | **14.3** | 345.3 |
| brfss_nchs_asthma_prevalence | 0.0 | 21.1 | 26.1 | **36.8** | 419.0 |
| ccd_enrollment | 0.0 | **2.6** | 0.0 | — | — |
| cdc_social_vulnerability_index | 0.0 | 0.0 | **2.4** | **2.4** | 562.3 |
| census_v2_sahie | 0.0 | 19.4 | **22.2** | 5.6 | 408.8 |
| census_v2_saipe | 0.0 | 0.0 | 14.3 | **42.9** | 302.9 |
| child_birth | 0.0 | 0.0 | 0.0 | — | — |
| commerce_eda | 0.0 | 0.0 | 1.6 | **220.0** | 490.4 |
| crdc_import_crdc_harassment_or_bullying | 0.0 | 0.0 | 0.0 | 0.0 | 507.9 |
| crdc_instructional_wifi_devices | 0.0 | 0.0 | 0.0 | — | — |
| database_on_indian_economy_india_rbi_state_statistics | 0.0 | 1.2 | 1.2 | **3.2** | 309.9 |
| doctoratedegreeemployment | 16.1 | **19.4** | 16.1 | 3.2 | 390.2 |
| fao_currency_and_exchange_rate | 0.0 | 0.0 | 0.0 | **0.7** | 214.7 |
| fbi_fbigovcrime | 0.0 | 0.0 | 0.0 | **0.7** | 397.2 |
| finland_census | 0.0 | 0.0 | 0.0 | — | — |
| google_sustainability_financial_incentives | 0.0 | 0.0 | 0.0 | — | — |
| india_ndap | **6.7** | 0.0 | 0.0 | **6.7** | 307.0 |
| india_ndap_india_nss_health_ailments | **25.0** | 0.0 | 0.0 | 2.7 | 362.5 |
| india_nfhs | 0.0 | 0.1 | 0.0 | **0.7** | 818.5 |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 0.0 | — | — |
| inpe_fire | 0.0 | 0.0 | **12.5** | 6.2 | 277.7 |
| ipeds | 0.0 | 0.0 | 0.0 | — | — |
| ireland_census | 0.0 | 0.0 | 0.0 | — | — |
| mexico_subnational_population_statistics_mexico_census_aa2 | 0.0 | 0.0 | 0.0 | — | — |
| ncses_median_annual_salary | **8.1** | **8.1** | **8.1** | **8.1** | 197.6 |
| ncses_ncses_demographics_seh_import | 7.3 | 10.5 | **18.4** | 2.6 | 500.4 |
| ncses_research_doctorate_recipients | 0.0 | 0.0 | 0.0 | — | — |
| ntia_internet_use_survey | 0.0 | 0.0 | 0.0 | — | — |
| nyu_diabetes_texas | 0.0 | 0.0 | 0.0 | — | — |
| oecd_regional_education | **5.6** | **5.6** | **5.6** | **5.6** | 206.9 |
| oecd_wastewater_treatment | 0.0 | 7.7 | 7.7 | **69.2** | 389.2 |
| opendataforafrica_ethiopia_statistics | 4.4 | **87.0** | **87.0** | **87.0** | 366.6 |
| opendataforafrica_kenya_census | 11.8 | 28.6 | 28.6 | **42.9** | 522.3 |
| opendataforafrica_rwanda_census | 0.0 | 0.0 | 0.0 | — | — |
| school_algebra1 | 0.0 | 0.0 | 0.0 | — | — |
| school_finance | 0.0 | 0.0 | 0.0 | — | — |
| school_retention | 0.0 | 0.0 | 0.0 | **1.3** | 369.6 |
| southkorea_statistics_education | 0.0 | 0.0 | 0.0 | — | — |
| southkorea_statistics_employment | 0.0 | 0.0 | 0.0 | **4.0** | 417.8 |
| southkorea_statistics_health | 0.0 | 2.9 | 2.9 | **8.8** | 405.8 |
| statistics_new_zealand_new_zealand_census | 0.0 | 0.0 | 0.0 | — | — |
| uae_bayanat | 0.0 | 0.0 | 0.0 | — | — |
| undata | 88.8 | 89.9 | 89.9 | **95.5** | 319.6 |
| us_bachelors_degree_data | 0.0 | 0.0 | 0.0 | — | — |
| us_bls_bls_ces | 0.2 | 0.4 | **0.8** | 0.3 | 442.4 |
| us_bls_bls_ces_state | 0.3 | 0.3 | **0.5** | 0.4 | 449.3 |
| us_bls_cpi_category | 0.0 | 0.0 | 0.0 | **5.1** | 274.4 |
| us_bls_us_cpi | 0.0 | 0.0 | **1.9** | **1.9** | 482.0 |
| us_cdc_single_race | 0.0 | 0.0 | **3.9** | — | — |
| us_census | 14.6 | 14.6 | 14.6 | **40.0** | 751.1 |
| us_census_us_monthly_retail_sales | 0.0 | **0.8** | 0.0 | 0.0 | 602.9 |
| us_crash_fars_crashdata | **5.9** | 4.4 | 3.7 | — | — |
| us_federal_reserve_h15_interest_rates | 0.0 | 0.0 | 0.0 | — | — |
| us_steam_degrees_data | **11.5** | **11.5** | **11.5** | **11.5** | 256.0 |
| us_urban_school_teachers | 0.0 | 0.0 | 0.0 | **20.0** | 386.8 |
| usa_dol | 0.0 | 0.0 | 0.0 | — | — |
| usa_dol_minimum_wage | 0.0 | 0.0 | 0.0 | 0.0 | 410.5 |
| world_bank_commodity_market | **7.4** | 0.0 | 0.0 | 0.0 | 592.6 |
| zurich_bev_3240_wiki | 0.0 | **25.0** | **25.0** | **25.0** | 198.3 |
| zurich_bev_3903_age10_wiki | **6.7** | 0.0 | **6.7** | **6.7** | 276.4 |
| zurich_bev_3903_hel_wiki | 0.0 | **12.5** | **12.5** | **12.5** | 168.1 |
| zurich_bev_3903_sex_wiki | 0.0 | **50.0** | 16.7 | **50.0** | 128.1 |
| zurich_bev_4031_hel_wiki | 0.0 | **16.7** | **16.7** | **16.7** | 364.9 |
| zurich_bev_4031_sex_wiki | 0.0 | 50.0 | 50.0 | **66.7** | 170.2 |
| zurich_bev_4031_wiki | 0.0 | 0.0 | **25.0** | **25.0** | 136.6 |
| zurich_wir_2552_wiki | 0.0 | 10.0 | 10.0 | **20.0** | 152.7 |

---

## Node Coverage Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % | Enhanced Pipeline % | Time (s) |
|---------|---------------|--------------|----------------|---------------------|----------|
| bis_bis_central_bank_policy_rate | 100.0 | 100.0 | **114.3** | 42.9 | 315.7 |
| brazil_sidra_ibge | **37.2** | 18.6 | 18.6 | 4.7 | 230.6 |
| brazil_visdata_FoodBasketDistribution | 50.0 | 87.5 | **100.0** | 42.9 | 243.8 |
| brazil_visdata_brazil_rural_development_program | 55.6 | **233.3** | 38.9 | 42.9 | 345.3 |
| brfss_nchs_asthma_prevalence | 20.0 | 63.2 | **269.6** | 63.2 | 419.0 |
| ccd_enrollment | 50.0 | **76.3** | 0.0 | — | — |
| cdc_social_vulnerability_index | 88.1 | **190.5** | 69.0 | 100.0 | 562.3 |
| census_v2_sahie | 38.9 | **86.1** | 75.0 | 27.8 | 408.8 |
| census_v2_saipe | 85.7 | **114.3** | 100.0 | 100.0 | 302.9 |
| child_birth | 0.0 | 0.0 | 0.0 | — | — |
| commerce_eda | 1.3 | 0.0 | 7.8 | **240.0** | 490.4 |
| crdc_import_crdc_harassment_or_bullying | **5.0** | 1.3 | 1.3 | 0.0 | 507.9 |
| crdc_instructional_wifi_devices | 0.0 | 0.0 | 0.0 | — | — |
| database_on_indian_economy_india_rbi_state_statistics | 4.9 | **14.5** | **14.5** | 6.5 | 309.9 |
| doctoratedegreeemployment | **61.3** | 54.8 | 51.6 | 16.1 | 390.2 |
| fao_currency_and_exchange_rate | **3.3** | 2.3 | 2.3 | 1.0 | 214.7 |
| fbi_fbigovcrime | 6.7 | **14.0** | 8.7 | 1.3 | 397.2 |
| finland_census | 0.0 | 0.0 | 0.0 | — | — |
| google_sustainability_financial_incentives | 0.0 | 0.0 | 0.0 | — | — |
| india_ndap | 23.3 | **30.0** | **30.0** | 16.7 | 307.0 |
| india_ndap_india_nss_health_ailments | 34.4 | 56.8 | **62.2** | 16.2 | 362.5 |
| india_nfhs | **38.5** | 4.1 | 24.0 | 13.0 | 818.5 |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 0.0 | — | — |
| inpe_fire | 43.8 | 0.0 | **93.8** | 39.6 | 277.7 |
| ipeds | 0.0 | 0.0 | 0.0 | — | — |
| ireland_census | 0.0 | 0.0 | 0.0 | — | — |
| mexico_subnational_population_statistics_mexico_census_aa2 | 0.0 | 0.0 | 0.0 | — | — |
| ncses_median_annual_salary | 10.8 | **13.5** | **13.5** | 10.8 | 197.6 |
| ncses_ncses_demographics_seh_import | 9.8 | **76.3** | 63.2 | 5.3 | 500.4 |
| ncses_research_doctorate_recipients | 0.0 | 0.0 | 0.0 | — | — |
| ntia_internet_use_survey | 0.0 | 0.0 | 0.0 | — | — |
| nyu_diabetes_texas | 0.0 | 0.0 | 0.0 | — | — |
| oecd_regional_education | **33.3** | 27.8 | 27.8 | 11.1 | 206.9 |
| oecd_wastewater_treatment | 92.3 | 100.0 | **107.7** | 92.3 | 389.2 |
| opendataforafrica_ethiopia_statistics | 36.3 | 0.5 | 0.5 | **87.1** | 366.6 |
| opendataforafrica_kenya_census | 47.1 | 171.4 | **185.7** | 100.0 | 522.3 |
| opendataforafrica_rwanda_census | 0.0 | 0.0 | 0.0 | — | — |
| school_algebra1 | 0.0 | 0.0 | 0.0 | — | — |
| school_finance | 0.0 | 0.0 | 0.0 | — | — |
| school_retention | 0.0 | 0.0 | 0.0 | **5.4** | 369.6 |
| southkorea_statistics_education | 0.0 | 0.0 | **188.5** | — | — |
| southkorea_statistics_employment | 20.5 | 23.3 | 17.9 | **44.0** | 417.8 |
| southkorea_statistics_health | 0.0 | **20.6** | **20.6** | 11.8 | 405.8 |
| statistics_new_zealand_new_zealand_census | 0.0 | 0.0 | 0.0 | — | — |
| uae_bayanat | 0.0 | 0.0 | 0.0 | — | — |
| undata | 98.9 | 7.9 | 10.1 | **102.2** | 319.6 |
| us_bachelors_degree_data | 0.0 | 0.0 | 0.0 | — | — |
| us_bls_bls_ces | 1.1 | 3.6 | **4.0** | 0.3 | 442.4 |
| us_bls_bls_ces_state | **1.1** | 0.3 | 0.4 | 0.6 | 449.3 |
| us_bls_cpi_category | **43.6** | 4.6 | 0.9 | 6.4 | 274.4 |
| us_bls_us_cpi | 5.6 | 37.0 | **103.7** | 3.7 | 482.0 |
| us_cdc_single_race | 17.1 | 13.2 | **19.7** | — | — |
| us_census | 28.1 | 15.7 | 16.9 | **44.0** | 751.1 |
| us_census_us_monthly_retail_sales | 37.5 | **56.2** | 12.5 | 0.8 | 602.9 |
| us_crash_fars_crashdata | **11.8** | **11.8** | 6.6 | — | — |
| us_federal_reserve_h15_interest_rates | 0.0 | 0.0 | 0.0 | — | — |
| us_steam_degrees_data | 13.5 | **17.3** | **17.3** | 13.5 | 256.0 |
| us_urban_school_teachers | 31.4 | 0.0 | 40.0 | **51.4** | 386.8 |
| usa_dol | 0.0 | 0.0 | 0.0 | — | — |
| usa_dol_minimum_wage | **90.5** | **90.5** | **90.5** | **90.5** | 410.5 |
| world_bank_commodity_market | **98.9** | 91.5 | 78.7 | 76.6 | 592.6 |
| zurich_bev_3240_wiki | **100.0** | **100.0** | **100.0** | **100.0** | 198.3 |
| zurich_bev_3903_age10_wiki | 33.3 | **100.0** | **100.0** | 26.7 | 276.4 |
| zurich_bev_3903_hel_wiki | **75.0** | **75.0** | **75.0** | 50.0 | 168.1 |
| zurich_bev_3903_sex_wiki | 66.7 | **100.0** | **100.0** | **100.0** | 128.1 |
| zurich_bev_4031_hel_wiki | **100.0** | **100.0** | **100.0** | 66.7 | 364.9 |
| zurich_bev_4031_sex_wiki | 66.7 | **100.0** | **100.0** | **100.0** | 170.2 |
| zurich_bev_4031_wiki | **100.0** | **100.0** | **100.0** | **100.0** | 136.6 |
| zurich_wir_2552_wiki | **100.0** | **100.0** | **100.0** | **100.0** | 152.7 |

---

## PV Accuracy Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % | Enhanced Pipeline % | Time (s) |
|---------|---------------|--------------|----------------|---------------------|----------|
| bis_bis_central_bank_policy_rate | 0.0 | 18.2 | **36.4** | 0.0 | 315.7 |
| brazil_sidra_ibge | **2.3** | **2.3** | **2.3** | **2.3** | 230.6 |
| brazil_visdata_FoodBasketDistribution | 2.9 | 0.0 | 0.0 | **6.1** | 243.8 |
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 | 0.0 | **4.2** | 345.3 |
| brfss_nchs_asthma_prevalence | 1.5 | 23.3 | 19.1 | **26.1** | 419.0 |
| ccd_enrollment | 23.2 | **31.9** | 0.0 | — | — |
| cdc_social_vulnerability_index | 4.9 | **28.3** | 14.6 | 20.5 | 562.3 |
| census_v2_sahie | 8.0 | **34.8** | 34.1 | 2.2 | 408.8 |
| census_v2_saipe | 35.7 | 50.0 | 53.3 | **58.8** | 302.9 |
| child_birth | 0.0 | 0.0 | 0.0 | — | — |
| commerce_eda | 0.0 | 0.0 | 6.7 | **26.2** | 490.4 |
| crdc_import_crdc_harassment_or_bullying | 0.0 | 0.0 | 0.0 | 0.0 | 507.9 |
| crdc_instructional_wifi_devices | 0.0 | 0.0 | 0.0 | — | — |
| database_on_indian_economy_india_rbi_state_statistics | 0.0 | 0.3 | **6.4** | 1.2 | 309.9 |
| doctoratedegreeemployment | 10.0 | **29.6** | 18.3 | 14.1 | 390.2 |
| fao_currency_and_exchange_rate | 0.0 | 0.0 | 0.0 | **0.3** | 214.7 |
| fbi_fbigovcrime | 0.0 | **8.2** | 6.6 | 0.5 | 397.2 |
| finland_census | 0.0 | 0.0 | 0.0 | — | — |
| google_sustainability_financial_incentives | 0.0 | 0.0 | 0.0 | — | — |
| india_ndap | 9.1 | 9.1 | 6.1 | **12.1** | 307.0 |
| india_ndap_india_nss_health_ailments | **21.6** | 0.0 | 0.0 | 2.5 | 362.5 |
| india_nfhs | 14.2 | 5.3 | **21.6** | 19.0 | 818.5 |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 0.0 | — | — |
| inpe_fire | 0.0 | 0.0 | **40.5** | 36.8 | 277.7 |
| ipeds | 0.0 | 0.0 | 0.0 | — | — |
| ireland_census | 0.0 | 0.0 | 0.0 | — | — |
| mexico_subnational_population_statistics_mexico_census_aa2 | 0.0 | 0.0 | 0.0 | — | — |
| ncses_median_annual_salary | **5.4** | **5.4** | **5.4** | **5.4** | 197.6 |
| ncses_ncses_demographics_seh_import | 3.9 | 6.2 | **8.1** | 0.7 | 500.4 |
| ncses_research_doctorate_recipients | 0.0 | 0.0 | 0.0 | — | — |
| ntia_internet_use_survey | 0.0 | 0.0 | 0.0 | — | — |
| nyu_diabetes_texas | 0.0 | 0.0 | 0.0 | — | — |
| oecd_regional_education | **5.3** | 2.6 | 2.6 | 2.6 | 206.9 |
| oecd_wastewater_treatment | 0.0 | 10.7 | 3.6 | **15.9** | 389.2 |
| opendataforafrica_ethiopia_statistics | 22.5 | **64.4** | **64.4** | **64.4** | 366.6 |
| opendataforafrica_kenya_census | 9.1 | 30.0 | 30.0 | **40.0** | 522.3 |
| opendataforafrica_rwanda_census | 0.0 | 0.0 | 0.0 | — | — |
| school_algebra1 | 0.0 | 0.0 | 0.0 | — | — |
| school_finance | 0.0 | 0.0 | 0.0 | — | — |
| school_retention | 0.0 | 0.0 | 0.0 | **2.0** | 369.6 |
| southkorea_statistics_education | 0.0 | 0.0 | 0.0 | — | — |
| southkorea_statistics_employment | 3.3 | 0.0 | 0.0 | **42.2** | 417.8 |
| southkorea_statistics_health | 0.0 | 1.5 | 1.5 | **4.3** | 405.8 |
| statistics_new_zealand_new_zealand_census | 0.0 | 0.0 | 0.0 | — | — |
| uae_bayanat | 0.0 | 0.0 | 0.0 | — | — |
| undata | 87.1 | **88.3** | **88.3** | 86.9 | 319.6 |
| us_bachelors_degree_data | 0.0 | 0.0 | 0.0 | — | — |
| us_bls_bls_ces | 0.0 | **0.4** | **0.4** | 0.1 | 442.4 |
| us_bls_bls_ces_state | 0.1 | **0.2** | **0.2** | 0.1 | 449.3 |
| us_bls_cpi_category | 0.0 | 0.0 | 0.0 | **4.0** | 274.4 |
| us_bls_us_cpi | 0.0 | 0.0 | **1.1** | **1.1** | 482.0 |
| us_cdc_single_race | 1.2 | 0.6 | **6.4** | — | — |
| us_census | 8.8 | 5.7 | 4.6 | **20.8** | 751.1 |
| us_census_us_monthly_retail_sales | **17.5** | 1.0 | 1.0 | 0.0 | 602.9 |
| us_crash_fars_crashdata | **2.1** | 1.0 | 1.2 | — | — |
| us_federal_reserve_h15_interest_rates | 0.0 | 0.0 | 0.0 | — | — |
| us_steam_degrees_data | **7.1** | **7.1** | **7.1** | **7.1** | 256.0 |
| us_urban_school_teachers | 2.1 | 0.0 | **8.2** | 6.5 | 386.8 |
| usa_dol | 0.0 | 0.0 | 0.0 | — | — |
| usa_dol_minimum_wage | 0.0 | **89.0** | **89.0** | 87.4 | 410.5 |
| world_bank_commodity_market | 3.7 | **35.5** | 32.7 | 23.5 | 592.6 |
| zurich_bev_3240_wiki | 0.0 | 33.3 | **50.0** | **50.0** | 198.3 |
| zurich_bev_3903_age10_wiki | 11.8 | 11.8 | **17.6** | **17.6** | 276.4 |
| zurich_bev_3903_hel_wiki | 0.0 | **30.0** | **30.0** | **30.0** | 168.1 |
| zurich_bev_3903_sex_wiki | 12.5 | **62.5** | 37.5 | **62.5** | 128.1 |
| zurich_bev_4031_hel_wiki | 0.0 | 25.0 | **37.5** | 25.0 | 364.9 |
| zurich_bev_4031_sex_wiki | 0.0 | 50.0 | **62.5** | **62.5** | 170.2 |
| zurich_bev_4031_wiki | 0.0 | 16.7 | **50.0** | 33.3 | 136.6 |
| zurich_wir_2552_wiki | 17.9 | 42.9 | **75.0** | 50.0 | 152.7 |

---
