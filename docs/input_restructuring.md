# Input Folder Restructuring

## Summary

The input folder structure was reorganized to separate concerns and support a more flexible pipeline. Metadata and schema files were moved into dedicated subdirectories, and new CLI arguments were added to support standalone file mode and optional metadata usage.

**When:** February 2026 (feature/nehil/pvmap-validation-enhanced branch)

## Migration Details

### 1. Metadata Files: Root → `input_metadata/`

Metadata CSV files were moved from the dataset root into a dedicated `input_metadata/` subdirectory.

| Before | After |
|--------|-------|
| `input/{dataset}/*_metadata.csv` | `input/{dataset}/input_metadata/*_metadata.csv` |

- **50 datasets** migrated
- Metadata is now **optional** — controlled by `--use-metadata` flag (default: off)

### 2. Schema Files: Root → `schema/`

Schema example files (.txt and .mcf) were moved from the dataset root into a `schema/` subdirectory.

| Before | After |
|--------|-------|
| `input/{dataset}/scripts_*_schema_examples_*.txt` | `input/{dataset}/schema/scripts_*_schema_examples_*.txt` |
| `input/{dataset}/scripts_*_vertical_*.mcf` | `input/{dataset}/schema/scripts_*_vertical_*.mcf` |

- The `schema/` directory is auto-populated by the SchemaSelectionAgent
- Manual schema files can still be placed in `schema/` before pipeline runs

### 3. Ground Truth: Flat → Structured

Ground truth directories were restructured to separate PVMAP files from metadata.

| Before | After |
|--------|-------|
| `ground_truth/{dataset}/pvmap.csv` | `ground_truth/{dataset}/pvmap/*_pvmap.csv` |
| `ground_truth/{dataset}/*_metadata.csv` | `ground_truth/{dataset}/metadata/*.csv` |

## New Folder Structure

### Before

```
input/{dataset_name}/
├── *_metadata.csv
├── scripts_*_schema_examples_*.txt
├── scripts_*_vertical_*.mcf
└── test_data/
    ├── *_input.csv
    └── *_sampled_data.csv

ground_truth/{dataset_name}/
├── pvmap.csv
└── *_metadata.csv
```

### After

```
input/{dataset_name}/
├── input_metadata/                    # Optional (use with --use-metadata)
│   └── *_metadata.csv
├── schema/                            # Auto-populated by SchemaSelectionAgent
│   ├── scripts_*_schema_examples_*.txt
│   └── scripts_*_vertical_*.mcf
└── test_data/                         # REQUIRED
    ├── *_input.csv                    # Original full dataset
    └── *_sampled_data.csv             # Auto-generated

ground_truth/{dataset_name}/
├── pvmap/
│   └── *_pvmap.csv
└── metadata/
    └── *.csv
```

## New CLI Arguments

| Flag | Description |
|------|-------------|
| `--input-file` | Path to standalone input file (no dataset folder required) |
| `--use-metadata` | Use metadata files for prompt building (default: off) |
| `--metadata-file-path` | Path to explicit metadata file (auto-enables `--use-metadata`) |
| `--schema-file` | Path to explicit schema file override |

## Code Changes Summary

| File | Key Changes |
|------|-------------|
| `src/state/dataset_info.py` | Added `input_metadata_path`, `schema_path` computed properties; `standalone`, `use_metadata`, `input_file_path` fields |
| `src/agents/discovery_agent.py` | Updated discovery to scan `input_metadata/`, `schema/`, `test_data/` subdirectories; added `use_metadata` and `standalone` mode support |
| `src/agents/pvmap_generation_agent.py` | Updated to read metadata from `input_metadata/` and schema from `schema/` |
| `src/agents/validation_agent.py` | Updated `--config_file` path to `input_metadata/` |
| `src/pipeline/schema_selection/schema_selector.py` | Updated to copy schema files to `schema/` subdirectory |
| `src/pipeline/evaluation/evaluate_pvmap_diff.py` | Updated to find ground truth in `pvmap/` subdirectory |
| `src/tools/evaluation_tools.py` | Updated ground truth discovery paths |
| `src/tools/validation_tool.py` | Updated metadata path resolution |
| `src/run_pipeline.py` | Added `--input-file`, `--use-metadata`, `--metadata-file-path`, `--schema-file` CLI args; updated discovery and preparation logic |
| `tests/conftest.py` | Updated test fixtures for new folder structure |
| `tests/agents/test_discovery_agent.py` | Updated test assertions for new paths |
| `tests/test_schema_selector.py` | Updated schema output paths |
| `tests/tools/test_schema_tools.py` | Updated expected schema file locations |

## Standalone File Mode

The `--input-file` flag enables running the pipeline on a single CSV file without any folder structure:

```bash
python src/run_pipeline.py --input-file=path/to/data.csv
```

This:
- Derives a dataset name from the filename
- Creates a virtual `DatasetInfo` with `standalone=True`
- Skips metadata discovery (unless `--metadata-file-path` is provided)
- Runs schema selection automatically
- Outputs to `output/{derived_dataset_name}/`

**With metadata:**
```bash
python src/run_pipeline.py --input-file=path/to/data.csv \
  --metadata-file-path=path/to/metadata.csv
```

## Backward Compatibility Notes

- **Metadata is now optional by default.** Previous pipeline runs that relied on metadata being auto-discovered must now pass `--use-metadata`.
- **Schema files must be in `schema/` subdirectory.** Any datasets with schema files in the root directory will not have them discovered — they need to be moved to `schema/` or regenerated via SchemaSelectionAgent.
- **Ground truth paths changed.** Code that looked for `ground_truth/{dataset}/pvmap.csv` must now look in `ground_truth/{dataset}/pvmap/`.
- **Test fixtures updated.** All test mock data now uses the new folder structure.
