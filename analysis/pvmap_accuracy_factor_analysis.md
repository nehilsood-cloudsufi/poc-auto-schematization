# What Affects PV Accuracy?

A statistical analysis of 48 datasets evaluated with Gemini 3 Pro.

## TL;DR

- Domain matters more than structure. Census/demographics datasets average 39.3% PV Accuracy. Brazil/LatAm and Crime/Safety datasets average under 3%.
- No single structural feature (column count, row count, data types) strongly predicts PV Accuracy. The strongest correlation is r=0.20 for numeric-to-categorical ratio — barely a signal.
- Simple, narrow tables with few columns (like the Zurich wiki datasets at 3-5 columns) consistently do well. But wide tables don't always fail — `usa_dol_minimum_wage` has 56 columns and hits 89% PV Accuracy.
- The pipeline's best results come from datasets that map cleanly to Data Commons schema: simple time series, single-dimension demographic breakdowns, and narrow economic indicators.

## The Data

We evaluated 48 datasets from the Gemini vs Claude comparison benchmark using Gemini 3 Pro results. These 48 are the ones where at least one model produced non-zero results — 20 additional datasets in the original benchmark scored 0% across all models and were excluded.

All 48 datasets have input CSVs available, so structural features (column count, row count, numeric/categorical breakdown, cardinality) are complete for every dataset. PV Accuracy is the primary metric. Domain was manually assigned to each dataset.

## What Affects PV Accuracy

Spearman rank correlations between each structural factor and Gemini 3 Pro PV Accuracy:

| Factor | Spearman r | p-value | N |
|--------|-----------|---------|---|
| Numeric-to-categorical ratio | 0.202 | 0.161 | 48 |
| Categorical column count | -0.168 | 0.249 | 48 |
| Numeric column count | 0.117 | 0.424 | 48 |
| Column count | -0.099 | 0.499 | 48 |
| Mean column cardinality | 0.058 | 0.695 | 48 |
| Row count | -0.051 | 0.729 | 48 |
| Max column cardinality | 0.042 | 0.777 | 48 |

None of these are statistically significant (all p > 0.16). Structural features alone don't explain PV Accuracy in this dataset. The real story is in the domain and dataset groupings below.

## Breaking It Down

### Numeric-to-Categorical Ratio

The strongest structural signal, but still weak. Datasets with more numeric columns relative to categorical ones tend to score slightly higher.

| Bucket | Count | Avg PV Accuracy | Median PV Accuracy |
|--------|-------|-----------------|-------------------|
| Low (mostly categorical) | 16 | 16.5% | 4.8% |
| Mid | 17 | 19.7% | 8.1% |
| High (mostly numeric) | 15 | 25.5% | 14.6% |

This probably happens because heavily categorical datasets have more dimension columns that the LLM needs to decompose into DC properties. Each categorical column is a potential mapping decision. More numeric columns means more straightforward value mappings.

### Column Count

Column count barely correlates (r=-0.099). Wide tables don't systematically fail.

| Bucket | Count | Avg PV Accuracy | Median PV Accuracy |
|--------|-------|-----------------|-------------------|
| Low (<7 cols) | 18 | 21.4% | 11.9% |
| Mid (7-15 cols) | 15 | 18.7% | 6.6% |
| High (>15 cols) | 15 | 21.0% | 14.6% |

The "high" bucket includes both top performers (`usa_dol_minimum_wage` at 89%, `world_bank_commodity_market` at 32.7%) and failures (`southkorea_statistics_education` at 0%, `us_crash_fars_crashdata` at 1.2%). Column count alone doesn't predict success — what matters is whether the columns map to known DC schema patterns.

### Domain

Domain is the strongest predictor of PV Accuracy. Not a single structural feature — the subject matter.

| Domain | Datasets | Avg PV Accuracy | Median PV Accuracy |
|--------|----------|-----------------|-------------------|
| Other/Misc | 2 | 81.6% | 81.6% |
| Census/Demographics | 12 | 39.3% | 37.5% |
| Employment/Labor | 4 | 22.4% | 0.3% |
| Environment | 2 | 22.0% | 22.0% |
| Economics/Finance | 8 | 10.5% | 3.8% |
| Health | 6 | 10.5% | 10.5% |
| Education | 7 | 7.1% | 7.1% |
| India | 1 | 6.1% | 6.1% |
| Crime/Safety | 3 | 2.6% | 1.2% |
| Brazil/LatAm | 3 | 0.8% | 0.0% |

Census/demographics datasets average 39.3% — three times the overall average. Crime/Safety and Brazil/LatAm datasets are near zero. This gap is bigger than any structural factor can explain.

Employment/Labor has a misleading mean (22.4%) because `usa_dol_minimum_wage` at 89% pulls it up. The median (0.3%) tells the real story — most labor datasets do poorly.

## Dataset Groups

### Group 1: Zurich Wiki Datasets (the winners)

Simple demographic tables from Zurich with 3-5 columns, 24 rows, clean structure.

| Dataset | Columns | PV Accuracy |
|---------|---------|-------------|
| zurich_bev_4031_sex_wiki | 4 | 62.5% |
| zurich_bev_3240_wiki | 3 | 50.0% |
| zurich_bev_4031_wiki | 3 | 50.0% |
| zurich_bev_3903_sex_wiki | 4 | 37.5% |
| zurich_bev_4031_hel_wiki | 4 | 37.5% |
| zurich_bev_3903_hel_wiki | 4 | 30.0% |
| zurich_bev_3903_age10_wiki | 5 | 17.6% |
| zurich_wir_2552_wiki | 9 | 75.0% |

**Avg PV Accuracy: 45.0%**

These work because they're narrow, uniform, and map directly to DC demographic properties (sex, age, nationality). The LLM doesn't have to guess — the columns are obvious.

### Group 2: Clean Economic/Census Indicators

Mid-size tables (6-26 columns) with clear economic or demographic structure.

| Dataset | Columns | PV Accuracy |
|---------|---------|-------------|
| undata | 11 | 88.3% |
| usa_dol_minimum_wage | 56 | 89.0% |
| opendataforafrica_ethiopia_statistics | 6 | 64.4% |
| census_v2_saipe | 8 | 53.3% |
| bis_bis_central_bank_policy_rate | 18 | 36.4% |
| census_v2_sahie | 26 | 34.1% |
| world_bank_commodity_market | 73 | 32.7% |
| opendataforafrica_kenya_census | 16 | 30.0% |

**Avg PV Accuracy: 53.5%**

These succeed despite varying column counts because the data maps to well-established DC schema: economic indicators, census counts, financial rates. The pipeline knows what to do with them. `usa_dol_minimum_wage` has 56 columns but they're all wage values across states — a single pattern repeated.

### Group 3: Health / Survey Datasets

Health and survey data with moderate complexity.

| Dataset | Columns | PV Accuracy |
|---------|---------|-------------|
| inpe_fire | 15 | 40.5% |
| india_nfhs | 112 | 21.6% |
| brfss_nchs_asthma_prevalence | 11 | 19.1% |
| cdc_social_vulnerability_index | 159 | 14.6% |
| doctoratedegreeemployment | 7 | 18.3% |
| us_cdc_single_race | 14 | 6.4% |

**Avg PV Accuracy: 20.1%**

Mixed results. `inpe_fire` does well (clear event data). `india_nfhs` and `cdc_social_vulnerability_index` are wide but partially succeed. These datasets have non-trivial schema mapping — health indicators, vulnerability indices, survey response categories — that partially overlap with DC schema but require more decomposition.

### Group 4: Complex / Domain-Specific Tables (the losers)

Large or domain-specific datasets where DC schema coverage is thin.

| Dataset | Columns | PV Accuracy |
|---------|---------|-------------|
| us_crash_fars_crashdata | 80 | 1.2% |
| crdc_import_crdc_harassment_or_bullying | 4 | 0.0% |
| brazil_visdata_FoodBasketDistribution | 6 | 0.0% |
| brazil_visdata_brazil_rural_development_program | 18 | 0.0% |
| brazil_sidra_ibge | 7 | 2.3% |
| southkorea_statistics_education | 179 | 0.0% |
| southkorea_statistics_employment | 12 | 0.0% |

**Avg PV Accuracy: 0.5%**

These fail for different reasons. `southkorea_statistics_education` has 179 columns — the prompt becomes unwieldy. `crdc_import_crdc_harassment_or_bullying` has only 4 columns but the concepts (harassment types, bullying categories) don't map to standard DC properties. Brazil datasets use Portuguese column names and non-standard structures. `us_crash_fars_crashdata` has 80 highly domain-specific columns (crash codes, vehicle types, injury scales) with no DC precedent.

## What We Think Is Happening

**Domain fit matters most.** Datasets that align with Data Commons' existing schema (demographics, economics, census counts) succeed. Datasets from domains with thin DC coverage (crime codes, Brazilian municipal programs, Korean education metrics) fail regardless of structure.

**Column count is a red herring.** Wide tables can succeed if the columns follow a repeating pattern (`usa_dol_minimum_wage`: 56 columns of state-level wages). Narrow tables can fail if the concepts don't map (`crdc_harassment`: 4 columns, 0% accuracy).

**The real bottleneck is schema vocabulary, not structural complexity.** The LLM needs to map column values to DC properties. When those properties exist in the schema vocabulary (gender, age, country, economic indicators), it works. When they don't (crash severity codes, food basket categories), it doesn't.

**Non-English or region-specific datasets struggle.** Brazil and South Korea datasets consistently underperform. This is likely a combination of language barriers in column names and lack of DC schema coverage for those specific national statistical categories.

**The numeric-to-categorical ratio signal is probably a proxy.** More numeric columns = more straightforward value mappings. More categorical columns = more dimension decomposition decisions for the LLM to get right. But the effect is small (r=0.20) because domain fit overwhelms it.
