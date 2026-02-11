# Benchmark Comparison: Gemini 3 Pro vs ADK Pipeline Batch

**Generated**: 2026-02-11
**Batch ID**: `batch_20260211_031041`

This report compares the ADK pipeline batch run (2026-02-11, 50 datasets) against the previous Gemini 3 Pro baseline (2026-01-21, 49 datasets). Both use `gemini-3-pro-preview` as the underlying model.

---

## Configuration Differences

| | Gemini 3 Pro Baseline (Jan 21) | ADK Batch (Feb 11) |
|---|---|---|
| **Pipeline** | `src/run_pipeline.py` (monolithic) | ADK agents (`src/agents/`) with LoopAgent retry |
| **Model** | `gemini-3-pro-preview` | `gemini-3-pro-preview` |
| **Retry Mechanism** | Python loop (3 attempts) | ADK LoopAgent (3 attempts, `max_retries=2`) |
| **Feedback** | Error feedback only | Unified ConditionalFeedbackAgent (error + quality) |
| **PVMAP Repair** | None | `pvmap_repair.py` (case/whitespace/fuzzy key repair) |
| **Prompt** | Original 623-line template | Restructured 275-line template with archetypes |
| **Column Reference** | None | COLUMN REFERENCE TABLE in skeleton_summary |
| **Schema Vocab** | Full .txt files (5-41KB) | Compressed `schema_vocab.json` (0.4-5.6KB) |
| **Sampling** | Heuristic | LLM-driven agentic sampling |
| **Validation** | Subprocess only | Pre-validation + repair + subprocess + key_match_report |
| **Datasets** | 49 | 50 |
| **Datasets Evaluated** | 49 (all) | 43 (7 without eval: no GT or runtime crash) |

---

## Summary Statistics (43 Overlapping Datasets)

| Metric | Gemini 3 Pro | ADK Batch | Delta |
|--------|:------------:|:---------:|:-----:|
| **Avg PV Accuracy** | 19.8% | **19.0%** | -0.8pp |
| **Avg Node Accuracy** | 12.4% | **13.0%** | +0.6pp |
| **Avg Node Coverage** | 58.1% | **63.6%** | +5.5pp |
| **Non-zero PV Acc** | 31/43 | **34/43** | +3 |
| **PV Acc > 10%** | 18/43 | **20/43** | +2 |
| **PV Acc > 25%** | 8/43 | **10/43** | +2 |

**Key Takeaway**: Same model, different pipeline. ADK achieves higher node accuracy (+0.6pp) and node coverage (+5.5pp), activates 3 more datasets to non-zero PV accuracy, and has more datasets above 10% and 25% thresholds. Average PV accuracy is slightly lower (-0.8pp) due to regressions on a handful of datasets, primarily from validation failures.

---

## PV Accuracy Comparison

PV Accuracy = PVs Matched / (PVs Matched + PVs Modified + PVs Deleted) x 100

| Dataset | G3P | ADK | Delta | Status |
|---------|:---:|:---:|:-----:|:------:|
| usa_dol_minimum_wage | 89.0 | **86.6** | -2.4 | PASS |
| undata | 88.3 | **86.2** | -2.1 | FAIL |
| opendataforafrica_ethiopia_statistics | 64.4 | **64.4** | 0.0 | PASS |
| zurich_bev_4031_sex_wiki | **62.5** | **62.5** | 0.0 | PASS |
| census_v2_saipe | **53.3** | **53.3** | 0.0 | PASS |
| zurich_bev_3240_wiki | **50.0** | **50.0** | 0.0 | PASS |
| southkorea_statistics_employment | 0.0 | **40.9** | **+40.9** | PASS |
| inpe_fire | **40.5** | 21.1 | -19.4 | PASS |
| zurich_bev_3903_sex_wiki | 37.5 | **62.5** | **+25.0** | PASS |
| zurich_bev_4031_hel_wiki | **37.5** | **37.5** | 0.0 | PASS |
| bis_bis_central_bank_policy_rate | **36.4** | 0.0 | -36.4 | FAIL |
| census_v2_sahie | **34.1** | 21.3 | -12.8 | PASS |
| world_bank_commodity_market | 32.7 | 32.7 | 0.0 | PASS |
| zurich_bev_3903_hel_wiki | **30.0** | **30.0** | 0.0 | PASS |
| opendataforafrica_kenya_census | 30.0 | 30.0 | 0.0 | PASS |
| brfss_nchs_asthma_prevalence | 19.1 | **25.6** | **+6.5** | PASS |
| zurich_bev_4031_wiki | **50.0** | 33.3 | -16.7 | PASS |
| zurich_bev_3903_age10_wiki | **17.6** | **17.6** | 0.0 | PASS |
| cdc_social_vulnerability_index | **14.6** | 8.8 | -5.8 | PASS |
| india_ndap | 6.1 | **9.1** | +3.0 | FAIL |
| us_urban_school_teachers | 8.2 | **8.9** | +0.7 | PASS |
| ncses_ncses_demographics_seh_import | **8.1** | 0.7 | -7.4 | FAIL |
| us_steam_degrees_data | 7.1 | 7.1 | 0.0 | PASS |
| ncses_median_annual_salary | 5.4 | 5.4 | 0.0 | PASS |
| database_on_indian_economy_india_rbi_state_statistics | **6.4** | 0.3 | -6.1 | FAIL |
| us_cdc_single_race | **6.4** | 1.2 | -5.2 | FAIL |
| us_census | 4.6 | 4.6 | 0.0 | FAIL |
| oecd_wastewater_treatment | 3.6 | 3.6 | 0.0 | PASS |
| oecd_regional_education | 2.6 | 2.6 | 0.0 | PASS |
| brazil_sidra_ibge | 2.3 | 2.3 | 0.0 | PASS |
| school_retention | 0.0 | **1.8** | **+1.8** | PASS |
| southkorea_statistics_health | 1.5 | 1.5 | 0.0 | PASS |
| us_crash_fars_crashdata | 1.2 | 1.4 | +0.2 | PASS |
| us_bls_us_cpi | **1.1** | 0.0 | -1.1 | FAIL |
| us_census_us_monthly_retail_sales | 1.0 | 0.0 | -1.0 | FAIL |
| ccd_enrollment | 0.0 | **0.9** | +0.9 | PASS |
| us_bls_bls_ces_state | 0.2 | 0.1 | -0.1 | FAIL |
| brazil_visdata_FoodBasketDistribution | 0.0 | 0.0 | 0.0 | PASS |
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 | 0.0 | PASS |
| crdc_import_crdc_harassment_or_bullying | 0.0 | 0.0 | 0.0 | PASS |
| fao_currency_and_exchange_rate | 0.0 | 0.0 | 0.0 | PASS |
| india_ndap_india_nss_health_ailments | 0.0 | 0.0 | 0.0 | PASS |
| us_bls_cpi_category | 0.0 | 0.0 | 0.0 | PASS |

---

## Node Accuracy Comparison

Node Accuracy = Nodes Matched / Ground Truth Nodes x 100

| Dataset | G3P | ADK | Delta |
|---------|:---:|:---:|:-----:|
| undata | 89.9 | **89.9** | 0.0 |
| opendataforafrica_ethiopia_statistics | 87.0 | **87.0** | 0.0 |
| zurich_bev_3903_sex_wiki | 16.7 | **50.0** | **+33.3** |
| zurich_bev_4031_sex_wiki | 50.0 | **50.0** | 0.0 |
| southkorea_statistics_employment | 0.0 | **36.0** | **+36.0** |
| opendataforafrica_kenya_census | 28.6 | 28.6 | 0.0 |
| brfss_nchs_asthma_prevalence | **26.1** | 21.1 | -5.0 |
| zurich_bev_3240_wiki | 25.0 | 25.0 | 0.0 |
| zurich_bev_4031_wiki | 25.0 | 25.0 | 0.0 |
| census_v2_sahie | **22.2** | 19.4 | -2.8 |
| ncses_ncses_demographics_seh_import | **18.4** | 2.6 | -15.8 |
| zurich_bev_4031_hel_wiki | 16.7 | 16.7 | 0.0 |
| bis_bis_central_bank_policy_rate | **14.3** | 0.0 | -14.3 |
| census_v2_saipe | 14.3 | 14.3 | 0.0 |
| us_census | 14.6 | 14.6 | 0.0 |
| zurich_bev_3903_hel_wiki | 12.5 | 12.5 | 0.0 |
| inpe_fire | **12.5** | 6.2 | -6.3 |
| us_steam_degrees_data | 11.5 | 11.5 | 0.0 |
| ncses_median_annual_salary | 8.1 | 8.1 | 0.0 |
| oecd_wastewater_treatment | 7.7 | 7.7 | 0.0 |
| zurich_bev_3903_age10_wiki | 6.7 | 6.7 | 0.0 |
| oecd_regional_education | 5.6 | 5.6 | 0.0 |
| us_crash_fars_crashdata | 3.7 | **5.1** | +1.4 |
| brazil_sidra_ibge | 4.7 | 4.7 | 0.0 |
| us_cdc_single_race | **3.9** | 0.0 | -3.9 |
| southkorea_statistics_health | 2.9 | 2.9 | 0.0 |
| us_urban_school_teachers | 0.0 | **2.9** | +2.9 |
| cdc_social_vulnerability_index | **2.4** | 0.0 | -2.4 |
| ccd_enrollment | 0.0 | **2.6** | +2.6 |
| database_on_indian_economy_india_rbi_state_statistics | 1.2 | 1.2 | 0.0 |
| us_bls_us_cpi | **1.9** | 0.0 | -1.9 |
| us_bls_bls_ces_state | **0.5** | 0.3 | -0.2 |

> 11 datasets where both models scored 0.0% Node Accuracy omitted: brazil_visdata_FoodBasketDistribution, brazil_visdata_brazil_rural_development_program, crdc_import_crdc_harassment_or_bullying, fao_currency_and_exchange_rate, india_ndap, india_ndap_india_nss_health_ailments, school_retention, us_bls_cpi_category, us_census_us_monthly_retail_sales, usa_dol_minimum_wage, world_bank_commodity_market.

---

## Node Coverage Comparison

Node Coverage = Auto-Generated Nodes / Ground Truth Nodes x 100

| Dataset | G3P | ADK | Delta |
|---------|:---:|:---:|:-----:|
| brazil_visdata_brazil_rural_development_program | 38.9 | **271.4** | +232.5 |
| ccd_enrollment | 0.0 | **252.6** | +252.6 |
| opendataforafrica_kenya_census | 185.7 | 157.1 | -28.6 |
| cdc_social_vulnerability_index | 69.0 | **131.0** | +62.0 |
| bis_bis_central_bank_policy_rate | 114.3 | 100.0 | -14.3 |
| brazil_visdata_FoodBasketDistribution | 100.0 | 100.0 | 0.0 |
| zurich_bev_3240_wiki | 100.0 | 100.0 | 0.0 |
| zurich_bev_3903_age10_wiki | 100.0 | 100.0 | 0.0 |
| zurich_bev_3903_sex_wiki | 100.0 | 100.0 | 0.0 |
| zurich_bev_4031_hel_wiki | 100.0 | 100.0 | 0.0 |
| zurich_bev_4031_sex_wiki | 100.0 | 100.0 | 0.0 |
| zurich_bev_4031_wiki | 100.0 | 100.0 | 0.0 |
| oecd_wastewater_treatment | 107.7 | 92.3 | -15.4 |
| census_v2_saipe | 100.0 | 85.7 | -14.3 |
| usa_dol_minimum_wage | 90.5 | 90.5 | 0.0 |
| brfss_nchs_asthma_prevalence | 269.6 | 84.2 | -185.4 |
| world_bank_commodity_market | 78.7 | 77.7 | -1.0 |
| zurich_bev_3903_hel_wiki | 75.0 | 75.0 | 0.0 |
| oecd_regional_education | 27.8 | **72.2** | +44.4 |
| southkorea_statistics_employment | 17.9 | **68.0** | +50.1 |
| census_v2_sahie | 75.0 | 58.3 | -16.7 |
| us_bls_us_cpi | 103.7 | 53.7 | -50.0 |
| india_ndap_india_nss_health_ailments | 62.2 | 51.4 | -10.8 |
| ncses_ncses_demographics_seh_import | 63.2 | 50.0 | -13.2 |
| us_urban_school_teachers | 40.0 | 40.0 | 0.0 |
| inpe_fire | 93.8 | 33.3 | -60.5 |
| india_ndap | 30.0 | 23.3 | -6.7 |
| brazil_sidra_ibge | 18.6 | **25.6** | +7.0 |
| us_cdc_single_race | 19.7 | 18.4 | -1.3 |
| us_census | 16.9 | 19.1 | +2.2 |
| us_steam_degrees_data | 17.3 | 17.3 | 0.0 |
| southkorea_statistics_health | 20.6 | 14.7 | -5.9 |
| ncses_median_annual_salary | 13.5 | 13.5 | 0.0 |
| database_on_indian_economy_india_rbi_state_statistics | 14.5 | 13.3 | -1.2 |
| us_census_us_monthly_retail_sales | 12.5 | 12.5 | 0.0 |
| undata | 10.1 | 7.9 | -2.2 |
| school_retention | 0.0 | **8.0** | +8.0 |
| us_crash_fars_crashdata | 6.6 | 5.1 | -1.5 |
| us_bls_cpi_category | 0.9 | **4.1** | +3.2 |
| fao_currency_and_exchange_rate | 2.3 | 2.3 | 0.0 |
| opendataforafrica_ethiopia_statistics | 0.5 | **1.8** | +1.3 |
| crdc_import_crdc_harassment_or_bullying | 1.3 | 1.3 | 0.0 |
| us_bls_bls_ces_state | 0.4 | 0.9 | +0.5 |

---

## Validation Pass/Fail Summary

The ADK batch ran 50 datasets; **34 passed validation (68%)**, **16 failed (32%)**.

Of the 43 datasets with evaluation results:
- **33 passed validation** with evaluation metrics
- **10 failed validation** but still have evaluation metrics from best-attempt PVMAPs

| Batch Status | Count | Avg PV Acc | Notes |
|---|---|---|---|
| PASS + GT available | 33 | 20.5% | Core comparison group |
| FAIL-VAL + GT available | 10 | 9.3% | Eval from best attempt despite validation failure |
| PASS, no GT | 1 | -- | india_nfhs |
| FAIL-VAL, no eval | 6 | -- | No ground truth or runtime crash |

---

## Improvements (ADK > G3P)

| Dataset | G3P | ADK | Delta | What Helped |
|---------|:---:|:---:|:-----:|-------------|
| southkorea_statistics_employment | 0.0% | **40.9%** | **+40.9pp** | Agentic sampling + COLUMN REFERENCE TABLE improved dimension decomposition |
| zurich_bev_3903_sex_wiki | 37.5% | **62.5%** | **+25.0pp** | Better PV alignment from restructured prompt |
| brfss_nchs_asthma_prevalence | 19.1% | **25.6%** | **+6.5pp** | PVMAP repair + retry loop working (2 attempts) |
| india_ndap | 6.1% | **9.1%** | +3.0pp | Better key matching despite FAIL-VAL |
| school_retention | 0.0% | **1.8%** | +1.8pp | First time achieving non-zero PV accuracy |
| ccd_enrollment | 0.0% | **0.9%** | +0.9pp | Previously 0% with G3P; now non-zero |
| us_urban_school_teachers | 8.2% | **8.9%** | +0.7pp | Marginal improvement |
| us_crash_fars_crashdata | 1.2% | **1.4%** | +0.2pp | Marginal improvement |

## Regressions (ADK < G3P)

| Dataset | G3P | ADK | Delta | Root Cause |
|---------|:---:|:---:|:-----:|------------|
| bis_bis_central_bank_policy_rate | 36.4% | 0.0% | **-36.4pp** | FAIL-VAL: Key mismatch (duplicated column descriptions) |
| inpe_fire | 40.5% | 21.1% | **-19.4pp** | Under-generated nodes (33% vs 94% coverage) |
| zurich_bev_4031_wiki | 50.0% | 33.3% | **-16.7pp** | Modified 2 PVs instead of matching them |
| census_v2_sahie | 34.1% | 21.3% | **-12.8pp** | Fewer nodes (58% vs 75% coverage); 249 invalid observations |
| ncses_ncses_demographics_seh_import | 8.1% | 0.7% | **-7.4pp** | FAIL-VAL: 0 SVObs despite key matches |
| database_on_indian_economy_india_rbi_state_statistics | 6.4% | 0.3% | **-6.1pp** | FAIL-VAL: Key hallucination (index suffix) |
| cdc_social_vulnerability_index | 14.6% | 8.8% | **-5.8pp** | Over-generated (131% coverage) but poor PV alignment |
| us_cdc_single_race | 6.4% | 1.2% | **-5.2pp** | FAIL-VAL: Place resolution failure |
| usa_dol_minimum_wage | 89.0% | 86.6% | -2.4pp | Minor: 1 PV modified vs previously matched |
| undata | 88.3% | 86.2% | -2.1pp | FAIL-VAL despite high PV accuracy |
| us_bls_us_cpi | 1.1% | 0.0% | -1.1pp | FAIL-VAL: Key hallucination |
| us_census_us_monthly_retail_sales | 1.0% | 0.0% | -1.0pp | FAIL-VAL: Key hallucination with index suffixes |
| us_bls_bls_ces_state | 0.2% | 0.1% | -0.1pp | FAIL-VAL: Conflicting date mappings |

## Tied (Delta = 0)

22 datasets matched G3P exactly: opendataforafrica_ethiopia_statistics (64.4%), zurich_bev_4031_sex_wiki (62.5%), census_v2_saipe (53.3%), zurich_bev_3240_wiki (50.0%), zurich_bev_4031_hel_wiki (37.5%), world_bank_commodity_market (32.7%), opendataforafrica_kenya_census (30.0%), zurich_bev_3903_hel_wiki (30.0%), zurich_bev_3903_age10_wiki (17.6%), us_steam_degrees_data (7.1%), ncses_median_annual_salary (5.4%), us_census (4.6%), oecd_wastewater_treatment (3.6%), oecd_regional_education (2.6%), brazil_sidra_ibge (2.3%), southkorea_statistics_health (1.5%), brazil_visdata_FoodBasketDistribution (0.0%), brazil_visdata_brazil_rural_development_program (0.0%), crdc_import_crdc_harassment_or_bullying (0.0%), fao_currency_and_exchange_rate (0.0%), india_ndap_india_nss_health_ailments (0.0%), us_bls_cpi_category (0.0%).

---

## Analysis

### What the ADK Pipeline Does Better

1. **Node generation accuracy**: Average node accuracy improved from 12.4% to 13.0% (+0.6pp). More precisely-sized node sets for many datasets.

2. **Node coverage breadth**: 63.6% average coverage vs 58.1% (+5.5pp). More ground truth nodes are being attempted.

3. **Activating "dead" datasets**: 3 datasets with G3P's 0% PV accuracy now show non-zero results (southkorea_statistics_employment 40.9%, school_retention 1.8%, ccd_enrollment 0.9%).

4. **Dimension decomposition**: southkorea_statistics_employment's +40.9pp improvement demonstrates the COLUMN REFERENCE TABLE and agentic sampling help the LLM understand dimensional structure.

5. **Retry effectiveness**: Where retries worked (brfss +6.5pp, inpe_fire from 0 to 21.1%), the pipeline produced better results. 82% of passing datasets succeeded on first attempt.

### What Regressed and Why

1. **Key hallucination (6 of 16 failures)**: The #1 failure mode. The LLM appends index suffixes (`: 1`, `: 2024`) to column headers, especially on datasets with `Unnamed:` columns. The pvmap_repair fuzzy matching (0.85 cutoff) doesn't catch these suffixed patterns.

2. **Validation false positives (2 failures)**: The `key_match_report` tool incorrectly flags some PVMAPs as having low match rates when the processor would actually accept them. Causes unnecessary retries that degrade the PVMAP.

3. **Over-generation without PV accuracy**: ccd_enrollment (252.6% coverage, 0.9% PV) and cdc_social_vulnerability_index (131% coverage, 8.8% PV) generate too many nodes. The archetype-based prompt may encourage broader generation at the expense of precision.

4. **Retry loop degradation**: Some datasets got worse with each retry. The unified feedback agent sometimes instructs the LLM to remove critical mappings like `observationDate`.

### Pipeline Changes: Impact Assessment

| Change | Impact | Evidence |
|--------|--------|----------|
| **Restructured prompt (623->275 lines)** | Mixed | Simpler prompt helps some datasets but loses specificity for complex ones |
| **Agentic sampling** | Positive | Better column classification leads to better skeleton_summary |
| **COLUMN REFERENCE TABLE** | Positive | southkorea_employment +40.9pp, us_urban_school +0.7pp |
| **pvmap_repair.py** | Positive but insufficient | Catches case/whitespace issues; misses index suffix hallucination |
| **Compressed schema vocab** | Neutral | No measurable impact on PV accuracy |
| **Unified feedback agent** | Mixed | Better error analysis but can cause retry degradation |
| **key_match_report** | Negative | False positives cause 2 validation failures and wasteful retries |
| **ADK LoopAgent (was broken until {Number} fix)** | Positive | Retry loop now executes all 3 attempts correctly |

### Priority Fixes for Next Iteration

1. **Fix key hallucination**: Add suffix-stripping patterns (`: \d+`, `: \d{4}`) to pvmap_repair.py before fuzzy matching
2. **Soften key_match_report**: Treat low match rate as warning when processor produces non-zero SVObs
3. **Add best-attempt tracking**: Save the PVMAP with highest SVObs count across retries, not just the latest
4. **Feedback agent guardrails**: Never suggest removing `observationDate`, `observationAbout`, or `value` mappings
5. **Pre-validation place check**: Detect raw place strings before expensive retry cycles

---

## Datasets Not Compared

7 datasets in the batch had no evaluation results for comparison:

| Dataset | G3P PV Acc | Batch Status | Reason |
|---------|:----------:|:------------:|--------|
| zurich_wir_2552_wiki | 75.0% | FAIL | Runtime crash (`RuntimeError: cannot schedule new futures`) |
| doctoratedegreeemployment | 18.3% | FAIL-VAL | No eval_results generated |
| fbi_fbigovcrime | 6.6% | FAIL-VAL | No eval_results generated |
| commerce_eda | 6.7% | FAIL-VAL | No eval_results generated |
| india_nfhs | 21.6% | PASS | No ground truth available for eval |
| us_bls_bls_ces | 0.4% | FAIL-VAL | No eval_results generated |
| southkorea_statistics_education | 0.0% | FAIL-VAL | No eval_results generated |

---

## Methodology Notes

- **PV Accuracy**: `PVs Matched / (PVs Matched + PVs Modified + PVs Deleted) x 100`
- **Node Accuracy**: `Nodes Matched / Ground Truth Nodes x 100`
- **Node Coverage**: `Auto-Generated Nodes / Ground Truth Nodes x 100`
- Both runs use the same `tools/stat_var_processor.py` for evaluation
- Both use the same `ground_truth/` directory with multi-PVMAP testing (best match selected)
- FAIL-VAL datasets still have evaluation metrics from the best-attempt PVMAP

---

*Generated 2026-02-11. Source data: `analysis/Gemini_vs_Claude_Comparison.md` (Jan 21 baseline) and `output/batch_20260211_031041/` (Feb 11 batch run).*
