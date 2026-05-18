"""Tests for CandidateRetriever — role assignment, Schema.org lookup, vocab lookup, merge."""

import json

import pytest

from src.api.models.plan import CandidateSource, ColumnRole, PropertyValueCandidate
from src.pipeline.plan.candidate_retriever import CandidateRetriever, _tokenize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_col(
    name: str = "col",
    dtype: str = "String",
    semantic_type: str = None,
    cardinality: int = 10,
    cardinality_ratio: float = 0.1,
    looks_like_place: bool = False,
    looks_like_date: bool = False,
    **extra,
) -> dict:
    """Build a minimal column profile dict."""
    d = {
        "name": name,
        "dtype": dtype,
        "semantic_type": semantic_type,
        "cardinality": cardinality,
        "cardinality_ratio": cardinality_ratio,
        "looks_like_place": looks_like_place,
        "looks_like_date": looks_like_date,
        "null_pct": 0.0,
        "top_values": [],
        "sample_values": [],
    }
    d.update(extra)
    return d


ECONOMY_VOCAB = json.dumps({
    "category": "Economy",
    "stat_var_skeletons": {
        "Person": ["age", "gender", "income", "employmentStatus"],
        "Household": ["householdType", "incomeStatus"],
    },
    "property_vocabulary": {
        "age": ["Years15Onwards", "Years16Onwards"],
        "gender": ["Female", "Male"],
        "income": ["USDollar10000To14999"],
        "employmentStatus": ["BLS_Employed"],
        "householdType": ["FamilyHousehold"],
        "incomeStatus": ["WithEarnings"],
    },
})


# ---------------------------------------------------------------------------
# _assign_role tests
# ---------------------------------------------------------------------------

class TestAssignRole:
    """Tests for CandidateRetriever._assign_role."""

    @pytest.fixture
    def retriever(self):
        return CandidateRetriever()

    def test_place_by_semantic_type(self, retriever):
        col = _make_col(semantic_type="FIPS_STATE")
        assert retriever._assign_role(col) == ColumnRole.OBSERVATION_ABOUT

    def test_place_by_looks_like_place(self, retriever):
        col = _make_col(looks_like_place=True)
        assert retriever._assign_role(col) == ColumnRole.OBSERVATION_ABOUT

    def test_date_by_semantic_type(self, retriever):
        col = _make_col(semantic_type="YYYY")
        assert retriever._assign_role(col) == ColumnRole.OBSERVATION_DATE

    def test_date_by_looks_like_date(self, retriever):
        col = _make_col(looks_like_date=True)
        assert retriever._assign_role(col) == ColumnRole.OBSERVATION_DATE

    def test_measure_float_high_cardinality(self, retriever):
        col = _make_col(dtype="Float", cardinality=500, cardinality_ratio=0.5)
        assert retriever._assign_role(col) == ColumnRole.MEASURE

    def test_measure_integer_high_cardinality(self, retriever):
        col = _make_col(dtype="Integer", cardinality=300, cardinality_ratio=0.35)
        assert retriever._assign_role(col) == ColumnRole.MEASURE

    def test_ignored_zero_cardinality(self, retriever):
        col = _make_col(cardinality=0)
        assert retriever._assign_role(col) == ColumnRole.IGNORED

    def test_ignored_empty_dtype(self, retriever):
        col = _make_col(dtype="Empty", cardinality=5)
        assert retriever._assign_role(col) == ColumnRole.IGNORED

    def test_ignored_constant(self, retriever):
        col = _make_col(cardinality=1)
        assert retriever._assign_role(col) == ColumnRole.IGNORED

    def test_dimension_default(self, retriever):
        col = _make_col(dtype="String", cardinality=10, cardinality_ratio=0.05)
        assert retriever._assign_role(col) == ColumnRole.DIMENSION

    def test_numeric_low_cardinality_is_dimension(self, retriever):
        """Integer with low cardinality_ratio should be DIMENSION, not MEASURE."""
        col = _make_col(dtype="Integer", cardinality=5, cardinality_ratio=0.02)
        assert retriever._assign_role(col) == ColumnRole.DIMENSION

    def test_place_takes_priority_over_numeric(self, retriever):
        """Place semantic type should override numeric measure heuristic."""
        col = _make_col(
            dtype="Integer", cardinality=500, cardinality_ratio=0.5,
            semantic_type="FIPS_STATE",
        )
        assert retriever._assign_role(col) == ColumnRole.OBSERVATION_ABOUT


# ---------------------------------------------------------------------------
# Schema.org candidate tests
# ---------------------------------------------------------------------------

class TestSchemaOrgCandidates:
    """Tests for CandidateRetriever._get_schemaorg_candidates."""

    @pytest.fixture
    def retriever(self):
        return CandidateRetriever()

    def test_place_returns_hardcoded(self, retriever):
        col = _make_col(semantic_type="ISO_3")
        cands = retriever._get_schemaorg_candidates(col)
        assert len(cands) >= 1
        assert cands[0].property == "observationAbout"
        assert cands[0].confidence == 0.95
        assert cands[0].source == CandidateSource.SCHEMA_ORG

    def test_date_returns_hardcoded(self, retriever):
        col = _make_col(looks_like_date=True)
        cands = retriever._get_schemaorg_candidates(col)
        assert len(cands) >= 1
        assert cands[0].property == "observationDate"
        assert cands[0].confidence == 0.95

    def test_measure_returns_hardcoded(self, retriever):
        col = _make_col(dtype="Float", cardinality_ratio=0.5)
        cands = retriever._get_schemaorg_candidates(col)
        assert len(cands) >= 1
        assert cands[0].property == "value"
        assert cands[0].confidence == 0.85

    def test_unknown_column_searches_schemaorg(self, retriever):
        """For an unknown column, should search Schema.org and return results at 0.50 confidence."""
        col = _make_col(name="gender", dtype="String", cardinality=3, cardinality_ratio=0.01)
        cands = retriever._get_schemaorg_candidates(col)
        # Results depend on Schema.org cache being present; if missing, empty is OK
        for c in cands:
            assert c.confidence == 0.50
            assert c.source == CandidateSource.SCHEMA_ORG

    def test_empty_name_returns_empty(self, retriever):
        col = _make_col(name="")
        cands = retriever._get_schemaorg_candidates(col)
        assert cands == []


# ---------------------------------------------------------------------------
# Vocab candidate tests
# ---------------------------------------------------------------------------

class TestVocabCandidates:
    """Tests for CandidateRetriever._get_vocab_candidates."""

    @pytest.fixture
    def retriever(self):
        return CandidateRetriever()

    def test_matching_single_word(self, retriever):
        col = _make_col(name="age")
        cands = retriever._get_vocab_candidates(col, ECONOMY_VOCAB)
        props = [c.property for c in cands]
        assert "age" in props

    def test_confidence_base_plus_overlap(self, retriever):
        """Single-word overlap should give 0.40 + 0.15 = 0.55."""
        col = _make_col(name="age")
        cands = retriever._get_vocab_candidates(col, ECONOMY_VOCAB)
        age_cand = next(c for c in cands if c.property == "age")
        assert age_cand.confidence == 0.55

    def test_multi_word_overlap(self, retriever):
        """Column 'household_type' should match 'householdType' with 2-word overlap."""
        col = _make_col(name="household_type")
        cands = retriever._get_vocab_candidates(col, ECONOMY_VOCAB)
        props = [c.property for c in cands]
        assert "householdType" in props
        ht_cand = next(c for c in cands if c.property == "householdType")
        # "household" and "type" both overlap -> 0.40 + 0.15 * 2 = 0.70
        assert ht_cand.confidence == 0.70

    def test_no_match_returns_empty(self, retriever):
        col = _make_col(name="zzz_unknown_xyz")
        cands = retriever._get_vocab_candidates(col, ECONOMY_VOCAB)
        assert cands == []

    def test_empty_vocab_returns_empty(self, retriever):
        col = _make_col(name="age")
        assert retriever._get_vocab_candidates(col, "") == []

    def test_invalid_json_returns_empty(self, retriever):
        col = _make_col(name="age")
        assert retriever._get_vocab_candidates(col, "not json") == []

    def test_source_is_schema_vocab(self, retriever):
        col = _make_col(name="gender")
        cands = retriever._get_vocab_candidates(col, ECONOMY_VOCAB)
        for c in cands:
            assert c.source == CandidateSource.SCHEMA_VOCAB

    def test_value_expression_uses_vocab_values(self, retriever):
        """When property_vocabulary has values, value_expression should reference first value."""
        col = _make_col(name="gender")
        cands = retriever._get_vocab_candidates(col, ECONOMY_VOCAB)
        gender_cand = next(c for c in cands if c.property == "gender")
        assert gender_cand.value_expression == "dcid:Female"

    def test_confidence_capped_at_080(self, retriever):
        """Confidence should not exceed 0.80 even with many word overlaps."""
        # Create a vocab with a very long property name that shares many tokens
        vocab = json.dumps({
            "stat_var_skeletons": {
                "T": ["some_very_long_property_name_here"],
            },
            "property_vocabulary": {},
        })
        col = _make_col(name="some_very_long_property_name_here")
        cands = retriever._get_vocab_candidates(col, vocab)
        for c in cands:
            assert c.confidence <= 0.80


# ---------------------------------------------------------------------------
# Merge tests
# ---------------------------------------------------------------------------

class TestMergeCandidates:
    """Tests for CandidateRetriever._merge_candidates."""

    @pytest.fixture
    def retriever(self):
        return CandidateRetriever()

    def test_dedup_keeps_higher_confidence(self, retriever):
        c1 = PropertyValueCandidate(
            property="gender", value_expression="{col}", confidence=0.50,
            source=CandidateSource.SCHEMA_ORG, reason="r1",
        )
        c2 = PropertyValueCandidate(
            property="gender", value_expression="dcid:Female", confidence=0.55,
            source=CandidateSource.SCHEMA_VOCAB, reason="r2",
        )
        merged = retriever._merge_candidates([c1, c2])
        assert len(merged) == 1
        assert merged[0].confidence == 0.55
        assert merged[0].source == CandidateSource.SCHEMA_VOCAB

    def test_tied_confidence_prefers_specific(self, retriever):
        c1 = PropertyValueCandidate(
            property="age", value_expression="{col}", confidence=0.55,
            source=CandidateSource.SCHEMA_ORG, reason="r1",
        )
        c2 = PropertyValueCandidate(
            property="age", value_expression="dcid:Years15Onwards", confidence=0.55,
            source=CandidateSource.SCHEMA_VOCAB, reason="r2",
        )
        merged = retriever._merge_candidates([c1, c2])
        assert len(merged) == 1
        assert merged[0].value_expression == "dcid:Years15Onwards"

    def test_different_properties_kept(self, retriever):
        c1 = PropertyValueCandidate(
            property="gender", value_expression="{col}", confidence=0.50,
            source=CandidateSource.SCHEMA_ORG, reason="r1",
        )
        c2 = PropertyValueCandidate(
            property="age", value_expression="dcid:Years15Onwards", confidence=0.55,
            source=CandidateSource.SCHEMA_VOCAB, reason="r2",
        )
        merged = retriever._merge_candidates([c1, c2])
        assert len(merged) == 2

    def test_sorted_by_confidence_descending(self, retriever):
        c1 = PropertyValueCandidate(
            property="a", value_expression="x", confidence=0.30,
            source=CandidateSource.SCHEMA_ORG, reason="r",
        )
        c2 = PropertyValueCandidate(
            property="b", value_expression="y", confidence=0.80,
            source=CandidateSource.SCHEMA_VOCAB, reason="r",
        )
        c3 = PropertyValueCandidate(
            property="c", value_expression="z", confidence=0.55,
            source=CandidateSource.SCHEMA_ORG, reason="r",
        )
        merged = retriever._merge_candidates([c1, c2, c3])
        confs = [c.confidence for c in merged]
        assert confs == sorted(confs, reverse=True)

    def test_empty_input(self, retriever):
        assert retriever._merge_candidates([]) == []


# ---------------------------------------------------------------------------
# Tokenizer tests
# ---------------------------------------------------------------------------

class TestTokenize:

    def test_snake_case(self):
        assert _tokenize("employment_status") == ["employment", "status"]

    def test_camel_case(self):
        assert _tokenize("employmentStatus") == ["employment", "status"]

    def test_mixed(self):
        assert _tokenize("FIPS_state_Code") == ["fips", "state", "code"]

    def test_single_word(self):
        assert _tokenize("age") == ["age"]

    def test_empty_string(self):
        assert _tokenize("") == []


# ---------------------------------------------------------------------------
# Integration: retrieve_for_column
# ---------------------------------------------------------------------------

class TestRetrieveForColumn:

    @pytest.fixture
    def retriever(self):
        return CandidateRetriever()

    def test_place_column(self, retriever):
        col = _make_col(name="country", semantic_type="ISO_3")
        role, cands, evidence = retriever.retrieve_for_column(col, ECONOMY_VOCAB)
        assert role == ColumnRole.OBSERVATION_ABOUT
        assert any(c.property == "observationAbout" for c in cands)
        assert "country" in evidence

    def test_date_column(self, retriever):
        col = _make_col(name="year", semantic_type="YYYY")
        role, cands, evidence = retriever.retrieve_for_column(col)
        assert role == ColumnRole.OBSERVATION_DATE
        assert any(c.property == "observationDate" for c in cands)

    def test_measure_column(self, retriever):
        col = _make_col(name="value", dtype="Float", cardinality=1000, cardinality_ratio=0.8)
        role, cands, evidence = retriever.retrieve_for_column(col)
        assert role == ColumnRole.MEASURE
        assert any(c.property == "value" for c in cands)

    def test_dimension_column_with_vocab(self, retriever):
        col = _make_col(name="gender", dtype="String", cardinality=3, cardinality_ratio=0.01)
        role, cands, evidence = retriever.retrieve_for_column(col, ECONOMY_VOCAB)
        assert role == ColumnRole.DIMENSION
        # Should have vocab candidate for "gender"
        vocab_cands = [c for c in cands if c.source == CandidateSource.SCHEMA_VOCAB]
        assert len(vocab_cands) >= 1

    def test_ignored_column(self, retriever):
        col = _make_col(name="constant", cardinality=1)
        role, cands, evidence = retriever.retrieve_for_column(col)
        assert role == ColumnRole.IGNORED


# ---------------------------------------------------------------------------
# Integration: retrieve_all
# ---------------------------------------------------------------------------

class TestRetrieveAll:

    @pytest.fixture
    def retriever(self):
        return CandidateRetriever()

    def test_processes_all_columns(self, retriever):
        columns = {
            "country": _make_col(name="country", semantic_type="ISO_3"),
            "year": _make_col(name="year", semantic_type="YYYY"),
            "value": _make_col(name="value", dtype="Float", cardinality=500, cardinality_ratio=0.5),
            "gender": _make_col(name="gender", dtype="String", cardinality=3, cardinality_ratio=0.01),
        }
        results = retriever.retrieve_all(columns, ECONOMY_VOCAB)
        assert set(results.keys()) == {"country", "year", "value", "gender"}

        # Check roles
        assert results["country"][0] == ColumnRole.OBSERVATION_ABOUT
        assert results["year"][0] == ColumnRole.OBSERVATION_DATE
        assert results["value"][0] == ColumnRole.MEASURE
        assert results["gender"][0] == ColumnRole.DIMENSION

    def test_empty_columns(self, retriever):
        results = retriever.retrieve_all({})
        assert results == {}
