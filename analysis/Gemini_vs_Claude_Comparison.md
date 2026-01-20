# Gemini vs Claude Auto-Schematization Comparison

**Generated**: 2026-01-20 12:36:28

This report compares the auto-generated PVMAP outputs from **Gemini** and **Claude** models for datasets where both have evaluation results with proper metrics.

---

## Executive Summary

### Dataset Coverage

| Metric | Gemini | Claude | Common |
|--------|--------|--------|--------|
| Total Datasets with Metrics | 25 | 82 | - |
| Datasets Compared | - | - | **25** |

### Winner Analysis (Based on PV Accuracy)

| Winner | Count | Percentage |
|--------|-------|------------|
| **Gemini** | 11 | 44.0% |
| **Claude** | 8 | 32.0% |
| **Tie** | 6 | 24.0% |

*Winner determined by PV Accuracy. Higher accuracy = better.*

### Average Performance Metrics

| Metric | Gemini Avg | Claude Avg | Difference |
|--------|------------|------------|------------|
| **Node Accuracy %** | 5.1 | 6.4 | -1.3 |
| **Node Coverage %** | 27.5 | 70.1 | -42.6 |
| **PV Accuracy %** | 15.2 | 10.1 | +5.1 |
| **Precision %** | 26.5 | 17.1 | +9.4 |

---

## Detailed Comparison Table

| Dataset | Gemini Node % | Claude Node % | Gemini PV % | Claude PV % | Gemini Prec % | Claude Prec % | Winner |
|---------|--------------|---------------|-------------|-------------|---------------|---------------|--------|
| bis_bis_central_bank_policy_rate | 14.3 | 100.0 | 36.4 | 73.1 | 35.7 | 61.3 | 🟢 Claude |
| brazil_sidra_ibge | 3.2 | 0.0 | 1.5 | 0.0 | 20.0 | 0.0 | 🔵 Gemini |
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | ⚪ Tie |
| ccd_enrollment | 2.6 | 15.8 | 44.2 | 20.4 | 45.3 | 47.2 | 🔵 Gemini |
| cdc_social_vulnerability_index | 2.4 | 2.4 | 11.7 | 15.5 | 28.4 | 24.5 | 🟢 Claude |
| census_v2_sahie | 27.8 | 33.3 | 36.0 | 39.4 | 55.2 | 60.9 | 🟢 Claude |
| census_v2_saipe | 14.3 | 0 | 53.3 | 0 | 47.4 | 0 | 🔵 Gemini |
| child_birth | 40.0 | 0.0 | 72.7 | 18.2 | 76.2 | 14.8 | 🔵 Gemini |
| crdc_instructional_wifi_devices | 10.0 | 0.0 | 28.6 | 23.1 | 15.6 | 8.8 | 🔵 Gemini |
| google_sustainability_financial_incentives | 0.4 | 0.0 | 0.7 | 0.4 | 13.3 | 3.1 | 🔵 Gemini |
| india_rbistatedomesticproduct | 0.0 | 0.0 | 0.0 | 3.5 | 0.0 | 33.3 | 🟢 Claude |
| ireland_census | 0.0 | 0.0 | 0.0 | 15.4 | 0.0 | 18.2 | 🟢 Claude |
| opendataforafrica_ethiopia_statistics | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | ⚪ Tie |
| opendataforafrica_kenya_census | 0.0 | 0 | 1.2 | 0 | 12.5 | 0 | 🔵 Gemini |
| opendataforafrica_rwanda_census | 4.9 | 0 | 3.5 | 0 | 55.6 | 0 | 🔵 Gemini |
| school_finance | 0.0 | 0.0 | 23.5 | 11.8 | 59.1 | 18.2 | 🔵 Gemini |
| school_retention | 0.0 | 0.0 | 0.0 | 0.0 | 20.0 | 0.0 | ⚪ Tie |
| southkorea_statistics_employment | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | ⚪ Tie |
| southkorea_statistics_health | 1.1 | 0.0 | 0.9 | 3.7 | 12.5 | 0.5 | 🟢 Claude |
| statistics_new_zealand_new_zealand_census | 1.7 | 4.2 | 63.0 | 24.3 | 52.2 | 33.9 | 🔵 Gemini |
| us_bls_bls_ces | 0.2 | 0.4 | 0.2 | 0.4 | 6.4 | 6.6 | 🟢 Claude |
| us_bls_bls_ces_state | 0.5 | 0.3 | 0.2 | 0.1 | 67.9 | 56.0 | ⚪ Tie |
| us_bls_cpi_category | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | ⚪ Tie |
| us_bls_us_cpi | 0.0 | 0.0 | 0.0 | 2.2 | 0.0 | 2.1 | 🟢 Claude |
| us_crash_fars_crashdata | 5.1 | 3.7 | 1.2 | 0.7 | 39.5 | 39.1 | 🔵 Gemini |

---

## Performance Analysis

### Datasets Where Gemini Outperforms Claude (by PV Accuracy)

| Dataset | Gemini PV % | Claude PV % | Difference |
|---------|-------------|-------------|-----------|
| child_birth | 72.7 | 18.2 | **+54.5** |
| census_v2_saipe | 53.3 | 0 | **+53.3** |
| statistics_new_zealand_new_zealand_census | 63.0 | 24.3 | **+38.7** |
| ccd_enrollment | 44.2 | 20.4 | **+23.8** |
| school_finance | 23.5 | 11.8 | **+11.7** |
| crdc_instructional_wifi_devices | 28.6 | 23.1 | **+5.5** |
| opendataforafrica_rwanda_census | 3.5 | 0 | **+3.5** |
| brazil_sidra_ibge | 1.5 | 0.0 | **+1.5** |
| opendataforafrica_kenya_census | 1.2 | 0 | **+1.2** |
| us_crash_fars_crashdata | 1.2 | 0.7 | **+0.5** |

### Datasets Where Claude Outperforms Gemini (by PV Accuracy)

| Dataset | Gemini PV % | Claude PV % | Difference |
|---------|-------------|-------------|-----------|
| bis_bis_central_bank_policy_rate | 36.4 | 73.1 | **-36.7** |
| ireland_census | 0.0 | 15.4 | **-15.4** |
| cdc_social_vulnerability_index | 11.7 | 15.5 | **-3.8** |
| india_rbistatedomesticproduct | 0.0 | 3.5 | **-3.5** |
| census_v2_sahie | 36.0 | 39.4 | **-3.4** |
| southkorea_statistics_health | 0.9 | 3.7 | **-2.8** |
| us_bls_us_cpi | 0.0 | 2.2 | **-2.2** |
| us_bls_bls_ces | 0.2 | 0.4 | **-0.2** |

### Datasets With Similar Performance (Ties)

| Dataset | Gemini PV % | Claude PV % |
|---------|-------------|-------------|
| brazil_visdata_brazil_rural_development_program | 0.0 | 0.0 |
| opendataforafrica_ethiopia_statistics | 0.0 | 0.0 |
| school_retention | 0.0 | 0.0 |
| southkorea_statistics_employment | 0.0 | 0.0 |
| us_bls_bls_ces_state | 0.2 | 0.1 |
| us_bls_cpi_category | 0.0 | 0.0 |

---

## Best Performing Datasets (by PV Accuracy)

### Top 10 Gemini Results

| Dataset | PV Accuracy % | Node Accuracy % | Precision % |
|---------|---------------|-----------------|-------------|
| child_birth | 72.7 | 40.0 | 76.2 |
| statistics_new_zealand_new_zealand_census | 63.0 | 1.7 | 52.2 |
| census_v2_saipe | 53.3 | 14.3 | 47.4 |
| ccd_enrollment | 44.2 | 2.6 | 45.3 |
| bis_bis_central_bank_policy_rate | 36.4 | 14.3 | 35.7 |
| census_v2_sahie | 36.0 | 27.8 | 55.2 |
| crdc_instructional_wifi_devices | 28.6 | 10.0 | 15.6 |
| school_finance | 23.5 | 0.0 | 59.1 |
| cdc_social_vulnerability_index | 11.7 | 2.4 | 28.4 |
| opendataforafrica_rwanda_census | 3.5 | 4.9 | 55.6 |

### Top 10 Claude Results

| Dataset | PV Accuracy % | Node Accuracy % | Precision % |
|---------|---------------|-----------------|-------------|
| bis_bis_central_bank_policy_rate | 73.1 | 100.0 | 61.3 |
| census_v2_sahie | 39.4 | 33.3 | 60.9 |
| statistics_new_zealand_new_zealand_census | 24.3 | 4.2 | 33.9 |
| crdc_instructional_wifi_devices | 23.1 | 0.0 | 8.8 |
| ccd_enrollment | 20.4 | 15.8 | 47.2 |
| child_birth | 18.2 | 0.0 | 14.8 |
| cdc_social_vulnerability_index | 15.5 | 2.4 | 24.5 |
| ireland_census | 15.4 | 0.0 | 18.2 |
| school_finance | 11.8 | 0.0 | 18.2 |
| southkorea_statistics_health | 3.7 | 0.0 | 0.5 |

---

## Key Insights

### Model Comparison Summary

1. **Overall Performance**: Gemini has higher average PV Accuracy (15.2% vs 10.1%)

2. **Win Rate**: Gemini wins on 11/25 datasets (44.0%), Claude wins on 8/25 (32.0%)

3. **Node Coverage**: Claude has better node coverage (70.1% vs 27.5%)

4. **Precision**: Gemini has higher precision (26.5% vs 17.1%)

### Recommendations

- For datasets requiring **high accuracy**: Choose the model that performs best on similar dataset types
- Both models struggle with large, complex schemas (BLS, CPI datasets)
- Both models perform better on simpler financial/census datasets

---

*Report generated on 2026-01-20 12:36:28*
*Comparison based on 25 datasets with evaluation metrics in both Gemini and Claude outputs*
