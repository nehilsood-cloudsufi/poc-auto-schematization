import pytest
from src.pipeline.validation.pvmap_repair import strip_ignore_rows


def test_strip_ignore_rows_removes_ignore():
    pvmap = """key,property,value
Year,observationDate,{Number}
CountryCode,#ignore,
Country,#ignore,skip
Value,value,{Number}"""
    result, changes = strip_ignore_rows(pvmap)
    assert "#ignore" not in result
    assert "Year,observationDate,{Number}" in result
    assert "Value,value,{Number}" in result
    assert len(changes) == 2


def test_strip_ignore_rows_no_changes():
    pvmap = """key,property,value
Year,observationDate,{Number}
Value,value,{Number}"""
    result, changes = strip_ignore_rows(pvmap)
    assert result == pvmap
    assert len(changes) == 0


def test_strip_ignore_rows_preserves_column_value_mappings():
    pvmap = """key,property,value
Year,observationDate,{Number}
CountryCode,#ignore,
CountryCode:356,observationAbout,country/IND
Value,value,{Number}"""
    result, changes = strip_ignore_rows(pvmap)
    assert "CountryCode,#ignore" not in result
    assert "CountryCode:356,observationAbout,country/IND" in result
    assert len(changes) == 1
