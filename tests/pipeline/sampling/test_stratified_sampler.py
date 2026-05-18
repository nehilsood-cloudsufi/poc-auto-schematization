"""Tests for the deterministic stratified sampler."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.agents.sampling.schemas import RelationalSkeleton, SemanticAnalysis, ColumnClassification, DependencyEdge
from src.pipeline.sampling.profiler import DatasetProfile, ColumnProfile, profile_dataset
from src.pipeline.sampling.stratified_sampler import (
    SamplingResult,
    _execute_stratified_with_coverage,
    calculate_target_rows,
    execute_sampling,
    select_strategy,
)


# --- Fixtures ---

def _make_analysis(
    topology="TIDY_LONG",
    is_preformatted=False,
    columns=None,
) -> SemanticAnalysis:
    """Create a minimal SemanticAnalysis for testing."""
    if columns is None:
        columns = [
            ColumnClassification(column_name="Place", role="place", confidence="high", reasoning="test", semantic_type="ISO_2"),
            ColumnClassification(column_name="Year", role="time", confidence="high", reasoning="test", semantic_type="YYYY"),
            ColumnClassification(column_name="Gender", role="dimension", confidence="high", reasoning="test"),
            ColumnClassification(column_name="Value", role="value", confidence="high", reasoning="test"),
        ]
    return SemanticAnalysis(
        topology=topology,
        topology_reasoning="test",
        columns=columns,
        population_type="Person",
        measurement_type="Count",
        is_preformatted_dc=is_preformatted,
    )


def _make_skeleton(
    dimension_columns=None,
    place_column="Place",
    time_column="Year",
    value_columns=None,
    aggregate_flags=None,
) -> RelationalSkeleton:
    """Create a minimal RelationalSkeleton for testing."""
    if dimension_columns is None:
        dimension_columns = ["Gender"]
    if value_columns is None:
        value_columns = ["Value"]
    return RelationalSkeleton(
        edges=[],
        statvar_pattern="Count_Person_{Gender}",
        dimension_columns=dimension_columns,
        place_column=place_column,
        time_column=time_column,
        value_columns=value_columns,
        aggregate_flags=aggregate_flags or [],
    )


def _make_profile(columns=None, total_rows=1000) -> DatasetProfile:
    """Create a minimal DatasetProfile for testing."""
    default_columns = {
        "Place": ColumnProfile(name="Place", dtype="String", cardinality=10),
        "Year": ColumnProfile(name="Year", dtype="Integer", cardinality=5, is_numeric_categorical=True),
        "Gender": ColumnProfile(name="Gender", dtype="String", cardinality=3),
        "Value": ColumnProfile(name="Value", dtype="Integer", cardinality=900),
    }
    return DatasetProfile(
        file_path="test.csv",
        total_rows=total_rows,
        total_columns=len(columns or default_columns),
        headers=list((columns or default_columns).keys()),
        columns=columns or default_columns,
    )


@pytest.fixture
def tall_csv(tmp_path):
    """Create a tall/tidy dataset."""
    rows = []
    for place in ["US", "GB", "DE"]:
        for year in [2020, 2021]:
            for gender in ["Male", "Female", "Total"]:
                rows.append({
                    "Place": place,
                    "Year": year,
                    "Gender": gender,
                    "Value": 100000 + hash(f"{place}{year}{gender}") % 100000,
                })
    df = pd.DataFrame(rows)
    csv_path = tmp_path / "tall.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def wide_csv(tmp_path):
    """Create a wide/pivoted dataset."""
    data = {
        "Country": ["US", "GB", "DE", "FR", "JP"],
        "Year": [2020, 2020, 2020, 2020, 2020],
        "Wheat": [250, 240, 260, 255, 270],
        "Corn": [180, 175, 190, 185, 195],
        "Rice": [350, 345, 360, 355, 365],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "wide.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def preformatted_csv(tmp_path):
    """Create a pre-formatted DC dataset."""
    rows = []
    for i in range(50):
        rows.append({
            "observationAbout": f"geoId/{i:02d}",
            "observationDate": "2020",
            "variableMeasured": "dcid:Count_Person",
            "value": 10000 + i * 100,
        })
    df = pd.DataFrame(rows)
    csv_path = tmp_path / "preformatted.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


# --- Strategy selection tests ---

class TestSelectStrategy:
    def test_preformatted_uses_head(self):
        analysis = _make_analysis(is_preformatted=True)
        skeleton = _make_skeleton()
        assert select_strategy(analysis, skeleton) == "head"

    def test_wide_uses_head(self):
        analysis = _make_analysis(topology="PIVOTED_WIDE")
        skeleton = _make_skeleton()
        assert select_strategy(analysis, skeleton) == "head"

    def test_with_dimensions_uses_stratified(self):
        analysis = _make_analysis(topology="TIDY_LONG")
        skeleton = _make_skeleton(dimension_columns=["Gender", "Age"])
        assert select_strategy(analysis, skeleton) == "stratified"

    def test_no_dimensions_uses_random(self):
        analysis = _make_analysis(topology="TIDY_LONG")
        skeleton = _make_skeleton(dimension_columns=[])
        assert select_strategy(analysis, skeleton) == "random"


# --- Target row calculation tests ---

class TestCalculateTargetRows:
    def test_basic_target(self):
        profile = _make_profile()
        analysis = _make_analysis()
        skeleton = _make_skeleton(dimension_columns=["Gender"])
        target = calculate_target_rows(profile, analysis, skeleton)
        # 3 (gender) + 10+5 (anchors) + 5 (edges) = 23 -> clamped to 30
        assert 30 <= target <= 150

    def test_many_dimensions_increases_target(self):
        columns = {
            "Place": ColumnProfile(name="Place", dtype="String", cardinality=50),
            "Year": ColumnProfile(name="Year", dtype="Integer", cardinality=10, is_numeric_categorical=True),
            "Gender": ColumnProfile(name="Gender", dtype="String", cardinality=3),
            "Age": ColumnProfile(name="Age", dtype="String", cardinality=20),
            "Race": ColumnProfile(name="Race", dtype="String", cardinality=8),
            "Value": ColumnProfile(name="Value", dtype="Integer", cardinality=9000),
        }
        profile = _make_profile(columns=columns)
        analysis = _make_analysis()
        skeleton = _make_skeleton(dimension_columns=["Gender", "Age", "Race"])
        target = calculate_target_rows(profile, analysis, skeleton)
        # 3 + 20 + 8 = 31 dims + ~20 anchor+edge = ~51
        assert target > 40

    def test_clamped_to_min(self):
        profile = _make_profile()
        analysis = _make_analysis()
        skeleton = _make_skeleton(dimension_columns=[])
        target = calculate_target_rows(profile, analysis, skeleton)
        assert target >= 30

    def test_clamped_to_max(self):
        columns = {
            "Place": ColumnProfile(name="Place", dtype="String", cardinality=200),
            "Year": ColumnProfile(name="Year", dtype="Integer", cardinality=50, is_numeric_categorical=True),
            "Dim1": ColumnProfile(name="Dim1", dtype="String", cardinality=100),
            "Dim2": ColumnProfile(name="Dim2", dtype="String", cardinality=100),
            "Value": ColumnProfile(name="Value", dtype="Integer", cardinality=50000),
        }
        profile = _make_profile(columns=columns, total_rows=100000)
        analysis = _make_analysis()
        skeleton = _make_skeleton(dimension_columns=["Dim1", "Dim2"])
        target = calculate_target_rows(profile, analysis, skeleton)
        assert target <= 150


# --- Sampling execution tests ---

class TestExecuteSampling:
    def test_stratified_sampling(self, tall_csv):
        profile = profile_dataset(tall_csv)
        analysis = _make_analysis()
        skeleton = _make_skeleton()
        output = tall_csv.parent / "sampled.csv"

        result = execute_sampling(
            file_path=tall_csv,
            output_path=output,
            skeleton=skeleton,
            analysis=analysis,
            profile=profile,
            target_rows=12,
        )
        assert result.success is True
        assert result.rows_sampled > 0
        assert output.exists()
        df = pd.read_csv(output)
        assert len(df) > 0

    def test_head_sampling_wide(self, wide_csv):
        profile = profile_dataset(wide_csv)
        analysis = _make_analysis(topology="PIVOTED_WIDE")
        skeleton = _make_skeleton(
            dimension_columns=[],
            place_column="Country",
            value_columns=["Wheat", "Corn", "Rice"],
        )
        output = wide_csv.parent / "sampled.csv"

        result = execute_sampling(
            file_path=wide_csv,
            output_path=output,
            skeleton=skeleton,
            analysis=analysis,
            profile=profile,
        )
        assert result.success is True
        assert result.strategy_used == "head"

    def test_head_sampling_preformatted(self, preformatted_csv):
        profile = profile_dataset(preformatted_csv)
        analysis = _make_analysis(is_preformatted=True)
        skeleton = _make_skeleton(
            dimension_columns=[],
            place_column="observationAbout",
            time_column="observationDate",
            value_columns=["value"],
        )
        output = preformatted_csv.parent / "sampled.csv"

        result = execute_sampling(
            file_path=preformatted_csv,
            output_path=output,
            skeleton=skeleton,
            analysis=analysis,
            profile=profile,
        )
        assert result.success is True
        assert result.strategy_used == "head"

    def test_file_not_found(self, tmp_path):
        result = execute_sampling(
            file_path=tmp_path / "nonexistent.csv",
            output_path=tmp_path / "out.csv",
            skeleton=_make_skeleton(),
            analysis=_make_analysis(),
            profile=_make_profile(),
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_coverage_stats_returned(self, tall_csv):
        profile = profile_dataset(tall_csv)
        analysis = _make_analysis()
        skeleton = _make_skeleton(
            place_column="Place", time_column="Year", dimension_columns=["Gender"]
        )
        output = tall_csv.parent / "sampled.csv"

        result = execute_sampling(
            file_path=tall_csv,
            output_path=output,
            skeleton=skeleton,
            analysis=analysis,
            profile=profile,
        )
        assert result.success is True
        assert isinstance(result.coverage_stats, dict)


# --- Dimension coverage guarantee tests ---

@pytest.fixture
def census_like_csv(tmp_path):
    """Create a Census SAHIE-like dataset with multiple dimension columns.

    agecat: [0, 1] (2 values)
    racecat: [0, 1, 2, 3] (4 values)
    100 rows total — sampling to 30 rows must cover ALL dimension values.
    """
    import random
    random.seed(42)
    rows = []
    places = [f"geoId/{i:02d}" for i in range(10)]
    years = [2020, 2021]
    agecats = [0, 1]
    racecats = [0, 1, 2, 3]

    for _ in range(100):
        rows.append({
            "Place": random.choice(places),
            "Year": random.choice(years),
            "agecat": random.choice(agecats),
            "racecat": random.choice(racecats),
            "Value": random.randint(1000, 99999),
        })
    df = pd.DataFrame(rows)
    csv_path = tmp_path / "census_sahie.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def metadata_polluted_csv(tmp_path):
    """Create a dataset with a metadata/unit row (World Bank-style)."""
    data = {
        "Commodity": ["Crude oil", "(units)", "Natural gas", "Coal",
                       "Gold", "Silver", "Copper", "Zinc",
                       "Lead", "Tin"],
        "Price_2020": [42.3, "($/bbl)", 2.1, 60.5, 1770.0,
                       25.0, 6000.0, 2500.0, 1800.0, 17000.0],
        "Price_2021": [70.7, "($/bbl)", 3.8, 130.0, 1800.0,
                       26.0, 9000.0, 3000.0, 2200.0, 30000.0],
        "Price_2022": [99.0, "($/bbl)", 6.5, 350.0, 1820.0,
                       22.0, 8000.0, 3500.0, 2000.0, 25000.0],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "commodities_with_units.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


class TestDimensionCoverageGuarantee:
    def test_all_dimension_values_covered(self, census_like_csv):
        """Stratified sampling must cover ALL unique values of ALL dimension columns."""
        profile = profile_dataset(census_like_csv)
        skeleton = _make_skeleton(
            dimension_columns=["agecat", "racecat"],
            place_column="Place",
            time_column="Year",
            value_columns=["Value"],
        )
        analysis = _make_analysis(
            columns=[
                ColumnClassification(column_name="Place", role="place", confidence="high", reasoning="test", semantic_type="DC_DCID"),
                ColumnClassification(column_name="Year", role="time", confidence="high", reasoning="test", semantic_type="YYYY"),
                ColumnClassification(column_name="agecat", role="dimension", confidence="high", reasoning="test"),
                ColumnClassification(column_name="racecat", role="dimension", confidence="high", reasoning="test"),
                ColumnClassification(column_name="Value", role="value", confidence="high", reasoning="test"),
            ]
        )
        output = census_like_csv.parent / "sampled.csv"

        result = execute_sampling(
            file_path=census_like_csv,
            output_path=output,
            skeleton=skeleton,
            analysis=analysis,
            profile=profile,
            target_rows=30,
        )
        assert result.success is True

        sampled = pd.read_csv(output)
        # ALL agecat values must appear
        assert set(sampled["agecat"].unique()) == {0, 1}
        # ALL racecat values must appear
        assert set(sampled["racecat"].unique()) == {0, 1, 2, 3}

    def test_coverage_with_small_budget(self, census_like_csv):
        """Even with a very small target, coverage pass should include all dimension values."""
        profile = profile_dataset(census_like_csv)
        output = census_like_csv.parent / "sampled_small.csv"

        result = _execute_stratified_with_coverage(
            file_path=census_like_csv,
            output_path=output,
            target_rows=10,
            dimension_columns=["agecat", "racecat"],
            profile=profile,
        )
        assert result["success"] is True

        sampled = pd.read_csv(output)
        # Even with target=10, all 6 unique dimension values (2+4) should be covered
        assert set(sampled["agecat"].unique()) == {0, 1}
        assert set(sampled["racecat"].unique()) == {0, 1, 2, 3}
        assert len(sampled) <= 10

    def test_no_valid_dims_falls_back_to_random(self, census_like_csv):
        """If dimension columns don't exist in the data, fall back to random."""
        profile = profile_dataset(census_like_csv)
        output = census_like_csv.parent / "sampled_nodim.csv"

        result = _execute_stratified_with_coverage(
            file_path=census_like_csv,
            output_path=output,
            target_rows=20,
            dimension_columns=["nonexistent_col"],
            profile=profile,
        )
        assert result["success"] is True


class TestMetadataRowExclusion:
    def test_metadata_rows_excluded_from_sample(self, metadata_polluted_csv):
        """Metadata rows (unit descriptors) should not appear in sampled output."""
        profile = profile_dataset(metadata_polluted_csv)
        # Profile should have detected the metadata row
        assert len(profile.metadata_rows) >= 1

        skeleton = _make_skeleton(
            dimension_columns=[],
            place_column="Commodity",
            value_columns=["Price_2020", "Price_2021", "Price_2022"],
        )
        analysis = _make_analysis(topology="TIDY_LONG")
        output = metadata_polluted_csv.parent / "sampled.csv"

        result = execute_sampling(
            file_path=metadata_polluted_csv,
            output_path=output,
            skeleton=skeleton,
            analysis=analysis,
            profile=profile,
        )
        assert result.success is True

        sampled = pd.read_csv(output)
        # Unit descriptor row "($/bbl)" should NOT be in the sample
        assert "($/bbl)" not in sampled["Price_2020"].astype(str).values
        assert "(units)" not in sampled["Commodity"].values


class TestNaNInDimensionColumns:
    """Regression: NaN values in dimension columns used to trigger
    'index 0 is out of bounds for axis 0 with size 0' because
    df[df[col] == NaN] is always empty (NaN != NaN in pandas).
    """

    def test_nan_in_dimension_does_not_crash(self, tmp_path):
        """Sampling must succeed when dimension columns contain NaN."""
        rows = []
        for sex in ["Female", "Male"]:
            for race in ["A", "B"]:
                rows.append({"Sex": sex, "Race": race, "Place": "US", "Year": 2020, "Value": 100})
        # Add rows with NaN in dimension columns
        for _ in range(5):
            rows.append({"Sex": None, "Race": None, "Place": "US", "Year": 2020, "Value": 200})
        df = pd.DataFrame(rows)
        csv_path = tmp_path / "with_nan_dims.csv"
        df.to_csv(csv_path, index=False)

        profile = profile_dataset(csv_path)
        output = tmp_path / "sampled.csv"

        result = _execute_stratified_with_coverage(
            file_path=csv_path,
            output_path=output,
            target_rows=20,
            dimension_columns=["Sex", "Race"],
            profile=profile,
        )
        assert result["success"] is True
        assert result["rows_sampled"] > 0
