import streamlit as st
import pandas as pd
import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add paths for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "tools" / "statvar_importer"))
sys.path.append(str(Path(__file__).parent / "util"))

# Import Agno pipeline
from agno_pipeline import run_pipeline, PVMAPAgent

# Page config
st.set_page_config(page_title="Auto-Schematization Pipeline", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #ffffff; }
    .diff-added { background-color: #d4edda; padding: 2px 5px; }
    .diff-deleted { background-color: #f8d7da; padding: 2px 5px; }
    .diff-modified { background-color: #fff3cd; padding: 2px 5px; }
</style>
""", unsafe_allow_html=True)

st.title("Auto-Schematization Pipeline")
st.markdown("Transform CSV data into Data Commons schema using **Gemini**")

# Load config from .env
gemini_api_key = os.getenv("GOOGLE_API_KEY", "")
gemini_model = os.getenv("GEMINI_MODEL", "google/gemini-3-pro-preview")

# Sidebar - Dataset History
with st.sidebar:
    st.header("Processed Datasets")

    output_dir = Path("output")
    if output_dir.exists():
        datasets = sorted([d.name for d in output_dir.iterdir() if d.is_dir()], reverse=True)
        if datasets:
            for ds in datasets:
                pvmap_exists = (output_dir / ds / "generated_pvmap.csv").exists()
                status = "✅" if pvmap_exists else "⏳"
                if st.sidebar.button(f"{status} {ds}", key=f"hist_{ds}", use_container_width=True):
                    st.session_state['selected_dataset'] = ds
        else:
            st.info("No datasets processed yet")
    else:
        st.info("No datasets processed yet")

    st.divider()
    st.caption(f"Model: {gemini_model}")
    if gemini_api_key:
        st.caption("✅ API Key loaded")
    else:
        st.caption("⚠️ No API Key in .env")

# Main upload section
col1, col2 = st.columns(2)

with col1:
    st.subheader("Upload Data File")
    data_file = st.file_uploader("Upload CSV data file", type=['csv'], key="data")

with col2:
    st.subheader("Upload Metadata")
    metadata_file = st.file_uploader("Upload metadata CSV", type=['csv'], key="metadata")

# Schema and dataset
col1, col2 = st.columns(2)
with col1:
    schemas = ["Demographics", "Economy", "Education", "Employment", "Energy", "Health"]
    selected_schema = st.selectbox("Schema Category (optional)", schemas, index=None, placeholder="Auto-detect using Gemini")
with col2:
    dataset_name = st.text_input("Dataset Name (optional)", placeholder="Auto-generated if empty")

# Options
with st.expander("Advanced Options"):
    col1, col2 = st.columns(2)
    with col1:
        skip_evaluation = st.checkbox("Skip Evaluation", value=True)
    with col2:
        force_resample = st.checkbox("Force Resample", value=False)

# Process button
if st.button("Process Dataset", type="primary", use_container_width=True):
    if not gemini_api_key:
        st.error("No API key found. Add GOOGLE_API_KEY to your .env file")
    elif data_file and metadata_file:
        # Auto-generate dataset name if not provided
        if not dataset_name:
            dataset_name = f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.info(f"Using auto-generated name: {dataset_name}")
        with st.spinner("Processing with Gemini..."):
            input_dir = Path(f"input/{dataset_name}")
            test_data_dir = input_dir / "test_data"
            test_data_dir.mkdir(parents=True, exist_ok=True)

            # Save files
            data_path = test_data_dir / f"{dataset_name}_input.csv"
            metadata_path = input_dir / f"{dataset_name}_metadata.csv"
            with open(data_path, "wb") as f:
                f.write(data_file.getbuffer())
            with open(metadata_path, "wb") as f:
                f.write(metadata_file.getbuffer())

            # Handle schema selection
            schema_to_use = selected_schema if selected_schema else None
            if not schema_to_use:
                st.info("Schema will be auto-detected using Gemini...")

            # Run Agno pipeline
            try:
                output_path = Path("output") / dataset_name
                success, message = run_pipeline(
                    dataset_name=dataset_name,
                    input_dir=input_dir,
                    output_dir=output_path,
                    schema_category=schema_to_use,
                    api_key=gemini_api_key,
                    model_id=gemini_model,
                    max_retries=2
                )

                if success:
                    st.success(f"Pipeline completed! {message}")
                    st.session_state['last_dataset'] = dataset_name
                else:
                    st.error(f"Pipeline failed: {message}")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Please upload both data file and metadata file")

st.divider()

# Results Section
st.header("Results & Evaluation")

tab1, tab2 = st.tabs(["Dataset Results", "Compare with Ground Truth"])

with tab1:
    st.subheader("View Generated PVMAP")

    # List available outputs
    output_path = Path("output")
    if output_path.exists():
        available_datasets = [d.name for d in output_path.iterdir() if d.is_dir()]
        if available_datasets:
            # Use session state if set from sidebar
            default_idx = 0
            if 'selected_dataset' in st.session_state and st.session_state['selected_dataset'] in available_datasets:
                default_idx = available_datasets.index(st.session_state['selected_dataset'])
            selected_dataset = st.selectbox("Select Dataset", available_datasets, index=default_idx)
            pvmap_path = output_path / selected_dataset / "generated_pvmap.csv"

            if pvmap_path.exists():
                try:
                    df = pd.read_csv(pvmap_path, on_bad_lines='skip')
                except:
                    df = pd.read_csv(pvmap_path, sep=',', engine='python', on_bad_lines='skip')
                st.dataframe(df, use_container_width=True, height=400)

                # Show stats
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Rows", len(df))
                col2.metric("Columns", len(df.columns))
                col3.metric("Schema", selected_schema)

                # Download button
                st.download_button("Download PVMAP", df.to_csv(index=False), f"{selected_dataset}_pvmap.csv")
            else:
                st.info("No generated PVMAP found for this dataset")
        else:
            st.info("No processed datasets found. Run the pipeline first.")
    else:
        st.info("No output directory found. Run the pipeline first.")

with tab2:
    st.subheader("Compare Generated PVMAP with Ground Truth")

    col1, col2 = st.columns(2)

    with col1:
        # Select generated pvmap
        if output_path.exists():
            compare_datasets = [d.name for d in output_path.iterdir() if d.is_dir()]
            if compare_datasets:
                compare_dataset = st.selectbox("Select Generated PVMAP", compare_datasets, key="compare")
            else:
                compare_dataset = None
                st.info("No datasets available")
        else:
            compare_dataset = None

    with col2:
        # Upload ground truth
        ground_truth_file = st.file_uploader("Upload Ground Truth PVMAP", type=['csv'], key="gt")

    if st.button("Compare", type="secondary", use_container_width=True):
        if compare_dataset and ground_truth_file:
            with st.spinner("Comparing..."):
                gen_pvmap_path = output_path / compare_dataset / "generated_pvmap.csv"

                if gen_pvmap_path.exists():
                    # Save ground truth temporarily
                    gt_path = Path(f"/tmp/gt_{compare_dataset}.csv")
                    with open(gt_path, "wb") as f:
                        f.write(ground_truth_file.getbuffer())

                    # Load both CSVs
                    try:
                        gen_df = pd.read_csv(gen_pvmap_path, on_bad_lines='skip')
                    except:
                        gen_df = pd.read_csv(gen_pvmap_path, engine='python', on_bad_lines='skip')
                    try:
                        gt_df = pd.read_csv(gt_path, on_bad_lines='skip')
                    except:
                        gt_df = pd.read_csv(gt_path, engine='python', on_bad_lines='skip')

                    # Simple comparison
                    gen_keys = set(gen_df.iloc[:, 0].astype(str).tolist()) if len(gen_df) > 0 else set()
                    gt_keys = set(gt_df.iloc[:, 0].astype(str).tolist()) if len(gt_df) > 0 else set()

                    matched = gen_keys & gt_keys
                    only_gen = gen_keys - gt_keys
                    only_gt = gt_keys - gen_keys

                    # Metrics
                    st.subheader("Comparison Results")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Matched Keys", len(matched), delta=None)
                    col2.metric("Only in Generated", len(only_gen), delta=f"-{len(only_gen)}" if only_gen else None, delta_color="inverse")
                    col3.metric("Only in Ground Truth", len(only_gt), delta=f"-{len(only_gt)}" if only_gt else None, delta_color="inverse")

                    total = len(gt_keys) if gt_keys else 1
                    accuracy = round(len(matched) / total * 100, 1)
                    col4.metric("Key Accuracy", f"{accuracy}%")

                    # Visual diff
                    st.subheader("Differential View")

                    diff_col1, diff_col2 = st.columns(2)

                    with diff_col1:
                        st.markdown("**Generated PVMAP**")
                        st.dataframe(gen_df, height=300, use_container_width=True)

                    with diff_col2:
                        st.markdown("**Ground Truth PVMAP**")
                        st.dataframe(gt_df, height=300, use_container_width=True)

                    # Detailed diff
                    st.subheader("Detailed Differences")

                    if only_gen:
                        with st.expander(f"Keys only in Generated ({len(only_gen)})", expanded=False):
                            for k in list(only_gen)[:20]:
                                st.markdown(f"<span class='diff-added'>+ {k}</span>", unsafe_allow_html=True)

                    if only_gt:
                        with st.expander(f"Keys missing from Generated ({len(only_gt)})", expanded=False):
                            for k in list(only_gt)[:20]:
                                st.markdown(f"<span class='diff-deleted'>- {k}</span>", unsafe_allow_html=True)

                    if matched:
                        with st.expander(f"Matched Keys ({len(matched)})", expanded=False):
                            for k in list(matched)[:20]:
                                st.markdown(f"✓ {k}")

                    # Bar chart comparison
                    st.subheader("Visual Comparison")
                    chart_df = pd.DataFrame({
                        "Category": ["Matched", "Only Generated", "Only Ground Truth"],
                        "Count": [len(matched), len(only_gen), len(only_gt)]
                    })
                    st.bar_chart(chart_df.set_index("Category"), height=250)

                else:
                    st.error("Generated PVMAP not found")
        else:
            st.warning("Select a dataset and upload ground truth file")

st.divider()
st.caption("Auto-Schematization POC | Powered by Gemini")
