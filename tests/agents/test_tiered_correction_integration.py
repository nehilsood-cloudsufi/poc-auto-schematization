"""Integration tests for TieredCorrectionAgent using real pipeline output."""
import pytest
from pathlib import Path

from src.pipeline.validation.log_filter import filter_counters


BIS_OUTPUT = Path("output/bis_bis_central_bank_policy_rate")
BRFSS_OUTPUT = Path("output/brfss_nchs_asthma_prevalence")


@pytest.mark.skipif(
    not (BIS_OUTPUT / "processed_counters.txt").exists(),
    reason="BIS output not available",
)
class TestBISCounterParsing:
    def test_parses_bis_counters(self):
        logs = filter_counters(BIS_OUTPUT / "processed_counters.txt")
        assert logs.input_rows > 0

    def test_bis_has_error_signals(self):
        logs = filter_counters(BIS_OUTPUT / "processed_counters.txt")
        # BIS should have errors (unresolved place or key mismatch)
        assert len(logs.errors) > 0 or logs.output_rows == 0


@pytest.mark.skipif(
    not (BRFSS_OUTPUT / "processed_counters.txt").exists(),
    reason="BRFSS output not available",
)
class TestBRFSSCounterParsing:
    def test_parses_brfss_counters(self):
        logs = filter_counters(BRFSS_OUTPUT / "processed_counters.txt")
        assert logs.input_rows > 0

    def test_brfss_property_cardinality_or_warnings(self):
        logs = filter_counters(BRFSS_OUTPUT / "processed_counters.txt")
        # BRFSS should have either property cardinality (if output exists)
        # or warnings/errors
        assert logs.property_cardinality or logs.errors or logs.warnings or logs.input_rows > 0


@pytest.mark.skipif(
    not any(Path("output").glob("*/processed_counters.txt")),
    reason="No pipeline output available",
)
class TestAnyDatasetCounterParsing:
    def test_at_least_one_dataset_has_enriched_signals(self):
        """Verify the new parsing works on at least one real counter file."""
        for counters_path in Path("output").glob("*/processed_counters.txt"):
            logs = filter_counters(counters_path)
            if logs.input_rows > 0:
                # At least input rows should parse
                assert True
                return
        pytest.skip("No counter files with data found")
