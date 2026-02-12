"""
Tests for #Eval syntax validation in pvmap_repair.py.

Verifies that _validate_eval_syntax() detects common #Eval issues:
- f-strings
- Nested double quotes
- Lambda expressions
- Import statements
- Python syntax errors
- Integration with pre_validate_pvmap()
"""

import pytest
from pathlib import Path

from src.pipeline.validation.pvmap_repair import (
    _validate_eval_syntax,
    pre_validate_pvmap,
)


# ============================================================================
# Test _validate_eval_syntax directly
# ============================================================================


class TestValidExpressionsNoWarnings:
    """Valid #Eval expressions should produce no warnings."""

    def test_simple_arithmetic(self):
        pvmap = (
            "key,property,value\n"
            "Year,observationDate,{Data}\n"
            'Population,value,{Number},#Eval,"int(\'{Data}\'.replace(\',\',\'\'))"\n'
        )
        warnings = _validate_eval_syntax(pvmap)
        assert warnings == []

    def test_split_expression(self):
        pvmap = (
            "key,property,value\n"
            "fiscal_year,#Eval,\"observationDate='{Data}'.split('-')[1]\",observationPeriod,P1Y\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert warnings == []

    def test_conditional_expression(self):
        pvmap = (
            "key,property,value\n"
            "Status,#Eval,\"active='Yes' if '{Data}' == 'Y' else 'No'\"\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert warnings == []

    def test_assignment_expression(self):
        pvmap = (
            "key,property,value\n"
            "Year,#Eval,\"Year1=int('{Year}'.split('-')[0])\",observationDate,{Year1}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert warnings == []


class TestFstringDetected:
    """f-strings in #Eval expressions should be detected."""

    def test_fstring_single_quote(self):
        # f'FY{Year}' in a properly CSV-quoted field
        pvmap = (
            "key,property,value\n"
            "Year,#Eval,\"f'FY{Year}'\",observationDate,{Data}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert any("f-string" in w for w in warnings)

    def test_fstring_with_format(self):
        # f-string with format specifier
        pvmap = (
            "key,property,value\n"
            "Year,#Eval,\"f'{Year:04d}'\",observationDate,{Data}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert any("f-string" in w for w in warnings)


class TestNestedDoubleQuotesDetected:
    """Nested double quotes in #Eval should be detected."""

    def test_nested_quotes(self):
        # Simulate an expression that has nested double quotes after CSV parsing
        pvmap = (
            'key,property,value\n'
            'Year,#Eval,"val=\"test\"",observationDate,{Data}\n'
        )
        warnings = _validate_eval_syntax(pvmap)
        # The CSV parser will handle the escaping, but if there are 2+ "
        # in the parsed expression, warn
        has_nested_warning = any("Nested double quotes" in w or "Syntax error" in w for w in warnings)
        assert has_nested_warning


class TestLambdaDetected:
    """Lambda expressions in #Eval should be detected."""

    def test_lambda_expression(self):
        pvmap = (
            "key,property,value\n"
            "Year,#Eval,\"lambda x: x.split('-')[0]\",observationDate,{Data}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert any("lambda" in w for w in warnings)


class TestImportDetected:
    """Import statements in #Eval should be detected."""

    def test_import_statement(self):
        pvmap = (
            "key,property,value\n"
            "Year,#Eval,\"import datetime; datetime.date.today()\",observationDate,{Data}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert any("import" in w for w in warnings)


class TestSyntaxErrorDetected:
    """Unparseable expressions should be detected."""

    def test_syntax_error(self):
        pvmap = (
            "key,property,value\n"
            "Year,#Eval,\"int('{Data}'.split('-')[0]\",observationDate,{Data}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert any("Syntax error" in w for w in warnings)

    def test_unclosed_bracket(self):
        pvmap = (
            "key,property,value\n"
            "Year,#Eval,\"'{Data}'.replace('[', ''\",observationDate,{Data}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert any("Syntax error" in w or "EVAL WARNING" in w for w in warnings)


class TestNoEvalRowsNoWarnings:
    """PVMAPs without #Eval should produce no warnings."""

    def test_no_eval_rows(self):
        pvmap = (
            "key,property,value\n"
            "Year,observationDate,{Data}\n"
            "State,observationAbout,geoId/{Data}\n"
            "Population,populationType,Person,measuredProperty,count,value,{Number}\n"
        )
        warnings = _validate_eval_syntax(pvmap)
        assert warnings == []


class TestIntegratedInPreValidate:
    """pre_validate_pvmap() should include eval warnings."""

    def test_eval_warnings_in_pre_validate(self, tmp_path):
        # Create input data file
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("Year,State,Population\n2020,CA,100\n")

        pvmap = (
            "key,property,value\n"
            "Year,observationDate,{Data}\n"
            "State,observationAbout,geoId/{Data}\n"
            "Population,populationType,Person,measuredProperty,count,value,{Number},"
            "#Eval,\"f'FY{Year}'\"\n"
        )

        passes, errors = pre_validate_pvmap(pvmap, input_csv)
        # f-string warning should be in errors (as informational)
        assert any("f-string" in e for e in errors)


class TestWarningsDontAffectPassFail:
    """Eval warnings are informational only — they should not affect pass/fail."""

    def test_eval_warning_doesnt_fail_pre_validate(self, tmp_path):
        # Create input data file
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("Year,State,Population\n2020,CA,100\n")

        # This PVMAP has all required mappings (observationAbout, observationDate, value)
        # plus an #Eval with an f-string warning
        pvmap = (
            "key,property,value\n"
            "Year,observationDate,{Data}\n"
            "State,observationAbout,geoId/{Data}\n"
            "Population,populationType,Person,measuredProperty,count,value,{Number},"
            "#Eval,\"f'FY{Year}'\"\n"
        )

        passes, errors = pre_validate_pvmap(pvmap, input_csv)
        # Should still pass (eval warnings are informational)
        assert passes is True
        # But warnings should be present
        assert any("EVAL WARNING" in e for e in errors)
