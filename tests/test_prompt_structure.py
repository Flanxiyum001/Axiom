"""Test that candidate prompt produces valid structured output."""
import json
import pytest

from axiom.benchmarks.inference_runner import _prompt_for
from axiom.benchmarks.loader import load_file
from pathlib import Path


def test_candidate_prompt_contains_required_instructions():
    """Ensure the candidate prompt includes arithmetic checking and JSON schema."""
    dataset = load_file(
        str(Path(__file__).parent.parent / "backend" / "axiom" / "benchmarks" / "datasets" / "nemotron_prompt_ab_v1.json")
    )
    case = dataset.cases[0]

    prompt = _prompt_for(case, "candidate")

    # Verify arithmetic checking is present
    assert "Check calculations" in prompt or "arithmetic" in prompt.lower() or "silently" in prompt

    # Verify JSON schema requirements
    assert "answer" in prompt
    assert "confidence" in prompt

    # Verify no redundant old instructions remain
    assert "Solve the task carefully" not in prompt
    assert "Keep the answer concise; do not show a derivation" not in prompt


def test_candidate_prompt_with_sample_case():
    """Test the candidate prompt works with an actual case."""
    dataset = load_file(
        str(Path(__file__).parent.parent / "backend" / "axiom" / "benchmarks" / "datasets" / "nemotron_prompt_ab_v1.json")
    )
    case = dataset.cases[0]

    prompt = _prompt_for(case, "candidate")

    # Parse the task from the prompt
    assert f"Task: {case.input}" in prompt

    # Verify the prompt is concise (not overly verbose)
    # The prompt should not contain the old verbose instructions
    old_phrases = [
        "Solve the task carefully and verify any arithmetic before answering.",
        "Keep the answer concise; do not show a derivation.",
    ]
    for phrase in old_phrases:
        assert phrase not in prompt, f"Old prompt phrase still present: {phrase}"