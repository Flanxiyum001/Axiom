import time

"""Runner behavior: structured results, metadata, and graceful provider failures."""

import pytest
from pydantic import BaseModel, ValidationError

from axiom.domain.interfaces import ProviderError, ReasoningProvider
from axiom.domain.models import RunStatus
from axiom.experiments.runner import ExperimentRequest, ExperimentResult, ExperimentRunner


class SampleOutput(BaseModel):
    """Minimal provider output used to exercise runner genericity."""

    answer: str


class StubProvider(ReasoningProvider):
    """Configurable test double recording the request it receives."""

    name = "stub"

    def __init__(self, output=None, error=None, delay=0.0, model=None):
        """Configure the canned output, error, delay, and model name."""
        self.output = output
        self.error = error
        self.delay = delay
        self.model = model
        self.seen = {}

    def generate(self, *, system, prompt, context, output_type):
        """Record arguments, then return output, raise, or build a default."""
        self.seen = {"system": system, "prompt": prompt, "context": context, "output_type": output_type}
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        if self.output is not None:
            return self.output
        return output_type(answer="default")


def test_success_returns_structured_result():
    """A good provider call yields a COMPLETED result with metadata."""
    provider = StubProvider(output=SampleOutput(answer="42"))
    runner = ExperimentRunner(provider)
    result = runner.run(
        ExperimentRequest(system="sys", prompt="prompt", context={"k": "v"}),
        output_type=SampleOutput,
    )
    assert isinstance(result, ExperimentResult)
    assert result.status == RunStatus.COMPLETED
    assert result.output is not None
    assert result.output.answer == "42"
    assert result.error is None
    assert result.latency_ms >= 0.0
    assert result.provider == "stub"
    assert result.completed_at is not None
    assert result.started_at <= result.completed_at


def test_request_reaches_provider_unmodified():
    """System, prompt, context, and output type pass through verbatim."""
    provider = StubProvider()
    ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p", context={"a": "b"}),
        output_type=SampleOutput,
    )
    assert provider.seen["system"] == "s"
    assert provider.seen["prompt"] == "p"
    assert provider.seen["context"] == {"a": "b"}
    assert provider.seen["output_type"] is SampleOutput


def test_request_context_defaults_empty():
    """Context is optional and defaults to an empty mapping."""
    assert ExperimentRequest(system="s", prompt="p").context == {}


def test_provider_error_becomes_failed_result():
    """ProviderError yields FAILED carrying the provider message."""
    provider = StubProvider(error=ProviderError("bad key"))
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.FAILED
    assert result.output is None
    assert result.error is not None
    assert "bad key" in result.error
    assert result.provider == "stub"
    assert result.completed_at is not None


def test_unexpected_error_does_not_raise():
    """Non-provider exceptions also yield FAILED instead of propagating."""
    provider = StubProvider(error=RuntimeError("connection reset"))
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.FAILED
    assert result.output is None
    assert result.error is not None
    assert "RuntimeError" in result.error


def test_latency_measures_provider_time():
    """Reported latency covers the provider call, not just overhead."""
    provider = StubProvider(delay=0.05)
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.COMPLETED
    assert result.latency_ms >= 40.0


def test_model_recorded_when_provider_exposes_it():
    """A string model attribute on the provider is captured in metadata."""
    provider = StubProvider(model="nemotron-test")
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.model == "nemotron-test"


def test_model_and_tokens_default_none():
    """Model and usage stay None until a provider reports them."""
    provider = StubProvider()
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.model is None
    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert result.total_tokens is None


def test_runner_is_generic_over_output_type():
    """The runner works with any validated output schema, not one benchmark."""
    from axiom.providers.schemas import PlanOutput

    provider = StubProvider()
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=PlanOutput,
    )
    assert result.status == RunStatus.COMPLETED
    assert isinstance(result.output, PlanOutput)


def test_garbage_output_becomes_failed_result():
    """Output failing schema validation yields FAILED instead of passing through."""
    provider = StubProvider(output={"not": "a model"})
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.FAILED
    assert result.output is None
    assert result.error is not None


def test_none_output_becomes_failed_result():
    """A provider returning None is a contract violation, reported as FAILED."""
    class NoneProvider(ReasoningProvider):
        """Test double violating the generate contract by returning None."""

        name = "none"

        def generate(self, *, system, prompt, context, output_type):
            """Return None instead of the required validated model."""
            return None

    result = ExperimentRunner(NoneProvider()).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.FAILED
    assert result.output is None
    assert result.error is not None
    assert "no output" in result.error


def test_empty_prompt_still_runs():
    """Empty prompts are accepted and flow to the provider unchanged."""
    provider = StubProvider()
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt=""),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.COMPLETED
    assert provider.seen["prompt"] == ""


def test_missing_required_fields_rejected():
    """Requests without system and prompt fail validation naming the field."""
    with pytest.raises(ValidationError) as system_missing:
        ExperimentRequest(prompt="p")
    assert "system" in {error["loc"][0] for error in system_missing.value.errors()}
    with pytest.raises(ValidationError) as prompt_missing:
        ExperimentRequest(system="s")
    assert "prompt" in {error["loc"][0] for error in prompt_missing.value.errors()}


def test_slow_provider_reports_measured_latency():
    """A sluggish provider still completes with honestly measured latency."""
    provider = StubProvider(delay=0.01)
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.COMPLETED
    assert result.latency_ms >= 5.0


def test_multiple_sequential_runs_stay_independent():
    """Consecutive runs return distinct results echoing each request."""
    class EchoingProvider(ReasoningProvider):
        """Test double answering with the incoming prompt."""

        name = "echoing"

        def generate(self, *, system, prompt, context, output_type):
            """Return the prompt as the answer."""
            return SampleOutput(answer=prompt)

    runner = ExperimentRunner(EchoingProvider())
    results = [
        runner.run(ExperimentRequest(system="s", prompt=f"q{i}"), output_type=SampleOutput)
        for i in range(3)
    ]
    assert all(result.status == RunStatus.COMPLETED for result in results)
    assert [result.output.answer for result in results] == ["q0", "q1", "q2"]
    assert len({id(result) for result in results}) == 3


def test_failed_result_preserves_metadata():
    """FAILED results still carry provider, timing, and timestamps."""
    provider = StubProvider(error=ProviderError("down"))
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.FAILED
    assert result.provider == "stub"
    assert result.latency_ms >= 0.0
    assert result.completed_at is not None
    assert result.started_at <= result.completed_at
