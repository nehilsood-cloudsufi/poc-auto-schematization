# KT 01 -- What Problem Does This Solve?

This document gives you enough context to understand *why* this pipeline exists and *what* the key concepts mean. By the end, you should be able to look at a raw CSV, a PVMAP, and the transformed output and follow the chain from start to finish.

---

## What is Data Commons?

Data Commons is an open knowledge graph maintained by Google. Its goal is simple: take statistical data published by hundreds of organizations -- census bureaus, the WHO, the World Bank, the Bank for International Settlements, and many more -- and make it all queryable through a single, standardized schema.

Think of it this way: every government agency publishes data in its own format, with its own column names, its own codes for countries, its own way of representing dates. If you wanted to compare Argentina's central bank policy rate (from the BIS) with Argentina's unemployment rate (from the ILO), you would need to manually reconcile two completely different CSV layouts. Data Commons eliminates that work by putting everything into a common format.

The key idea is a shared vocabulary. Instead of each dataset inventing its own column headers, Data Commons defines standard **properties** (`observationAbout`, `observationDate`, `value`, `measuredProperty`, `unit`, etc.) and standard **entities** (`country/ARG`, `Count_Person`, `PercentPerAnnum`). Once data is expressed in this vocabulary, you can query across all sources with a single API.

---

## What is a PVMAP?

A PVMAP (Property-Value Map) is a small CSV lookup table that tells the system how to transform a raw dataset into Data Commons format. It is the central artifact this pipeline produces.

Let's walk through a real example using the BIS central bank policy rate dataset.

### The Raw CSV

The source file lives at `input/bis_bis_central_bank_policy_rate/test_data/WS_CBPOL_csv_flat_input.csv`. Here are the columns that matter (simplified):

| FREQ:Frequency | REF_AREA:Reference area | TIME_PERIOD:Time period or range | OBS_VALUE:Observation Value | UNIT_MEASURE:Unit of measure |
|---|---|---|---|---|
| M: Monthly | AR: Argentina | 1993-04 | 0.63 | 368: Per cent per year |
| M: Monthly | AR: Argentina | 1993-05 | 0.11 | 368: Per cent per year |
| M: Monthly | US: United States | 2024-01 | 5.33 | 368: Per cent per year |

Each row is one observation: a country, a date, and a numeric value representing the policy rate.

### The PVMAP

The ground truth PVMAP lives at `ground_truth/bis_bis_central_bank_policy_rate/pvmap/bis_bis_central_bank_policy_rate_pvmap.csv`:

```csv
key,,,,,,
BIS:WS_CBPOL(1.0): Central bank policy rates,measuredProperty,interestRate,populationType,FinancialInstrument,instrumentType,CountryCentralBankPolicyRate
M: Monthly,measurementQualifier,Monthly,observationPeriod,P1M,,
D: Daily,measurementQualifier,Daily,observationPeriod,P1D,,
REF_AREA:Reference area,observationAbout,{Data},,,,
TIME_PERIOD:Time period or range,observationDate,{Data},,,,
OBS_VALUE:Observation Value,value,{Number},,,,
368: Per cent per year,unit,PercentPerAnnum,,,,
```

The format is: the first column (`key`) is a string to match against the data. The remaining columns come in property/value pairs. Here is what each row does:

- **Row 1** (`key,,,,,,`) -- header row. Just column labels; no data here.
- **Row 2** (`BIS:WS_CBPOL(1.0): Central bank policy rates`) -- this matches the value in the `STRUCTURE_ID` column. It sets the dataset-level properties: `measuredProperty` is `interestRate`, `populationType` is `FinancialInstrument`, and `instrumentType` is `CountryCentralBankPolicyRate`. Together these define *what* is being measured.
- **Row 3** (`M: Monthly`) -- when the system sees `M: Monthly` in the frequency column, it sets `measurementQualifier` to `Monthly` and `observationPeriod` to `P1M` (ISO 8601 for "one month").
- **Row 4** (`D: Daily`) -- same idea for daily data: qualifier `Daily`, period `P1D`.
- **Row 5** (`REF_AREA:Reference area`) -- this matches the *column header* itself. The value `{Data}` is a special placeholder meaning "pass the cell value through as-is." So when a row has `AR: Argentina`, the system maps it to `observationAbout` = `AR: Argentina` (which the processor then resolves to `dcid:country/ARG`).
- **Row 6** (`TIME_PERIOD:Time period or range`) -- same pattern for dates. `{Data}` passes `1993-04` through to `observationDate`.
- **Row 7** (`OBS_VALUE:Observation Value`) -- matches the value column header. `{Number}` means "interpret the cell as a numeric value."
- **Row 8** (`368: Per cent per year`) -- maps the unit code to the Data Commons vocabulary term `PercentPerAnnum`.

### The Transformed Output

After `stat_var_processor.py` applies the PVMAP to the full dataset, you get clean Data Commons observations:

```csv
observationAbout,observationDate,variableMeasured,value
dcid:country/ARG,1993-04,dcid:InterestRate_FinancialInstrument_CountryCentralBankPolicyRate_Monthly,0.63
dcid:country/ARG,1993-05,dcid:InterestRate_FinancialInstrument_CountryCentralBankPolicyRate_Monthly,0.11
dcid:country/USA,2024-01,dcid:InterestRate_FinancialInstrument_CountryCentralBankPolicyRate_Monthly,5.33
```

Notice what happened:
- `AR: Argentina` became `dcid:country/ARG` (a standardized place identifier).
- All the properties from the PVMAP were composed into a single `variableMeasured` DCID.
- The raw numeric value passed through unchanged.

This output is ready to be loaded into the Data Commons knowledge graph.

---

## What is a StatVar / StatVarObservation?

These are the two core concepts in the Data Commons data model.

**StatisticalVariable (StatVar)** -- a unique, measurable concept. It answers the question "what are you measuring?" A StatVar is defined by its properties (population type, measured property, constraints). Examples:

1. `Count_Person` -- the total population count for a place.
2. `UnemploymentRate_Person` -- the unemployment rate among people.
3. `InterestRate_FinancialInstrument_CountryCentralBankPolicyRate` -- the central bank policy interest rate, which is exactly what the BIS dataset tracks.

Each StatVar has a DCID (Data Commons Identifier) that encodes its properties. You can read the DCID like a sentence: "Interest rate of a financial instrument, specifically a country central bank policy rate."

**StatVarObservation** -- a single data point that ties a StatVar to a place, a date, and a value. Every row in the transformed output above is one StatVarObservation:

| Component | Example |
|---|---|
| StatVar | `InterestRate_FinancialInstrument_CountryCentralBankPolicyRate_Monthly` |
| Place | `country/ARG` (Argentina) |
| Date | `1993-04` |
| Value | `0.63` |

If the StatVar is the *question* ("what is the monthly central bank policy rate?"), the StatVarObservation is one *answer* ("for Argentina, in April 1993, it was 0.63%").

---

## What is MCF / TMCF?

When data goes into the knowledge graph, it needs a formal definition for each StatVar. That is where MCF and TMCF come in.

**MCF (Meta Content Framework)** -- a plain text format for defining nodes in the knowledge graph. Each block describes one entity. Here is what the BIS StatVar looks like in MCF:

```
Node: dcid:InterestRate_FinancialInstrument_CountryCentralBankPolicyRate_Monthly
typeOf: dcs:StatisticalVariable
measuredProperty: dcs:interestRate
populationType: dcs:FinancialInstrument
instrumentType: dcs:CountryCentralBankPolicyRate
measurementQualifier: dcs:Monthly
```

Each line is a property/value pair. The `Node:` line gives the DCID. The remaining lines define what the variable measures.

**TMCF (Template MCF)** -- the same format, but with column references instead of literal values. TMCF is used to batch-process entire CSV files. Instead of writing one MCF block per row, you write one template that references CSV columns like `C:dataset->observationDate`.

For a deeper dive into how `stat_var_processor.py` uses these formats, see [docs/stat_var_processor_guide.md](../stat_var_processor_guide.md).

---

## Why Automate?

Creating a PVMAP by hand is slow and error-prone. You need to:

1. Understand the source dataset's column layout and encoding.
2. Know the Data Commons schema vocabulary (hundreds of valid properties and types).
3. Map every column, every coded value, and every unit to the right DC term.
4. Validate by running the full dataset through `stat_var_processor.py` and checking for errors.

For a single dataset, this can take hours of work from a domain expert.

This pipeline automates the entire process:

- **81 ground truth datasets** available for evaluation across 6 domains (demographics, economy, education, employment, energy, health).
- **~45 seconds** average processing time per dataset -- from raw CSV to validated PVMAP.
- **100% validation success rate** on test datasets (every generated PVMAP passes `stat_var_processor` without errors).
- **+18.7% PV accuracy improvement** vs the Gemini baseline (26.8% vs 8.1% property-value accuracy).

The pipeline uses LLM-powered generation with a retry loop: generate a PVMAP, validate it against the full dataset, feed errors back to the LLM, and try again (up to 3 attempts). This self-correction loop is what drives the high success rate.

---

## Glossary

| Term | Definition |
|---|---|
| **PVMAP** | Property-Value Map. A CSV lookup table that defines how to transform source data columns and values into Data Commons format. This is the primary output of the pipeline. |
| **StatVar** | Statistical Variable. A unique measurable concept in Data Commons, defined by its properties (e.g., `Count_Person`, `UnemploymentRate_Person`). |
| **StatVarObservation** | A single data point: one StatVar measured at one place on one date with one value. Every row of transformed output is a StatVarObservation. |
| **MCF** | Meta Content Framework. A plain text format for defining knowledge graph nodes. Each block describes one entity (like a StatVar) with property/value pairs. |
| **TMCF** | Template MCF. Like MCF, but with column references instead of literal values. Used to batch-process CSV files into the knowledge graph. |
| **DCID** | Data Commons Identifier. A unique ID for any entity in the graph. Examples: `country/USA` (a place), `Count_Person` (a StatVar), `PercentPerAnnum` (a unit). |
| **Schema.org** | A web vocabulary standard for structured data. Data Commons extends the Schema.org type hierarchy with statistical data types and properties. |
| **MCP** | Model Context Protocol. A standard that lets an LLM call external tools and services at runtime. Used optionally in this pipeline for StatVar discovery. |
| **ADK** | Google Agent Development Kit. The framework used to build the multi-agent LLM pipeline. Each phase (sampling, schema selection, generation, validation) runs as a separate agent. |
| **skeleton_summary** | A Markdown document generated during the sampling phase that describes the dataset's structure -- column types, value distributions, functional dependencies. It is injected into the PVMAP generation prompt so the LLM understands the data. |
