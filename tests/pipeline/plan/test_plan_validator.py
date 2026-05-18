"""Tests for PlanValidator -- DC API validation of candidates."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.models.plan import (
    CandidateSource,
    CandidateValidation,
    ColumnMapping,
    ColumnRole,
    DatasetUnderstanding,
    MappingPlan,
    PropertyValueCandidate,
    StaticProperty,
)
from src.pipeline.plan.plan_validator import (
    PlanValidator,
    WELL_KNOWN_PROPERTIES,
    clear_property_cache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure a clean property cache for every test."""
    clear_property_cache()
    yield
    clear_property_cache()


def _make_candidate(prop: str = "measuredProperty", value: str = "{col}") -> PropertyValueCandidate:
    return PropertyValueCandidate(
        property=prop,
        value_expression=value,
        confidence=0.9,
        source=CandidateSource.LLM,
        reason="test",
    )


def _make_plan(
    active_candidates: list[PropertyValueCandidate] | None = None,
    static_candidates: list[PropertyValueCandidate] | None = None,
) -> MappingPlan:
    active_cols = []
    if active_candidates:
        active_cols.append(
            ColumnMapping(
                column_name="col_a",
                role=ColumnRole.MEASURE,
                candidates=active_candidates,
                evidence="test evidence",
            )
        )

    static_props = []
    if static_candidates:
        static_props.append(
            StaticProperty(
                property_name="populationType",
                candidates=static_candidates,
            )
        )

    return MappingPlan(
        dataset_name="test_dataset",
        understanding=DatasetUnderstanding(
            archetype="Wide",
            observation_grain="country-year",
            key_insight="test insight",
        ),
        active_columns=active_cols,
        ignored_columns=[],
        static_properties=static_props,
        global_notes=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckPropertyExists:
    """Unit tests for _check_property_exists."""

    @pytest.mark.asyncio
    async def test_well_known_properties_return_true_immediately(self):
        """Well-known properties should return True without any HTTP call."""
        validator = PlanValidator()
        for prop in WELL_KNOWN_PROPERTIES:
            assert await validator._check_property_exists(prop) is True

    @pytest.mark.asyncio
    async def test_api_success_property_found(self):
        """When the DC API returns data for the property, return True."""
        validator = PlanValidator()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"dcid:myCustomProp": {"arcs": {"name": {}}}}
        }

        with patch("src.pipeline.plan.plan_validator.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await validator._check_property_exists("myCustomProp")
            assert result is True

    @pytest.mark.asyncio
    async def test_api_success_property_not_found(self):
        """When the DC API returns empty data, return False."""
        validator = PlanValidator()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {}}

        with patch("src.pipeline.plan.plan_validator.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await validator._check_property_exists("totallyFakeProp")
            assert result is False

    @pytest.mark.asyncio
    async def test_api_error_returns_false(self):
        """On HTTP error, return False (best-effort)."""
        validator = PlanValidator()

        with patch("src.pipeline.plan.plan_validator.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = Exception("network down")
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await validator._check_property_exists("someProp")
            assert result is False

    @pytest.mark.asyncio
    async def test_cache_is_used_on_second_call(self):
        """A second call for the same property should hit the cache, not HTTP."""
        validator = PlanValidator()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"dcid:cachedProp": {"arcs": {}}}
        }

        with patch("src.pipeline.plan.plan_validator.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # First call -- hits API
            result1 = await validator._check_property_exists("cachedProp")
            assert result1 is True

            # Second call -- should NOT trigger another HTTP call
            result2 = await validator._check_property_exists("cachedProp")
            assert result2 is True

            # get should only have been called once (first call)
            assert mock_client_instance.get.call_count == 1


class TestValidateCandidate:
    """Unit tests for _validate_candidate."""

    @pytest.mark.asyncio
    async def test_valid_property_marked_true(self):
        """A candidate with a valid property gets property_exists=True."""
        validator = PlanValidator()

        with patch.object(validator, "_check_property_exists", return_value=True):
            cand = _make_candidate(prop="measuredProperty")
            result = await validator._validate_candidate(cand)

            assert isinstance(result, CandidateValidation)
            assert result.property_exists is True
            assert result.notes == ""

    @pytest.mark.asyncio
    async def test_invalid_property_marked_false(self):
        """A candidate with an invalid property gets property_exists=False."""
        validator = PlanValidator()

        with patch.object(validator, "_check_property_exists", return_value=False):
            cand = _make_candidate(prop="totallyFakeProp")
            result = await validator._validate_candidate(cand)

            assert isinstance(result, CandidateValidation)
            assert result.property_exists is False
            assert "totallyFakeProp" in result.notes


class TestValidatePlan:
    """Integration-level tests for the full validate() method."""

    @pytest.mark.asyncio
    async def test_validate_plan_populates_validation_field(self):
        """All candidates should have a validation after validate()."""
        validator = PlanValidator()

        active_cands = [
            _make_candidate(prop="measuredProperty"),
            _make_candidate(prop="populationType"),
        ]
        static_cands = [
            _make_candidate(prop="unit"),
        ]
        plan = _make_plan(
            active_candidates=active_cands,
            static_candidates=static_cands,
        )

        with patch.object(
            validator,
            "_check_property_exists",
            return_value=True,
        ):
            result = await validator.validate(plan)

        # Every candidate should now have a validation object.
        for col in result.active_columns:
            for cand in col.candidates:
                assert cand.validation is not None
                assert cand.validation.property_exists is True

        for sp in result.static_properties:
            for cand in sp.candidates:
                assert cand.validation is not None
                assert cand.validation.property_exists is True

    @pytest.mark.asyncio
    async def test_api_failure_degrades_gracefully(self):
        """If _check_property_exists raises, the plan is still returned."""
        validator = PlanValidator()

        cand = _make_candidate(prop="flakyProp")
        plan = _make_plan(active_candidates=[cand])

        with patch.object(
            validator,
            "_check_property_exists",
            side_effect=RuntimeError("boom"),
        ):
            result = await validator.validate(plan)

        # Plan is returned, candidate has a validation with error note.
        assert result is plan
        validation = result.active_columns[0].candidates[0].validation
        assert validation is not None
        assert validation.property_exists is False
        assert "not found" in validation.notes

    @pytest.mark.asyncio
    async def test_empty_plan_returns_unchanged(self):
        """A plan with no candidates is returned immediately."""
        validator = PlanValidator()
        plan = _make_plan()

        result = await validator.validate(plan)
        assert result is plan

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid(self):
        """Plan with a mix of valid and invalid properties."""
        validator = PlanValidator()

        async def mock_check(prop: str) -> bool:
            return prop in WELL_KNOWN_PROPERTIES

        active_cands = [
            _make_candidate(prop="measuredProperty"),  # well-known -> True
            _make_candidate(prop="totallyFakeProp"),    # unknown -> False
        ]
        plan = _make_plan(active_candidates=active_cands)

        with patch.object(validator, "_check_property_exists", side_effect=mock_check):
            result = await validator.validate(plan)

        validations = [c.validation for c in result.active_columns[0].candidates]
        assert validations[0].property_exists is True
        assert validations[1].property_exists is False
