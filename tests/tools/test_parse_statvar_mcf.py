import pytest
from tools.parse_statvar_mcf import parse_mcf_statvars, classify_statvar_category


def test_parse_single_statvar():
    mcf_text = """Node: dcid:Count_Person_16OrMoreYears_WhiteAlone
typeOf: dcid:StatisticalVariable
name: "Population: 16 Years or More,White Alone"
populationType: dcid:Person
measuredProperty: dcid:count
statType: dcid:measuredValue
race: dcid:WhiteAlone
age: dcid:Years16Onwards
"""
    result = parse_mcf_statvars(mcf_text)
    assert len(result) == 1
    sv = result[0]
    assert sv["dcid"] == "Count_Person_16OrMoreYears_WhiteAlone"
    assert sv["populationType"] == "dcs:Person"
    assert sv["measuredProperty"] == "dcs:count"
    assert sv["statType"] == "dcs:measuredValue"
    assert sv["race"] == "dcs:WhiteAlone"
    assert sv["age"] == "dcs:Years16Onwards"


def test_parse_multiple_statvars():
    mcf_text = """Node: dcid:Count_Person_Male
typeOf: dcid:StatisticalVariable
populationType: dcid:Person
measuredProperty: dcid:count
statType: dcid:measuredValue
gender: dcid:Male

Node: dcid:Exports_EconomicActivity_Unspecified
typeOf: dcid:StatisticalVariable
populationType: dcid:EconomicActivity
measuredProperty: dcid:exports
statType: dcid:measuredValue
product: dcid:Unspecified
"""
    result = parse_mcf_statvars(mcf_text)
    assert len(result) == 2
    assert result[0]["dcid"] == "Count_Person_Male"
    assert result[1]["populationType"] == "dcs:EconomicActivity"


def test_classify_demographics():
    sv = {"populationType": "dcs:Person", "race": "dcs:WhiteAlone", "age": "dcs:Years16Onwards"}
    assert classify_statvar_category(sv) == "Demographics"


def test_classify_economy():
    sv = {"populationType": "dcs:EconomicActivity", "measuredProperty": "dcs:exports"}
    assert classify_statvar_category(sv) == "Economy"


def test_classify_economy_establishment():
    sv = {"populationType": "dcs:Establishment", "measuredProperty": "dcs:count"}
    assert classify_statvar_category(sv) == "Economy"


def test_classify_education():
    sv = {"populationType": "dcs:Student", "measuredProperty": "dcs:assessmentScore"}
    assert classify_statvar_category(sv) == "Education"


def test_classify_health():
    sv = {"populationType": "dcs:MedicalConditionIncident", "measuredProperty": "dcs:count"}
    assert classify_statvar_category(sv) == "Health"


def test_dcid_prefix_normalization():
    """dcid: in MCF should be normalized to dcs: in output."""
    mcf_text = """Node: dcid:Count_Person
typeOf: dcid:StatisticalVariable
populationType: dcid:Person
measuredProperty: dcid:count
statType: dcid:measuredValue
"""
    result = parse_mcf_statvars(mcf_text)
    assert result[0]["populationType"] == "dcs:Person"
    assert result[0]["measuredProperty"] == "dcs:count"
