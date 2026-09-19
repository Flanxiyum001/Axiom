import time

from pydantic import BaseModel

from axiom.domain.interfaces import ProviderError, ReasoningProvider
from axiom.domain.models import RunStatus
from axiom.experiments.runner import ExperimentRequest, ExperimentResult, ExperimentRunner


class SampleOutput(BaseModel):
    answer: str


class StubProvider(ReasoningProvider):
    name = "stub"

    def __init__(self, output=None, error=None, delay=0.0, model=None):
        self.output = output
        self.error = error
        self.delay = delay
        self.model = model
        self.seen = {}

    def generate(self, *, system, prompt, context, output_type):
        self.seen = {"system": system, "prompt": prompt, "context": context, "output_type": output_type}
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        if self.output is not None:
            return self.output
        return output_type(answer="default")


def test_success_returns_structured_result():
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
    assert ExperimentRequest(system="s", prompt="p").context == {}


def test_provider_error_becomes_failed_result():
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
    provider = StubProvider(delay=0.05)
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.COMPLETED
    assert result.latency_ms >= 40.0


def test_model_recorded_when_provider_exposes_it():
    provider = StubProvider(model="nemotron-test")
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.model == "nemotron-test"


def test_model_and_tokens_default_none():
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
    from axiom.providers.schemas import PlanOutput

    provider = StubProvider()
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=PlanOutput,
    )
    assert result.status == RunStatus.COMPLETED
    assert isinstance(result.output, PlanOutput)


def test_garbage_output_becomes_failed_result():
    provider = StubProvider(output={"not": "a model"})
    result = ExperimentRunner(provider).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.FAILED
    assert result.output is None
    assert result.error is not None


def test_none_output_becomes_failed_result():
    class NoneProvider(ReasoningProvider):
        name = "none"

        def generate(self, *, system, prompt, context, output_type):
            return None

    result = ExperimentRunner(NoneProvider()).run(
        ExperimentRequest(system="s", prompt="p"),
        output_type=SampleOutput,
    )
    assert result.status == RunStatus.FAILED
    assert result.output is None
