import json
import pytest
from pathlib import Path
from tools.parse_statvar_mcf import parse_mcf_file, group_by_category

MCF_PATH = Path("src/resources/schema_org/sample_statvars.mcf")


@pytest.mark.skipif(not MCF_PATH.exists(), reason="sample_statvars.mcf not present")
def test_parse_sample_statvars_mcf():
    statvars = parse_mcf_file(MCF_PATH)
    assert len(statvars) >= 50
    for sv in statvars:
        assert "dcid" in sv
        assert "populationType" in sv


@pytest.mark.skipif(not MCF_PATH.exists(), reason="sample_statvars.mcf not present")
def test_group_by_category():
    statvars = parse_mcf_file(MCF_PATH)
    groups = group_by_category(statvars)
    assert "Demographics" in groups
    assert "Education" in groups


@pytest.mark.skipif(not MCF_PATH.exists(), reason="sample_statvars.mcf not present")
def test_statvar_examples_in_vocab():
    from tools.build_schema_vocab import enrich_with_statvar_examples
    vocab = {"category": "Demographics", "stat_var_skeletons": {}, "property_vocabulary": {}, "examples": []}
    statvars = parse_mcf_file(MCF_PATH)
    groups = group_by_category(statvars)
    enriched = enrich_with_statvar_examples(vocab, groups.get("Demographics", []))
    assert "statvar_examples" in enriched
    assert len(enriched["statvar_examples"]) > 0
    assert len(enriched["statvar_examples"]) <= 15
    for ex in enriched["statvar_examples"]:
        assert "dcid" in ex
        assert "populationType" in ex
