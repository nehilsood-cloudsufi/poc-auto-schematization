"""Tests for feedback_enforcement module.

Covers enforce_pinned_row, enforce_mapping, and apply_enforcement functions.
These are pure functions — no ADK, no mocking needed.
"""
import pytest

from src.agents.feedback_enforcement import (
    enforce_mapping,
    enforce_pinned_row,
    apply_enforcement,
)
from src.api.models.feedback import (
    FeedbackEntry,
    FeedbackLedger,
    FeedbackType,
)

# ---------------------------------------------------------------------------
# Sample PVMAPs used across tests
# ---------------------------------------------------------------------------

SIMPLE_PVMAP = """\
key,property1,value1,property2,value2
Year,observationDate,{Data},,
REF_AREA,observationAbout,{Data},,
Population,populationType,Person,measuredProperty,count,value,{Number}\
"""

# Same content, no trailing newline — enforce functions should be idempotent
SIMPLE_PVMAP_NO_TRAILING = SIMPLE_PVMAP.rstrip("\n")


# ===========================================================================
# enforce_pinned_row
# ===========================================================================


class TestEnforcePinnedRow:
    """enforce_pinned_row(pvmap_csv, target_key, pinned_content) -> (csv, changed)"""

    # -----------------------------------------------------------------------
    # Replace existing row
    # -----------------------------------------------------------------------

    def test_replaces_existing_row(self):
        pinned = "Year,observationDate,{Data},unit,Percent"
        new_pvmap, changed = enforce_pinned_row(SIMPLE_PVMAP, "Year", pinned)

        assert changed is True
        lines = [l for l in new_pvmap.splitlines() if l.strip()]
        year_lines = [l for l in lines if l.startswith("Year,")]
        assert len(year_lines) == 1
        assert year_lines[0] == pinned

    def test_replace_preserves_other_rows(self):
        pinned = "Year,observationDate,{Data},unit,Percent"
        new_pvmap, _ = enforce_pinned_row(SIMPLE_PVMAP, "Year", pinned)

        assert "REF_AREA,observationAbout,{Data}" in new_pvmap
        assert "Population,populationType,Person" in new_pvmap

    def test_replaces_middle_row(self):
        pinned = "REF_AREA,observationAbout,dcid:country/IND"
        new_pvmap, changed = enforce_pinned_row(SIMPLE_PVMAP, "REF_AREA", pinned)

        assert changed is True
        assert "REF_AREA,observationAbout,dcid:country/IND" in new_pvmap
        # Old mapping gone
        assert "REF_AREA,observationAbout,{Data}" not in new_pvmap

    def test_replaces_last_row(self):
        pinned = "Population,populationType,MedicalCondition,measuredProperty,count,value,{Number}"
        new_pvmap, changed = enforce_pinned_row(SIMPLE_PVMAP, "Population", pinned)

        assert changed is True
        assert "Population,populationType,MedicalCondition" in new_pvmap
        assert "Population,populationType,Person" not in new_pvmap

    # -----------------------------------------------------------------------
    # Append when key not found
    # -----------------------------------------------------------------------

    def test_appends_when_key_not_found(self):
        pinned = "Country,observationAbout,dcid:country/{Data}"
        new_pvmap, changed = enforce_pinned_row(SIMPLE_PVMAP, "Country", pinned)

        assert changed is True
        assert pinned in new_pvmap
        # Original rows untouched
        assert "Year,observationDate,{Data}" in new_pvmap
        assert "REF_AREA,observationAbout,{Data}" in new_pvmap

    def test_append_adds_exactly_one_row(self):
        pinned = "NewCol,measuredProperty,count"
        original_lines = [l for l in SIMPLE_PVMAP.splitlines() if l.strip()]
        new_pvmap, _ = enforce_pinned_row(SIMPLE_PVMAP, "NewCol", pinned)
        new_lines = [l for l in new_pvmap.splitlines() if l.strip()]

        assert len(new_lines) == len(original_lines) + 1

    # -----------------------------------------------------------------------
    # No-change when already correct
    # -----------------------------------------------------------------------

    def test_no_change_when_already_correct(self):
        # Use the exact existing content of the Year row
        existing_row = "Year,observationDate,{Data},,"
        new_pvmap, changed = enforce_pinned_row(SIMPLE_PVMAP, "Year", existing_row)

        assert changed is False
        assert new_pvmap == SIMPLE_PVMAP

    def test_no_change_returns_original_object(self):
        """When unchanged, returned string should equal the input."""
        existing_row = "Year,observationDate,{Data},,"
        new_pvmap, changed = enforce_pinned_row(SIMPLE_PVMAP, "Year", existing_row)

        assert new_pvmap == SIMPLE_PVMAP

    # -----------------------------------------------------------------------
    # Edge cases
    # -----------------------------------------------------------------------

    def test_key_matched_by_first_column_only(self):
        """A key that appears inside a later column must NOT trigger replacement."""
        # 'Person' appears inside the Population row but is not a key
        pinned = "Person,measuredProperty,count"
        new_pvmap, changed = enforce_pinned_row(SIMPLE_PVMAP, "Person", pinned)

        # Key not found → append
        assert changed is True
        assert "Person,measuredProperty,count" in new_pvmap
        # Original Population row still intact
        assert "Population,populationType,Person" in new_pvmap

    def test_empty_pvmap_appends_row(self):
        pinned = "Year,observationDate,{Data}"
        new_pvmap, changed = enforce_pinned_row("", "Year", pinned)

        assert changed is True
        assert "Year,observationDate,{Data}" in new_pvmap

    def test_header_only_pvmap_appends_row(self):
        header_only = "key,property1,value1"
        pinned = "Year,observationDate,{Data}"
        new_pvmap, changed = enforce_pinned_row(header_only, "Year", pinned)

        assert changed is True
        assert "Year,observationDate,{Data}" in new_pvmap
        assert "key,property1,value1" in new_pvmap


# ===========================================================================
# enforce_mapping
# ===========================================================================


class TestEnforceMapping:
    """enforce_mapping(pvmap_csv, target_column, mapping_content) -> (csv, changed)"""

    # -----------------------------------------------------------------------
    # Overwrite property mapping for existing row
    # -----------------------------------------------------------------------

    def test_overwrites_existing_mapping(self):
        new_pvmap, changed = enforce_mapping(
            SIMPLE_PVMAP, "Year", "observationDate,{Data},unit,Year"
        )

        assert changed is True
        lines = [l for l in new_pvmap.splitlines() if l.strip()]
        year_lines = [l for l in lines if l.startswith("Year,")]
        assert len(year_lines) == 1
        assert year_lines[0] == "Year,observationDate,{Data},unit,Year"

    def test_overwrite_preserves_other_rows(self):
        new_pvmap, _ = enforce_mapping(
            SIMPLE_PVMAP, "Year", "observationDate,2020"
        )
        assert "REF_AREA,observationAbout,{Data}" in new_pvmap
        assert "Population,populationType,Person" in new_pvmap

    def test_overwrites_population_row(self):
        new_pvmap, changed = enforce_mapping(
            SIMPLE_PVMAP,
            "Population",
            "populationType,HouseholdWorker,measuredProperty,count,value,{Number}",
        )

        assert changed is True
        assert "Population,populationType,HouseholdWorker" in new_pvmap
        # Old mapping replaced
        assert "Population,populationType,Person" not in new_pvmap

    # -----------------------------------------------------------------------
    # Create new row when column not mapped
    # -----------------------------------------------------------------------

    def test_creates_new_row_when_missing(self):
        new_pvmap, changed = enforce_mapping(
            SIMPLE_PVMAP, "Country", "observationAbout,dcid:country/{Data}"
        )

        assert changed is True
        assert "Country,observationAbout,dcid:country/{Data}" in new_pvmap

    def test_new_row_does_not_duplicate(self):
        new_pvmap, _ = enforce_mapping(
            SIMPLE_PVMAP, "Country", "observationAbout,dcid:country/{Data}"
        )
        country_lines = [l for l in new_pvmap.splitlines() if l.startswith("Country,")]
        assert len(country_lines) == 1

    # -----------------------------------------------------------------------
    # No change when already correct
    # -----------------------------------------------------------------------

    def test_no_change_when_already_correct(self):
        # Determine exact content of REF_AREA row minus "REF_AREA,"
        ref_area_row = "REF_AREA,observationAbout,{Data},,"
        # mapping_content is everything after "REF_AREA,"
        mapping_content = ref_area_row[len("REF_AREA,"):]
        new_pvmap, changed = enforce_mapping(SIMPLE_PVMAP, "REF_AREA", mapping_content)

        assert changed is False
        assert new_pvmap == SIMPLE_PVMAP

    def test_no_change_returns_original_string(self):
        ref_area_row_content = "observationAbout,{Data},,"
        new_pvmap, changed = enforce_mapping(SIMPLE_PVMAP, "REF_AREA", ref_area_row_content)

        assert changed is False
        assert new_pvmap == SIMPLE_PVMAP

    # -----------------------------------------------------------------------
    # Edge cases
    # -----------------------------------------------------------------------

    def test_target_matched_by_first_column_only(self):
        """'Person' is a value in Population row, not a key — should create new row."""
        new_pvmap, changed = enforce_mapping(SIMPLE_PVMAP, "Person", "populationType,Animal")

        assert changed is True
        assert "Person,populationType,Animal" in new_pvmap
        # Original Population row intact
        assert "Population,populationType,Person" in new_pvmap

    def test_empty_pvmap_creates_row(self):
        new_pvmap, changed = enforce_mapping("", "Year", "observationDate,{Data}")

        assert changed is True
        assert "Year,observationDate,{Data}" in new_pvmap

    def test_result_row_format(self):
        """Result row must be '{target_column},{mapping_content}'."""
        new_pvmap, _ = enforce_mapping(
            SIMPLE_PVMAP, "Year", "observationDate,{Data},unit,Years"
        )
        assert "Year,observationDate,{Data},unit,Years" in new_pvmap


# ===========================================================================
# apply_enforcement
# ===========================================================================


def _make_entry(
    feedback_type: FeedbackType,
    content: str,
    target: str | None = None,
    source: str = "human",
    round_: int = 1,
) -> FeedbackEntry:
    return FeedbackEntry(
        type=feedback_type,
        round=round_,
        source=source,
        content=content,
        target=target,
    )


class TestApplyEnforcement:
    """apply_enforcement(pvmap_csv, ledger) -> (enforced_csv, change_list)"""

    # -----------------------------------------------------------------------
    # Only human entries enforced
    # -----------------------------------------------------------------------

    def test_auto_entries_skipped(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.AUTO, "Year,observationDate,hardcoded_2020",
            target="Year", source="auto",
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        # No structural change — auto entry ignored
        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    def test_retracted_human_entry_skipped(self):
        ledger = FeedbackLedger()
        entry = _make_entry(
            FeedbackType.PIN_ROW, "Year,observationDate,hardcoded_2020", target="Year"
        )
        ledger.add_entry(entry)
        ledger.retract(entry.id)

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    def test_superseded_human_entry_skipped(self):
        """Superseded entries should not be enforced."""
        ledger = FeedbackLedger()
        old_entry = _make_entry(
            FeedbackType.PIN_ROW, "Year,observationDate,{Data}", target="Year"
        )
        ledger.add_entry(old_entry)
        # Adding another entry with same target supersedes the first
        ledger.add_entry(_make_entry(
            FeedbackType.PIN_ROW, "Year,observationDate,{Data},unit,Percent", target="Year"
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        # Only the second (non-superseded) entry enforced
        assert changes  # at least one change
        year_lines = [l for l in new_pvmap.splitlines() if l.startswith("Year,")]
        assert len(year_lines) == 1
        assert "unit,Percent" in year_lines[0]

    # -----------------------------------------------------------------------
    # APPLY_RULE entries NOT enforced
    # -----------------------------------------------------------------------

    def test_apply_rule_not_enforced(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.APPLY_RULE, "Always use {Data} for string columns", target="Year"
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    # -----------------------------------------------------------------------
    # FREE_TEXT entries NOT enforced
    # -----------------------------------------------------------------------

    def test_free_text_not_enforced(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.FREE_TEXT, "Please fix the Year column mapping"
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    # -----------------------------------------------------------------------
    # PIN_ROW enforcement
    # -----------------------------------------------------------------------

    def test_pin_row_enforced(self):
        pinned = "Year,observationDate,{Data},unit,Percent"
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.PIN_ROW, pinned, target="Year"
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert len(changes) == 1
        assert "Year" in changes[0]
        assert "Year,observationDate,{Data},unit,Percent" in new_pvmap

    def test_pin_row_without_target_skipped(self):
        """PIN_ROW with no target cannot be matched — skip silently."""
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.PIN_ROW, "Year,observationDate,{Data}", target=None
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    # -----------------------------------------------------------------------
    # SET_MAPPING enforcement
    # -----------------------------------------------------------------------

    def test_set_mapping_enforced(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.SET_MAPPING, "observationDate,{Data},unit,Year",
            target="Year"
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert len(changes) == 1
        assert "Year" in changes[0]
        year_lines = [l for l in new_pvmap.splitlines() if l.startswith("Year,")]
        assert year_lines[0] == "Year,observationDate,{Data},unit,Year"

    def test_set_mapping_without_target_skipped(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.SET_MAPPING, "observationDate,{Data}", target=None
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    # -----------------------------------------------------------------------
    # Multiple entries applied in sequence
    # -----------------------------------------------------------------------

    def test_multiple_entries_applied_in_sequence(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.PIN_ROW, "Year,observationDate,{Data},unit,Percent",
            target="Year"
        ))
        ledger.add_entry(_make_entry(
            FeedbackType.SET_MAPPING, "observationAbout,dcid:country/{Data}",
            target="REF_AREA"
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert len(changes) == 2
        assert "Year,observationDate,{Data},unit,Percent" in new_pvmap
        assert "REF_AREA,observationAbout,dcid:country/{Data}" in new_pvmap

    def test_multiple_entries_change_list_length(self):
        ledger = FeedbackLedger()
        for i in range(3):
            ledger.add_entry(_make_entry(
                FeedbackType.SET_MAPPING, f"measuredProperty,col{i}",
                target=f"Col{i}"
            ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        # All 3 columns were missing → all appended → 3 changes
        assert len(changes) == 3
        for i in range(3):
            assert f"Col{i},measuredProperty,col{i}" in new_pvmap

    # -----------------------------------------------------------------------
    # Empty ledger produces no changes
    # -----------------------------------------------------------------------

    def test_empty_ledger_no_changes(self):
        ledger = FeedbackLedger()
        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    # -----------------------------------------------------------------------
    # Mixed entry types — only PIN_ROW and SET_MAPPING enforced
    # -----------------------------------------------------------------------

    def test_mixed_types_only_structural_enforced(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.FREE_TEXT, "Please keep the Year mapping"
        ))
        ledger.add_entry(_make_entry(
            FeedbackType.APPLY_RULE, "Always use wikidataId for places", target="REF_AREA"
        ))
        ledger.add_entry(_make_entry(
            FeedbackType.PIN_ROW, "Year,observationDate,{Data},unit,Percent",
            target="Year"
        ))
        ledger.add_entry(_make_entry(
            FeedbackType.AUTO, "Validation error on Year", target="Year", source="auto"
        ))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        # Only the PIN_ROW is enforced
        assert len(changes) == 1
        assert "Year,observationDate,{Data},unit,Percent" in new_pvmap

    # -----------------------------------------------------------------------
    # No-change entries not listed in changes
    # -----------------------------------------------------------------------

    def test_no_change_entry_not_in_changes(self):
        """When pinned content already matches, no change entry returned."""
        # Content that exactly matches the existing row
        existing = "Year,observationDate,{Data},,"
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(FeedbackType.PIN_ROW, existing, target="Year"))

        new_pvmap, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert new_pvmap == SIMPLE_PVMAP
        assert changes == []

    # -----------------------------------------------------------------------
    # Return types
    # -----------------------------------------------------------------------

    def test_returns_tuple(self):
        ledger = FeedbackLedger()
        result = apply_enforcement(SIMPLE_PVMAP, ledger)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_changes_is_list_of_strings(self):
        ledger = FeedbackLedger()
        ledger.add_entry(_make_entry(
            FeedbackType.PIN_ROW, "Year,observationDate,{Data},unit,Percent",
            target="Year"
        ))
        _, changes = apply_enforcement(SIMPLE_PVMAP, ledger)

        assert isinstance(changes, list)
        assert all(isinstance(c, str) for c in changes)
