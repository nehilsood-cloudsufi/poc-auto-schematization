"""Zip creation and download button for pipeline outputs."""
import io
import logging
import zipfile
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)


def create_zip_bytes(output_dir: Path) -> bytes:
    """Create an in-memory zip of the output directory."""
    buffer = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in sorted(output_dir.rglob("*")):
            if fpath.is_file():
                arcname = fpath.relative_to(output_dir.parent)
                zf.write(fpath, arcname)
                file_count += 1

    zip_bytes = buffer.getvalue()
    logger.info("Created zip: %d files, %d bytes", file_count, len(zip_bytes))
    return zip_bytes


def render_download_button(output_dir: Path, dataset_name: str):
    """Render download button for zipped output."""
    st.subheader("Download")

    if not output_dir.exists():
        st.caption("No output yet.")
        return

    zip_bytes = create_zip_bytes(output_dir)
    logger.debug("Rendering download button for %s", dataset_name)

    st.download_button(
        label=":material/download: All Outputs (ZIP)",
        data=zip_bytes,
        file_name=f"{dataset_name}_outputs.zip",
        mime="application/zip",
        use_container_width=True,
    )

    files = sorted(output_dir.rglob("*"))
    file_list = [str(f.relative_to(output_dir)) for f in files if f.is_file()]
    with st.expander(f"{len(file_list)} files"):
        st.caption("\n".join(file_list))
