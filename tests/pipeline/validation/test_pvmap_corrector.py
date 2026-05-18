"""Tests for Tier 1 counter-driven PVMAP correction rule engine."""

import csv
import io
import pytest
from pathlib import Path
from unittest.mock import patch

from src.pipeline.validation.pvmap_corrector import (
    CorrectionRule,
    apply_correction_rules,
    _apply_key_mismatch,
    _apply_place_leading_zeros,
    _apply_place_prefix,
    _apply_duplicate_observations,
    _apply_missing_required_props,
    _apply_aggregate_invalid,
    _condition_key_mismatch,
    _condition_place_leading_zeros,
    _condition_place_prefix,
    _condition_duplicate_observations,
    _condition_missing_required_props,
    _condition_aggregate_invalid,
    _diagnostic_duplicate_observations,
    _build_rules,
    _parse_pvmap_rows,
    _rows_to_csv,
    _parse_unmatched_keys_from_report,
    _get_actual_headers,
)
from src.pipeline.validation.log_filter import FilteredLogs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logs(
    errors=None,
    error_examples=None,
    **kwargs,
) -> FilteredLogs:
    """Build a FilteredLogs with the given overrides."""
    return FilteredLogs(
        errors=errors or {},
        error_examples=error_examples or {},
        **kwargs,
    )


def _csv_str(*rows) -> str:
    """Build a CSV string from row tuples."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


# ===========================================================================
# TestCorrectionRule
# ===========================================================================

class TestCorrectionRule:
    """Tests for the CorrectionRule dataclass."""

    def test_rule_creation(self):
        rule = CorrectionRule(
            name='test_rule',
            error_type='error-test',
            priority=5,
            condition=lambda fl, ctx: True,
            apply=lambda csv, fl, ctx: csv,
        )
        assert rule.name == 'test_rule'
        assert rule.error_type == 'error-test'
        assert rule.priority == 5

    def test_condition_checking(self):
        rule = CorrectionRule(
            name='test_rule',
            error_type='error-test',
            priority=0,
            condition=lambda fl, ctx: ctx.get('fire', False),
            apply=lambda csv, fl, ctx: csv.upper(),
        )
        logs = _make_logs()
        assert rule.condition(logs, {'fire': True}) is True
        assert rule.condition(logs, {'fire': False}) is False

    def test_priority_ordering(self):
        rules = _build_rules()
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities), "Rules must be in priority order"
        assert rules[0].name == 'fix_key_mismatch'
        assert rules[-1].name == 'fix_aggregate_invalid'


# ===========================================================================
# TestFixKeyMismatch
# ===========================================================================

class TestFixKeyMismatch:
    """Tests for Rule 0: fix_key_mismatch."""

    def test_simple_key_replacement(self):
        pvmap = _csv_str(
            ['State Fips', 'observationAbout', 'dcid:geoId/{Data}'],
            ['Year', 'observationDate', '{Data}'],
        )
        logs = _make_logs(
            errors={'error-pvmap-dropped-undefined-property': 5},
            error_examples={'error-pvmap-dropped-undefined-property': [('State Fips', 5)]},
        )
        report = "Unmatched PVMAP keys: State Fips\nActual headers: ['State FIPS', 'Year', 'Value']"
        ctx = {'key_match_report': report, 'input_data_path': None}

        result = _apply_key_mismatch(pvmap, logs, ctx)
        rows = _parse_pvmap_rows(result)
        assert rows[0][0] == 'State FIPS'

    def test_fuzzy_match(self):
        pvmap = _csv_str(
            ['StateCode', 'observationAbout', 'dcid:geoId/{Data}'],
        )
        logs = _make_logs(
            errors={'error-pvmap-dropped-undefined-property': 3},
            error_examples={'error-pvmap-dropped-undefined-property': [('StateCode', 3)]},
        )
        report = "Unmatched PVMAP keys: StateCode\nActual headers: ['State_Code', 'Year']"
        ctx = {'key_match_report': report, 'input_data_path': None}

        result = _apply_key_mismatch(pvmap, logs, ctx)
        rows = _parse_pvmap_rows(result)
        assert rows[0][0] == 'State_Code'

    def test_column_value_syntax(self):
        pvmap = _csv_str(
            ['Mesure:GDP', 'measuredProperty', 'dcid:amount'],
        )
        logs = _make_logs(
            errors={'error-pvmap-dropped-undefined-property': 2},
            error_examples={'error-pvmap-dropped-undefined-property': [('Mesure:GDP', 2)]},
        )
        report = "Unmatched PVMAP keys: Mesure:GDP\nActual headers: ['Measure', 'Year', 'Value']"
        ctx = {'key_match_report': report, 'input_data_path': None}

        result = _apply_key_mismatch(pvmap, logs, ctx)
        rows = _parse_pvmap_rows(result)
        # Should replace column part (Mesure -> Measure) and keep :GDP
        assert rows[0][0] == 'Measure:GDP'

    def test_no_match_available(self):
        pvmap = _csv_str(
            ['XYZ_UNKNOWN', 'observationAbout', 'dcid:geoId/{Data}'],
        )
        logs = _make_logs(
            errors={'error-pvmap-dropped-undefined-property': 1},
            error_examples={'error-pvmap-dropped-undefined-property': [('XYZ_UNKNOWN', 1)]},
        )
        report = "Unmatched PVMAP keys: XYZ_UNKNOWN\nActual headers: ['State', 'Year']"
        ctx = {'key_match_report': report, 'input_data_path': None}

        result = _apply_key_mismatch(pvmap, logs, ctx)
        rows = _parse_pvmap_rows(result)
        # Should remain unchanged -- no close match
        assert rows[0][0] == 'XYZ_UNKNOWN'


# ===========================================================================
# TestFixPlaceLeadingZeros
# ===========================================================================

class TestFixPlaceLeadingZeros:
    """Tests for Rule 1: fix_place_leading_zeros."""

    def test_number_to_02d(self):
        pvmap = _csv_str(
            ['State FIPS', 'observationAbout', 'dcid:geoId/{Number}'],
            ['Year', 'observationDate', '{Data}'],
        )
        logs = _make_logs(
            errors={'error-unresolved-place': 10},
            error_examples={'error-unresolved-place': [
                ('6', 5), ('1', 3), ('4', 2),
            ]},
        )
        ctx = {'key_match_report': '', 'input_data_path': None}

        result = _apply_place_leading_zeros(pvmap, logs, ctx)
        assert '{Number:02d}' in result
        assert '{Number}' not in result

    def test_data_to_padded(self):
        pvmap = _csv_str(
            ['State FIPS', 'observationAbout', 'dcid:geoId/{Data}'],
        )
        logs = _make_logs(
            errors={'error-unresolved-place': 10},
            error_examples={'error-unresolved-place': [
                ('6', 5), ('1', 3), ('4', 2),
            ]},
        )
        ctx = {'key_match_report': '', 'input_data_path': None}

        result = _apply_place_leading_zeros(pvmap, logs, ctx)
        assert '{Data:0>2}' in result
        assert 'geoId/{Data}' not in result

    def test_no_place_errors(self):
        pvmap = _csv_str(
            ['State', 'observationAbout', 'dcid:geoId/{Data}'],
        )
        logs = _make_logs(errors={})
        ctx = {'key_match_report': '', 'input_data_path': None}

        assert _condition_place_leading_zeros(logs, ctx) is False


# ===========================================================================
# TestFixPlacePrefix
# ===========================================================================

class TestFixPlacePrefix:
    """Tests for Rule 2: fix_place_prefix."""

    def test_bare_fips_to_geoid(self):
        pvmap = _csv_str(
            ['State FIPS', 'observationAbout', 'dcid:{Data}'],
        )
        logs = _make_logs(
            errors={'error-unresolved-place': 8},
            error_examples={'error-unresolved-place': [
                ('06', 4), ('48', 4),
            ]},
        )
        ctx = {'key_match_report': '', 'input_data_path': None}

        result = _apply_place_prefix(pvmap, logs, ctx)
        assert 'geoId/{Data}' in result

    def test_already_prefixed(self):
        pvmap = _csv_str(
            ['State FIPS', 'observationAbout', 'dcid:geoId/{Data}'],
        )
        logs = _make_logs(
            errors={'error-unresolved-place': 8},
            error_examples={'error-unresolved-place': [
                ('06', 4), ('48', 4),
            ]},
        )
        ctx = {'key_match_report': '', 'input_data_path': None}

        result = _apply_place_prefix(pvmap, logs, ctx)
        # Should not double-prefix
        assert 'geoId/geoId/' not in result

    def test_country_codes_no_trigger(self):
        """Country ISO codes (US, IN) should not trigger bare FIPS condition."""
        logs = _make_logs(
            errors={'error-unresolved-place': 5},
            error_examples={'error-unresolved-place': [
                ('US', 3), ('IN', 2),
            ]},
        )
        ctx = {'key_match_report': '', 'input_data_path': None}

        # 'US' and 'IN' are not purely numeric -- condition should be False
        assert _condition_place_prefix(logs, ctx) is False


# ===========================================================================
# TestFixDuplicateObservations
# ===========================================================================

class TestFixDuplicateObservations:
    """Tests for Rule 3: fix_duplicate_observations (diagnostic only)."""

    def test_produces_diagnostic(self):
        logs = _make_logs(
            errors={'error-mismatched-svobs': 15},
            error_examples={'error-mismatched-svobs': [
                ('StatVar_Population', 10),
                ('StatVar_Income', 5),
            ]},
        )
        diag = _diagnostic_duplicate_observations(logs)
        assert '15 duplicate' in diag
        assert 'StatVar_Population' in diag
        assert 'qualifier' in diag.lower()

    def test_no_duplicates(self):
        logs = _make_logs(errors={})
        assert _condition_duplicate_observations(logs, {}) is False


# ===========================================================================
# TestFixMissingRequiredProps
# ===========================================================================

class TestFixMissingRequiredProps:
    """Tests for Rule 4: fix_missing_required_props."""

    def test_fixes_odd_cell_count(self):
        # Row with odd number of cells after key (missing value in a pair)
        pvmap = _csv_str(
            ['Year', 'observationDate', '{Data}', 'extra_prop'],
        )
        logs = _make_logs(errors={'error-svobs-missing-property': 5})
        ctx = {}

        result = _apply_missing_required_props(pvmap, logs, ctx)
        rows = _parse_pvmap_rows(result)
        # Should have added an empty cell to make pairs even
        data_cells = rows[0][1:]
        assert len(data_cells) % 2 == 0

    def test_no_change_when_even(self):
        pvmap = _csv_str(
            ['Year', 'observationDate', '{Data}'],
        )
        logs = _make_logs(errors={'error-svobs-missing-property': 2})
        ctx = {}

        result = _apply_missing_required_props(pvmap, logs, ctx)
        assert result == pvmap  # No structural issue found


# ===========================================================================
# TestFixAggregateInvalid
# ===========================================================================

class TestFixAggregateInvalid:
    """Tests for Rule 5: fix_aggregate_invalid."""

    def test_number_to_data_swap(self):
        pvmap = _csv_str(
            ['Category', 'measuredProperty', 'dcid:count', 'value', '{Number}'],
        )
        logs = _make_logs(
            errors={'error-aggregate-invalid-values': 10},
            error_examples={'error-aggregate-invalid-values': [
                ('Category', 10),
            ]},
        )
        ctx = {}

        result = _apply_aggregate_invalid(pvmap, logs, ctx)
        rows = _parse_pvmap_rows(result)
        assert '{Data}' in rows[0]
        assert '{Number}' not in rows[0]

    def test_already_correct(self):
        pvmap = _csv_str(
            ['Amount', 'value', '{Number}'],
        )
        logs = _make_logs(
            errors={'error-aggregate-invalid-values': 3},
            error_examples={'error-aggregate-invalid-values': [
                ('OtherColumn', 3),
            ]},
        )
        ctx = {}

        result = _apply_aggregate_invalid(pvmap, logs, ctx)
        # Amount doesn't match OtherColumn, so no change
        assert result == pvmap


# ===========================================================================
# TestApplyCorrectionRules
# ===========================================================================

class TestApplyCorrectionRules:
    """Integration tests for apply_correction_rules."""

    def test_multiple_rules_apply(self):
        pvmap = _csv_str(
            ['State Fips', 'observationAbout', 'dcid:geoId/{Data}'],
            ['Year', 'observationDate', '{Data}'],
            ['Population', 'value', '{Number}'],
        )
        logs = _make_logs(
            errors={
                'error-pvmap-dropped-undefined-property': 5,
                'error-mismatched-svobs': 10,
            },
            error_examples={
                'error-pvmap-dropped-undefined-property': [('State Fips', 5)],
                'error-mismatched-svobs': [('SV_Pop', 10)],
            },
        )
        report = "Unmatched PVMAP keys: State Fips\nActual headers: ['State FIPS', 'Year', 'Population']"

        result, changes = apply_correction_rules(
            pvmap, logs, report, input_data_path=None,
        )

        # At least key mismatch and duplicate diagnostic should fire
        rule_names = [c.split(']')[0].lstrip('[') for c in changes]
        assert 'fix_key_mismatch' in rule_names
        assert 'fix_duplicate_observations' in rule_names
        # Key should be corrected
        rows = _parse_pvmap_rows(result)
        assert rows[0][0] == 'State FIPS'

    def test_no_rules_match(self):
        pvmap = _csv_str(
            ['Year', 'observationDate', '{Data}'],
        )
        logs = _make_logs(errors={})
        result, changes = apply_correction_rules(pvmap, logs, '', None)
        assert result == pvmap
        assert changes == []

    def test_priority_ordering(self):
        """Rules with lower priority number should fire first."""
        pvmap = _csv_str(
            ['State Fips', 'observationAbout', 'dcid:{Data}'],
            ['Year', 'observationDate', '{Data}'],
        )
        logs = _make_logs(
            errors={
                'error-pvmap-dropped-undefined-property': 5,
                'error-unresolved-place': 8,
            },
            error_examples={
                'error-pvmap-dropped-undefined-property': [('State Fips', 5)],
                'error-unresolved-place': [('06', 4), ('48', 4)],
            },
        )
        report = "Unmatched PVMAP keys: State Fips\nActual headers: ['State FIPS', 'Year']"

        _result, changes = apply_correction_rules(
            pvmap, logs, report, input_data_path=None,
        )

        # Key mismatch (priority 0) should appear before place prefix (priority 2)
        rule_names = [c.split(']')[0].lstrip('[') for c in changes]
        if 'fix_key_mismatch' in rule_names and 'fix_place_prefix' in rule_names:
            assert rule_names.index('fix_key_mismatch') < rule_names.index('fix_place_prefix')
