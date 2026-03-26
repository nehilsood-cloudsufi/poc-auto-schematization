import pytest
import inspect


def test_feedback_v1_template_exists():
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    assert (PROJECT_ROOT / "src" / "resources" / "prompts" / "feedback_agent.txt").exists()


def test_feedback_v2_template_exists():
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    assert (PROJECT_ROOT / "src" / "resources" / "prompts" / "feedback_agent_v2.txt").exists()


def test_feedback_v2_has_gt_placeholder():
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v2_text = (PROJECT_ROOT / "src" / "resources" / "prompts" / "feedback_agent_v2.txt").read_text()
    assert "{gt_feedback_section}" in v2_text


def test_feedback_v2_shorter_than_v1():
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    prompts = PROJECT_ROOT / "src" / "resources" / "prompts"
    v1_lines = len((prompts / "feedback_agent.txt").read_text().splitlines())
    v2_lines = len((prompts / "feedback_agent_v2.txt").read_text().splitlines())
    assert v2_lines < v1_lines * 0.6  # v2 should be <60% of v1


def test_feedback_v2_no_dropped_vars():
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v2_text = (PROJECT_ROOT / "src" / "resources" / "prompts" / "feedback_agent_v2.txt").read_text()
    for dropped in ["{sampled_data}", "{structure_warnings}", "{mcp_resolved_context}"]:
        assert dropped not in v2_text, f"Dropped variable {dropped} found in v2 prompt"


def test_run_dataset_pipeline_accepts_feedback_prompt_version():
    from src.run_pipeline import run_dataset_pipeline
    sig = inspect.signature(run_dataset_pipeline)
    assert "feedback_prompt_version" in sig.parameters
    assert sig.parameters["feedback_prompt_version"].default == "v1"


def test_quality_eval_has_column_coverage_threshold():
    from src.agents.quality_evaluation_agent import QualityEvaluationAgent
    assert hasattr(QualityEvaluationAgent, 'COLUMN_COVERAGE_THRESHOLD')
    assert QualityEvaluationAgent.COLUMN_COVERAGE_THRESHOLD == 80.0
