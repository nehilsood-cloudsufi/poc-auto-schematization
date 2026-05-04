# PV Accuracy Factor Analysis — Summary

Hey,

I spent some time digging into what actually drives PV accuracy across our benchmark datasets. I wanted to understand why some datasets do well and others completely fail, so I pulled the 49 datasets from our evaluation benchmark and ran a proper statistical analysis.

## What I did

I extracted 7 structural features from each dataset's input CSV — column count, row count, numeric vs categorical column breakdown, cardinality stats — and computed Spearman rank correlations against PV accuracy. I also manually tagged each dataset with a domain category (Census, Health, Education, etc.) to see if subject matter matters.

I also ran a ground truth validation pass — ran the existing human-authored PVMAPs through the stat_var_processor to check how many datasets actually produce valid output. Only 28 out of 49 datasets have confirmed working ground truth. The rest fail due to PVMAP keys not matching input CSV headers or DC API timeouts on the Africa/Kenya datasets. So we're benchmarking against ground truth that is itself partially broken, which means our accuracy numbers are probably underselling the pipeline on some of those datasets.

The full report with charts is attached (`pvmap_benchmark_study.docx`), but here's the short version.

## What I found

**None of the structural features matter much.** I tested column count, row count, numeric-to-categorical ratio, and cardinality. The strongest correlation was r=0.20 for numeric-to-categorical ratio, and even that isn't statistically significant (p=0.16). Column count in particular is basically a red herring — `usa_dol_minimum_wage` has 56 columns and hits 89% PV accuracy because all the columns follow the same pattern.

**Domain is what actually predicts accuracy.** Census/demographics datasets average 39.3% PV accuracy. Crime/Safety averages 2.6%. Brazil/LatAm datasets are near zero. That gap is way bigger than anything structural can explain.

**Row count doesn't matter at all** (r=-0.05). This makes sense — the pipeline samples rows before sending to the LLM, so whether a dataset has 4 rows or 3,000 makes no difference.

**The real bottleneck is schema vocabulary coverage.** I grouped domains into tiers based on how well Data Commons covers them. Domains with strong DC schema (demographics, employment, environment) consistently outperform domains with thin coverage (crime codes, Brazilian municipal programs, Korean education stats). The LLM can only map columns to DC properties that actually exist in the vocabulary.

## The five hypotheses I tested

| # | Hypothesis | Result | Key stat |
|---|-----------|--------|----------|
| H1 | More columns = lower accuracy | Rejected | r=-0.10, p=0.50 |
| H2 | More numeric columns = higher accuracy | Partially supported | r=0.20, p=0.16 |
| H3 | Domain is the strongest predictor | Supported | 39.3% vs 2.6% avg |
| H4 | More rows = lower accuracy | Rejected | r=-0.05, p=0.73 |
| H5 | Schema vocabulary coverage drives success | Supported | Strong tier >> Weak tier |

## What this means for us

The pipeline's accuracy ceiling isn't about handling wide tables or large datasets better — it's about schema coverage. Datasets that map cleanly to existing DC properties work. Datasets from domains where DC has thin coverage fail, and no amount of prompt engineering will fix that.

Worth noting — the ground truth validation shows that even human-written PVMAPs only pass at 20%, so we're measuring against a pretty noisy benchmark. A chunk of the "ground truth" files have key mismatches with their input CSVs and produce zero data rows. That means our automated accuracy numbers are probably underselling the pipeline on some datasets where the ground truth itself is broken.

If we want to move the needle on the bottom half of the benchmark, we'd need to either expand the schema vocabulary for underperforming domains or build domain-specific mapping strategies. Cleaning up the ground truth files themselves would also help us get more accurate measurements.

Happy to walk through the full report if useful.

Nehil

---

Google Chat version (plain text):


Hey - here is the summary of my analysis

First thing I pulled structural features from every dataset — column count, row count, how many columns are numeric vs categorical, cardinality. Ran Spearman correlations against PV accuracy for each one. My initial hunch was that wider or messier tables would do worse.

That turned out to be wrong. Column count, row count, cardinality — none of them correlated with accuracy in any meaningful way. The strongest signal was numeric-to-categorical ratio, and even that wasn't statistically significant (I have graphs to show my results). A dataset with 56 columns (usa_dol_minimum_wage) scored 89%, while one with just 4 columns (crdc_harassment) scored 0%.

So I started looking at domain instead. Tagged each dataset by subject area — Census, Health, Education, Crime, etc. That's where the real pattern showed up. Census/demographics datasets average 39% accuracy. Crime/Safety averages 3%. Brazil/LatAm datasets are basically zero. The gap between domains is way bigger than any structural factor.

Then I dug into why. Grouped the domains by how well Data Commons covers them. Domains with strong DC schema (demographics, employment, environment) consistently outperform those with thin coverage (crime codes, Brazilian municipal programs, Korean education stats). The LLM does fine when the target properties exist in the vocabulary. When they don't, it fails — doesn't matter how clean the table is.

Where this leaves us: The accuracy ceiling isn't about table handling — it's about schema coverage. To move the needle, we'd need to expand DC vocabulary for underperforming domains or build domain-specific strategies. 

when you get some time, let me know, we can discuss further upon this


Also validated the ground truth itself. Ran all the human-authored PVMAPs through stat_var_processor. Only 28 out of 49 datasets have working ground truth — the rest have key mismatches or API failures. So our benchmark is partially measuring against broken references, which means we're probably underselling the pipeline on some datasets.Cleaning up the ground truth would also give us more reliable numbers to work with.