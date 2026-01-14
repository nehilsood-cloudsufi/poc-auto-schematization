#!/usr/bin/env bash

# Script to map datasets to schema categories and copy .mcf and .txt files
# Based on content analysis of each dataset

SCHEMA_DIR="/Users/nehilsood/work/poc-auto-schematization/Schema Example Files"
INPUT_DIR="/Users/nehilsood/work/poc-auto-schematization/input"

# Function to get category for a dataset
get_category() {
    local dataset="$1"
    case "$dataset" in
        # Demographics datasets
        bev_3240_wiki|bev_3903_age10_wiki|bev_3903_hel_wiki|bev_3903_sex_wiki|\
        bev_4031_hel_wiki|bev_4031_sex_wiki|bev_4031_wiki|\
        finland_census|us_census_pep_asrh|kenya_census|\
        ncses_demographics_seh_import|social_vulnerability_index|\
        fars_crashdata|fbigovcrime)
            echo "Demographics"
            ;;
        # Economy datasets
        bis_central_bank_policy_rate|commerce_eda|commodity_market|\
        sahie|ndap|wir_2552_wiki|undata)
            echo "Economy"
            ;;
        # Health datasets
        india_nfhs|india_nss_health_ailments|ny_diabetes|\
        who_covid19|texas|single_race)
            echo "Health"
            ;;
        # Employment datasets
        bls_ces|bls_ces_state|doctoratedegreeemployment|teachers)
            echo "Employment"
            ;;
        # Education datasets
        education|school_algebra1|enrollment|maths_and_science_enrollment|\
        new_york_education|covid_directional_indicators)
            echo "Education"
            ;;
        # Energy/Environment datasets
        wastewater_treatment|inpe_fire)
            echo "Energy"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Counters
total_datasets=0
mapped_datasets=0
unmapped_datasets=0
txt_copied=0
mcf_copied=0

# Category counters
demographics_count=0
economy_count=0
health_count=0
employment_count=0
education_count=0
energy_count=0

echo "=== Mapping Schema Files to Datasets ==="
echo ""

# Process each dataset folder
for dataset_dir in "$INPUT_DIR"/*/; do
    dataset_name=$(basename "$dataset_dir")
    total_datasets=$((total_datasets + 1))

    # Get category for this dataset
    category=$(get_category "$dataset_name")

    if [[ -z "$category" ]]; then
        echo "WARNING: No mapping for dataset: $dataset_name"
        unmapped_datasets=$((unmapped_datasets + 1))
        continue
    fi

    echo "Processing: $dataset_name -> $category"
    mapped_datasets=$((mapped_datasets + 1))

    # Update category counter
    case "$category" in
        Demographics) demographics_count=$((demographics_count + 1)) ;;
        Economy) economy_count=$((economy_count + 1)) ;;
        Health) health_count=$((health_count + 1)) ;;
        Employment) employment_count=$((employment_count + 1)) ;;
        Education) education_count=$((education_count + 1)) ;;
        Energy) energy_count=$((energy_count + 1)) ;;
    esac

    # Define source files based on category
    schema_folder="$SCHEMA_DIR/$category"

    # Copy .txt file (schema examples)
    txt_file=$(find "$schema_folder" -name "*.txt" -type f 2>/dev/null | head -1)
    if [[ -n "$txt_file" && -f "$txt_file" ]]; then
        cp "$txt_file" "$dataset_dir/"
        echo "  Copied: $(basename "$txt_file")"
        txt_copied=$((txt_copied + 1))
    else
        echo "  No .txt file found for $category"
    fi

    # Copy .mcf file (statvars)
    mcf_file=$(find "$schema_folder" -name "*.mcf" -type f 2>/dev/null | head -1)
    if [[ -n "$mcf_file" && -f "$mcf_file" ]]; then
        cp "$mcf_file" "$dataset_dir/"
        echo "  Copied: $(basename "$mcf_file")"
        mcf_copied=$((mcf_copied + 1))
    else
        echo "  No .mcf file found for $category"
    fi

    echo ""
done

echo "=== Summary ==="
echo "Total datasets: $total_datasets"
echo "Mapped datasets: $mapped_datasets"
echo "Unmapped datasets: $unmapped_datasets"
echo ".txt files copied: $txt_copied"
echo ".mcf files copied: $mcf_copied"
echo ""

echo "=== Category Distribution ==="
echo "Demographics: $demographics_count datasets"
echo "Economy: $economy_count datasets"
echo "Health: $health_count datasets"
echo "Employment: $employment_count datasets"
echo "Education: $education_count datasets"
echo "Energy: $energy_count datasets"
