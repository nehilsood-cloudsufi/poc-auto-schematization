# Ground Truth Validation Report (Upstream Files)

16 of 97 PVMAP files pass validation across 48 datasets.

Uses files from `datacommonsorg/data` repo instead of local consolidated inputs.

- PASS: 16
- FAIL: 69
- SKIP: 12

## Results

| Dataset | PVMAP File | Input File | Status | Data Rows | Upstream Dir | Error |
|---------|-----------|------------|--------|-----------|--------------|-------|
| bis_bis_central_bank_policy_rate | central_bank_policy_rate_pvmap.csv | WS_CBPOL_csv_flat_input.csv | FAIL | 0 | bis/bis_central_bank_policy_rate | processed.csv has 0 data rows |
| brazil_sidra_ibge |  |  | SKIP | 0 | brazil_sidra_ibge | no input CSV files found in brazil_sidra_ibge/test_data/ |
| brazil_visdata_FoodBasketDistribution | FoodBasket_EmergencyCare_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | FoodBasket_ExtractiveFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | FoodBasket_FishingFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | FoodBasket_IndigenousFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | FoodBasket_QuilombolaFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | FoodBasket_RecycledMaterialCollectorFamily_pvmap.csv | MunicipalFoodBasket_RecycledMaterialCollectorFamily_data.csv | PASS | 5 | brazil_visdata/FoodBasketDistribution |  |
| brazil_visdata_FoodBasketDistribution | FoodBaskets_SettledFamilies_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | FoodDistributionAct_FoodBasketByPartners_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | PASS | 176 | brazil_visdata/FoodBasketDistribution |  |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBasket_EmergencyCare_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBasket_ExtractiveFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBasket_FishingFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBasket_GypsyFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBasket_IndigenousFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBasket_QuilombolaFamily_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBasket_RecycledMaterialCollectorFamily_pvmap.csv | MunicipalFoodBasket_RecycledMaterialCollectorFamily_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodBaskets_SettledFamilies_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_FoodBasketDistribution | MunicipalFoodDistributionAct_FoodBasketByPartners_pvmap.csv | FoodDistributionAct_FoodBasketByPartners_data.csv | FAIL | 0 | brazil_visdata/FoodBasketDistribution | processed.csv has 0 data rows |
| brazil_visdata_brazil_rural_development_program |  |  | SKIP | 0 | brazil_visdata/brazil_rural_development_program | no input CSV files found in brazil_visdata/brazil_rural_development_program/test_data/ |
| brfss_nchs_asthma_prevalence |  |  | SKIP | 0 | brfss_nchs_asthma_prevalence | no PVMAP files found in brfss_nchs_asthma_prevalence |
| cdc_social_vulnerability_index | SVI_2010_US_county_pvmap.csv | SVI_2022_US_county_input.csv | PASS | 232 | cdc/social_vulnerability_index |  |
| cdc_social_vulnerability_index | pvmap.csv | SVI_2022_US_county_input.csv | PASS | 1131 | cdc/social_vulnerability_index |  |
| census_v2_sahie | census_sahie_pv_map.csv | census_sahie_input.csv | PASS | 1000 | census_v2/sahie |  |
| census_v2_saipe | saipe_pvmap.csv | saipe_test_input.csv | PASS | 72 | census_v2/saipe |  |
| commerce_eda | Estimatedpvmap.csv | commerce_eda_input.csv | FAIL | 0 | commerce_eda | processed.csv has 0 data rows |
| commerce_eda | Investmentpvmap.csv | commerce_eda_input.csv | FAIL | 0 | commerce_eda | processed.csv has 0 data rows |
| commerce_eda | Povertypvmap.csv | commerce_eda_input.csv | FAIL | 0 | commerce_eda | processed.csv has 0 data rows |
| crdc_import_crdc_harassment_or_bullying | harassment_or_bullying_pvmap.csv | harassment_or_bullying_data.csv | PASS | 3105 | crdc_import/crdc_harassment_or_bullying |  |
| database_on_indian_economy_india_rbi_state_statistics |  |  | SKIP | 0 | database_on_indian_economy/india_rbi_state_statistics | no input CSV files found in database_on_indian_economy/india_rbi_state_statistics/test_data/ |
| doctoratedegreeemployment | pv_map.csv | sample_input.csv | PASS | 338 | doctoratedegreeemployment |  |
| fao_currency_and_exchange_rate |  |  | SKIP | 0 | fao_currency_and_exchange_rate | no PVMAP files found in fao_currency_and_exchange_rate |
| fbi_fbigovcrime | fbigovcrime_pvmap.csv | fbigovcrime_input.csv | FAIL | 0 | fbi/fbigovcrime | processed.csv has 0 data rows |
| india_ndap |  |  | SKIP | 0 | india_ndap | no PVMAP files found in india_ndap |
| india_ndap_india_nss_health_ailments | india_nss_health_ailments_pvmap.csv | india_nss_health_ailments_input.csv | FAIL | 0 | india_ndap/india_nss_health_ailments | processed.csv has 0 data rows |
| india_nfhs | nfhs4pvmap.csv | india_nfhs5survey_input.csv | PASS | 144 | india_nfhs |  |
| india_nfhs | nfhs5pvmap.csv | india_nfhs5survey_input.csv | PASS | 2183 | india_nfhs |  |
| india_nfhs | nfhsStatepvmap.csv | india_nfhs5survey_input.csv | PASS | 7 | india_nfhs |  |
| inpe_fire | pvmap.csv | inpe_fire_event_count_input.csv | PASS | 9433 | inpe_fire |  |
| ncses_median_annual_salary |  |  | SKIP | 0 | ncses/ncses_median_annual_salary | no input CSV files found in ncses/ncses_median_annual_salary/test_data/ |
| ncses_ncses_demographics_seh_import | ncses_demographics_seh_import_pv_map.csv | ncses_demographics_seh_import_2021_input.csv | PASS | 110 | ncses/ncses_demographics_seh_import |  |
| oecd_regional_education | oecd_regional_education_pvmap.csv | oecd_regional_education_data.csv | FAIL | 0 | oecd/regional_education | processed.csv has 0 data rows |
| oecd_wastewater_treatment | oecd_wastewatertreatment_pvmap.csv | oecd_wastewater_treatment_input.csv | FAIL | 0 | oecd/wastewater_treatment | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at http://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_ethiopia_statistics | ethiopia-Ethiopia_Demographics_pvmap.csv | ethiopia-Ethiopia_Demographics_data.csv | FAIL | 0 | opendataforafrica/ethiopia_statistics | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_ethiopia_statistics | ethiopia-Ethiopia_Population_all_year_pvmap.csv | ethiopia-Ethiopia_Population_all_year_data.csv | FAIL | 0 | opendataforafrica/ethiopia_statistics | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_ethiopia_statistics | ethiopia-Population_Projection_by_Region_and_Sex_2022_pvmap.csv | ethiopia-Population_Projection_by_Region_and_Sex_2022_data.csv | FAIL | 0 | opendataforafrica/ethiopia_statistics | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_ethiopia_statistics | ethiopia-yusibcg_pvmap.csv | ethiopia-yusibcg_data.csv | FAIL | 0 | opendataforafrica/ethiopia_statistics | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_ethiopia_statistics | ethiopia_population_2007_pvmap.csv | ethiopia_population_2007_data.csv | FAIL | 0 | opendataforafrica/ethiopia_statistics | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | dlrrjxg_pvmap.csv | dlrrjxg_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | egdxgkd_pvmap.csv | egdxgkd_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | emxkej_pvmap.csv | emxkej_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | fwjfdnc_pvmap.csv | fwjfdnc_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | gxbucsd_pvmap.csv | gxbucsd_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | ixdvqrf_pvmap.csv | dlrrjxg_input.csv | FAIL | 0 | opendataforafrica/kenya_census | processed.csv has 0 data rows |
| opendataforafrica_kenya_census | rsfzlbg_pvmap.csv | rsfzlbg_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | srricmg_pvmap.csv | srricmg_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | tdxdksf_pvmap.csv | dlrrjxg_input.csv | FAIL | 0 | opendataforafrica/kenya_census | processed.csv has 0 data rows |
| opendataforafrica_kenya_census | vdbvyfd_pvmap.csv | vdbvyfd_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | welrttb_pvmap.csv | welrttb_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| opendataforafrica_kenya_census | xszlbb_pvmap.csv | xszlbb_input.csv | FAIL | 0 | opendataforafrica/kenya_census | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| southkorea_statistics_education | elementary_school_pvmap.csv | elementary_school_input.csv | FAIL | 0 | southkorea_statistics/education | processed.csv has 0 data rows |
| southkorea_statistics_education | high_school_pvmap.csv | high_school_input.csv | FAIL | 0 | southkorea_statistics/education | processed.csv has 0 data rows |
| southkorea_statistics_education | junior_college_pvmap.csv | junior_college_input.csv | FAIL | 0 | southkorea_statistics/education | processed.csv has 0 data rows |
| southkorea_statistics_education | kindergarten_pvmap.csv | kindergarten_input.csv | FAIL | 0 | southkorea_statistics/education | processed.csv has 0 data rows |
| southkorea_statistics_education | middle_school_pvmap.csv | middle_school_input.csv | FAIL | 0 | southkorea_statistics/education | processed.csv has 0 data rows |
| southkorea_statistics_employment | employmentstatus_pvmap.csv | southkorea_employmentstatus_data.csv | PASS | 16 | southkorea_statistics/employment |  |
| southkorea_statistics_employment | sexandeducationalattainment_unemploymentstatus_pvmap.csv | southkorea_sexandeducationalattainment_unemploymentstatus_data.csv | PASS | 24 | southkorea_statistics/employment |  |
| southkorea_statistics_employment | unemploymentrate_by_gender_age_pvmap.csv | southkorea_unemploymentrate_by_gender_age_data.csv | PASS | 55 | southkorea_statistics/employment |  |
| southkorea_statistics_employment | unemploymentstatus_pvmap.csv | southkorea_sexandeducationalattainment_unemploymentstatus_data.csv | FAIL | 0 | southkorea_statistics/employment | processed.csv has 0 data rows |
| southkorea_statistics_health | diseasereport_pvmap.csv | health_data.csv | FAIL | 0 | southkorea_statistics/health | processed.csv has 0 data rows |
| southkorea_statistics_health | health_pvmap.csv | health_data.csv | FAIL | 0 | southkorea_statistics/health | processed.csv has 0 data rows |
| undata | UNData_pvmap.csv | UNData_input.csv | FAIL | 0 | undata | processed.csv has 0 data rows |
| us_bls_bls_ces | bls_ces_pvmap.csv | bls_ces_input.csv | FAIL | 0 | us_bls/bls_ces | processed.csv has 0 data rows |
| us_bls_bls_ces_state | bls_ces_state_pvmap.csv | bls_ces_state_input.csv | FAIL | 0 | us_bls/bls_ces_state | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| us_bls_cpi_category |  |  | SKIP | 0 | us_bls/cpi_category | no input CSV files found in us_bls/cpi_category/test_data/ |
| us_bls_us_cpi |  |  | SKIP | 0 | us_bls/us_cpi | no input CSV files found in us_bls/us_cpi/test_data/ |
| us_cdc_single_race | single_race_pvmap.csv | underlyingcauseofdeath2018_2023singlerace_input.csv | FAIL | 0 | us_cdc/single_race | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| us_census |  |  | SKIP | 0 | us_census | no PVMAP files found in us_census |
| us_census_us_monthly_retail_sales |  |  | SKIP | 0 | us_census/us_monthly_retail_sales | no input CSV files found in us_census/us_monthly_retail_sales/test_data/ |
| us_crash_fars_crashdata | fars_crash_pvmap.csv | fars_test_input.csv | FAIL | 0 | us_crash/fars_crashdata | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| us_steam_degrees_data |  |  | SKIP | 0 | us_steam_degrees_data | no PVMAP files found in us_steam_degrees_data |
| us_urban_school_teachers | teachers_and_staff_pvmap.csv | teachers_and_staff_input.csv | FAIL | 0 | us_urban_school/teachers | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| usa_dol_minimum_wage | us_dol_wages_pvmap.csv | us_dol_wages_data.csv | FAIL | 0 | usa_dol/minimum_wage | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| world_bank_commodity_market | commodity_annual_indices_pvmap_nominal.csv | commodity_monthly_price_data_input.csv | FAIL | 0 | world_bank/commodity_market | processed.csv has 0 data rows |
| world_bank_commodity_market | commodity_annual_indices_pvmap_real.csv | commodity_monthly_price_data_input.csv | FAIL | 0 | world_bank/commodity_market | processed.csv has 0 data rows |
| world_bank_commodity_market | commodity_annual_price_pvmap_nominal.csv | commodity_monthly_price_data_input.csv | FAIL | 0 | world_bank/commodity_market | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| world_bank_commodity_market | commodity_annual_price_pvmap_real.csv | commodity_monthly_price_data_input.csv | FAIL | 0 | world_bank/commodity_market | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| world_bank_commodity_market | commodity_monthly_indices_pvmap.csv | commodity_monthly_price_data_input.csv | FAIL | 0 | world_bank/commodity_market | processed.csv has 0 data rows |
| world_bank_commodity_market | commodity_monthly_price_pvmap.csv | commodity_monthly_price_data_input.csv | FAIL | 0 | world_bank/commodity_market | processed.csv has 0 data rows |
| zurich_bev_3240_wiki | bev_3240_wiki_pvmap.csv | bev_3240_wiki_input.csv | FAIL | 0 | zurich/bev_3240_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| zurich_bev_3903_age10_wiki | bev_3903_age10_wiki_pvmap.csv | bev_3903_age10_wiki_input.csv | FAIL | 0 | zurich/bev_3903_age10_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| zurich_bev_3903_hel_wiki | bev_3903_hel_wiki_pvmap.csv | bev_3903_hel_wiki_utf8_input.csv | FAIL | 0 | zurich/bev_3903_hel_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| zurich_bev_3903_sex_wiki | bev_3903_sex_wiki_pvmap.csv | bev_3903_sex_wiki_input.csv | FAIL | 0 | zurich/bev_3903_sex_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| zurich_bev_4031_hel_wiki | bev_4031_hel_wiki_pvmap.csv | bev_4031_hel_wiki_input.csv | FAIL | 0 | zurich/bev_4031_hel_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| zurich_bev_4031_sex_wiki | bev_4031_sex_wiki_pvmap.csv | bev_4031_sex_wiki_input.csv | FAIL | 0 | zurich/bev_4031_sex_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| zurich_bev_4031_wiki | bev_4031_wiki_pvmap.csv | bev_4031_wiki_input.csv | FAIL | 0 | zurich/bev_4031_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |
| zurich_wir_2552_wiki | wir_2552_wiki_pvmap.csv | wir_2552_wiki_input.csv | FAIL | 0 | zurich/wir_2552_wiki | DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>> |

## Failures

- **bis_bis_central_bank_policy_rate** / `central_bank_policy_rate_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `FoodBasket_EmergencyCare_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `FoodBasket_ExtractiveFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `FoodBasket_FishingFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `FoodBasket_IndigenousFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `FoodBasket_QuilombolaFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `FoodBaskets_SettledFamilies_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBasket_EmergencyCare_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBasket_ExtractiveFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBasket_FishingFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBasket_GypsyFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBasket_IndigenousFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBasket_QuilombolaFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBasket_RecycledMaterialCollectorFamily_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodBaskets_SettledFamilies_pvmap.csv`: processed.csv has 0 data rows
- **brazil_visdata_FoodBasketDistribution** / `MunicipalFoodDistributionAct_FoodBasketByPartners_pvmap.csv`: processed.csv has 0 data rows
- **commerce_eda** / `Estimatedpvmap.csv`: processed.csv has 0 data rows
- **commerce_eda** / `Investmentpvmap.csv`: processed.csv has 0 data rows
- **commerce_eda** / `Povertypvmap.csv`: processed.csv has 0 data rows
- **fbi_fbigovcrime** / `fbigovcrime_pvmap.csv`: processed.csv has 0 data rows
- **india_ndap_india_nss_health_ailments** / `india_nss_health_ailments_pvmap.csv`: processed.csv has 0 data rows
- **oecd_regional_education** / `oecd_regional_education_pvmap.csv`: processed.csv has 0 data rows
- **oecd_wastewater_treatment** / `oecd_wastewatertreatment_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at http://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_ethiopia_statistics** / `ethiopia-Ethiopia_Demographics_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_ethiopia_statistics** / `ethiopia-Ethiopia_Population_all_year_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_ethiopia_statistics** / `ethiopia-Population_Projection_by_Region_and_Sex_2022_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_ethiopia_statistics** / `ethiopia-yusibcg_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_ethiopia_statistics** / `ethiopia_population_2007_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `dlrrjxg_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `egdxgkd_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `emxkej_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `fwjfdnc_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `gxbucsd_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `ixdvqrf_pvmap.csv`: processed.csv has 0 data rows
- **opendataforafrica_kenya_census** / `rsfzlbg_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `srricmg_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `tdxdksf_pvmap.csv`: processed.csv has 0 data rows
- **opendataforafrica_kenya_census** / `vdbvyfd_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `welrttb_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **opendataforafrica_kenya_census** / `xszlbb_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **southkorea_statistics_education** / `elementary_school_pvmap.csv`: processed.csv has 0 data rows
- **southkorea_statistics_education** / `high_school_pvmap.csv`: processed.csv has 0 data rows
- **southkorea_statistics_education** / `junior_college_pvmap.csv`: processed.csv has 0 data rows
- **southkorea_statistics_education** / `kindergarten_pvmap.csv`: processed.csv has 0 data rows
- **southkorea_statistics_education** / `middle_school_pvmap.csv`: processed.csv has 0 data rows
- **southkorea_statistics_employment** / `unemploymentstatus_pvmap.csv`: processed.csv has 0 data rows
- **southkorea_statistics_health** / `diseasereport_pvmap.csv`: processed.csv has 0 data rows
- **southkorea_statistics_health** / `health_pvmap.csv`: processed.csv has 0 data rows
- **undata** / `UNData_pvmap.csv`: processed.csv has 0 data rows
- **us_bls_bls_ces** / `bls_ces_pvmap.csv`: processed.csv has 0 data rows
- **us_bls_bls_ces_state** / `bls_ces_state_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **us_cdc_single_race** / `single_race_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **us_crash_fars_crashdata** / `fars_crash_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **us_urban_school_teachers** / `teachers_and_staff_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **usa_dol_minimum_wage** / `us_dol_wages_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **world_bank_commodity_market** / `commodity_annual_indices_pvmap_nominal.csv`: processed.csv has 0 data rows
- **world_bank_commodity_market** / `commodity_annual_indices_pvmap_real.csv`: processed.csv has 0 data rows
- **world_bank_commodity_market** / `commodity_annual_price_pvmap_nominal.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **world_bank_commodity_market** / `commodity_annual_price_pvmap_real.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **world_bank_commodity_market** / `commodity_monthly_indices_pvmap.csv`: processed.csv has 0 data rows
- **world_bank_commodity_market** / `commodity_monthly_price_pvmap.csv`: processed.csv has 0 data rows
- **zurich_bev_3240_wiki** / `bev_3240_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **zurich_bev_3903_age10_wiki** / `bev_3903_age10_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **zurich_bev_3903_hel_wiki** / `bev_3903_hel_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **zurich_bev_3903_sex_wiki** / `bev_3903_sex_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **zurich_bev_4031_hel_wiki** / `bev_4031_hel_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **zurich_bev_4031_sex_wiki** / `bev_4031_sex_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **zurich_bev_4031_wiki** / `bev_4031_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>
- **zurich_wir_2552_wiki** / `wir_2552_wiki_pvmap.csv`: DC API call failed after 3 attempts: <bound method NodeEndpoint.fetch of <Node Endpoint using <API at https://api.datacommons.org/v2 (Authenticated)>>>

## Skipped

- **brazil_sidra_ibge**: no input CSV files found in brazil_sidra_ibge/test_data/
- **brazil_visdata_brazil_rural_development_program**: no input CSV files found in brazil_visdata/brazil_rural_development_program/test_data/
- **brfss_nchs_asthma_prevalence**: no PVMAP files found in brfss_nchs_asthma_prevalence
- **database_on_indian_economy_india_rbi_state_statistics**: no input CSV files found in database_on_indian_economy/india_rbi_state_statistics/test_data/
- **fao_currency_and_exchange_rate**: no PVMAP files found in fao_currency_and_exchange_rate
- **india_ndap**: no PVMAP files found in india_ndap
- **ncses_median_annual_salary**: no input CSV files found in ncses/ncses_median_annual_salary/test_data/
- **us_bls_cpi_category**: no input CSV files found in us_bls/cpi_category/test_data/
- **us_bls_us_cpi**: no input CSV files found in us_bls/us_cpi/test_data/
- **us_census**: no PVMAP files found in us_census
- **us_census_us_monthly_retail_sales**: no input CSV files found in us_census/us_monthly_retail_sales/test_data/
- **us_steam_degrees_data**: no PVMAP files found in us_steam_degrees_data
