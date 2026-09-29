"""Parallel execution: bounds, ordering, isolation, and configuration."""

import threading

from pydantic import BaseModel

from axiom.benchmarks.loader import load_dict
from axiom.benchmarks.models import BenchmarkDataset
from axiom.domain.interfaces import ProviderError, ReasoningProvider
from axiom.evaluation.evaluators import LatencyEvaluator, ResponseEvaluator
from axiom.evaluation.framework import EvaluationFramework
from axiom.experiments.runner import ExperimentRunner
from axiom.pipeline.pipeline import ExperimentPipeline, RECOMMENDED_MAX_CONCURRENCY


class TextOutput(BaseModel):
    """Deterministic stub output for parallel execution tests."""

    answer: str


class EchoProvider(ReasoningProvider):
    """Test double answering from the incoming prompt."""

    name = "echo"

    def generate(self, *, system, prompt, context, output_type):
        """Return canned text derived from the prompt."""
        return TextOutput(answer=f"Answer to {prompt}")


class BarrierProvider(ReasoningProvider):
    """Test double forcing worker overlap to prove real parallelism."""

    name = "barrier"

    def __init__(self, parties):
        """Block workers pairwise so overlap is mandatory, not luck."""
        self.barrier = threading.Barrier(parties)
        self.lock = threading.Lock()
        self.active = 0
        self.max_observed = 0

    def generate(self, *, system, prompt, context, output_type):
        """Track concurrency, rendezvous, then answer."""
        with self.lock:
            self.active += 1
            self.max_observed = max(self.max_observed, self.active)
        try:
            self.barrier.wait(timeout=30)
        finally:
            with self.lock:
                self.active -= 1
        return TextOutput(answer=f"Answer to {prompt}")


class GateProvider(ReasoningProvider):
    """Test double finishing the first case last to scramble completion order."""

    name = "gate"

    def __init__(self, total):
        """Hold case-000 until every other case has finished."""
        self.total = total
        self.lock = threading.Lock()
        self.done = 0
        self.event = threading.Event()
        self.finish_order = []

    def generate(self, *, system, prompt, context, output_type):
        """Gate the first case, release it once all others complete."""
        if "case-000" in prompt:
            assert self.event.wait(timeout=30)
        else:
            with self.lock:
                self.done += 1
                if self.done == self.total - 1:
                    self.event.set()
        with self.lock:
            self.finish_order.append(prompt)
        return TextOutput(answer=f"Answer to {prompt}")


def _dataset(size=4):
    """Dataset with uniquely identifiable inputs for association checks."""
    return load_dict(
        {
            "name": "parallel_benchmark",
            "cases": [{"id": f"case-{i:03d}", "input": f"case-{i:03d} question?"} for i in range(size)],
        }
    )


def _pipeline(provider=None, evaluators=None, **kwargs):
    """Build a pipeline with stub defaults overridable per test."""
    runner = ExperimentRunner(provider or EchoProvider())
    framework = EvaluationFramework(
        evaluators if evaluators is not None else [LatencyEvaluator(60000.0), ResponseEvaluator()]
    )
    return ExperimentPipeline(runner, framework, **kwargs)


def test_parallel_success_matches_sequential():
    """Parallel runs produce the same verdicts and order as sequential runs."""
    dataset = _dataset()
    parallel = _pipeline(max_concurrency=4).run(dataset, output_type=TextOutput)
    sequential = _pipeline(max_concurrency=1).run(dataset, output_type=TextOutput)
    assert parallel.failures == []
    assert [record.case_id for record in parallel.records] == [f"case-{i:03d}" for i in range(4)]
    assert parallel.report is not None
    assert parallel.report.cases == 4
    assert _tallies(parallel) == _tallies(sequential)


def _tallies(pipeline_result):
    """Per-evaluator verdict tallies identifying a report's verdict shape."""
    return [
        (summary.evaluator, summary.passed, summary.failed)
        for summary in pipeline_result.report.summaries
    ]


def test_concurrency_bound_respected():
    """Workers truly overlap but never exceed the configured maximum."""
    provider = BarrierProvider(parties=2)
    result = _pipeline(provider=provider, max_concurrency=2).run(_dataset(), output_type=TextOutput)
    assert result.failures == []
    assert result.report is not None
    assert provider.max_observed == 2


def test_sequential_mode_runs_one_at_a_time():
    """max_concurrency=1 never overlaps executions."""
    provider = BarrierProvider(parties=1)
    result = _pipeline(provider=provider, max_concurrency=1).run(_dataset(), output_type=TextOutput)
    assert result.failures == []
    assert provider.max_observed == 1


def test_default_concurrency_is_sequential():
    """Omitting max_concurrency preserves existing sequential behavior."""
    assert ExperimentPipeline(
        ExperimentRunner(EchoProvider()), EvaluationFramework()
    ).max_concurrency == 1
    assert RECOMMENDED_MAX_CONCURRENCY == 4


def test_out_of_order_completion_preserves_association():
    """Records follow dataset order even when completion order is scrambled."""
    provider = GateProvider(total=4)
    result = _pipeline(provider=provider, max_concurrency=4).run(_dataset(), output_type=TextOutput)
    assert result.failures == []
    assert [record.case_id for record in result.records] == [f"case-{i:03d}" for i in range(4)]
    assert "case-000" in provider.finish_order[-1]
    assert "case-000" not in provider.finish_order[0]
    for record in result.records:
        assert record.evaluation is not None


def test_mixed_success_and_failure_parallel():
    """Failed and completed cases share one report with honest tallies."""
    class SelectiveProvider(EchoProvider):
        """Test double failing a single case by prompt marker."""

        def generate(self, *, system, prompt, context, output_type):
            """Raise for case-001, answer everything else."""
            if "case-001" in prompt:
                raise ProviderError("down")
            return super().generate(
                system=system, prompt=prompt, context=context, output_type=output_type
            )

    result = _pipeline(provider=SelectiveProvider(), max_concurrency=4).run(
        _dataset(), output_type=TextOutput
    )
    assert result.failures == []
    assert len(result.records) == 4
    assert [record.case_id for record in result.records] == [f"case-{i:03d}" for i in range(4)]
    response = result.report.summary_for("response")
    assert response is not None
    assert response.passed == 3
    assert response.failed == 1


def test_all_provider_failures_parallel():
    """Total provider outage still yields full records and a report."""
    class DownProvider(ReasoningProvider):
        """Test double failing every provider call."""

        name = "down"

        def generate(self, *, system, prompt, context, output_type):
            """Raise unconditionally."""
            raise ProviderError("down")

    result = _pipeline(provider=DownProvider(), max_concurrency=4).run(
        _dataset(), output_type=TextOutput
    )
    assert result.failures == []
    assert len(result.records) == 4
    assert result.report is not None


def test_empty_cases_produce_empty_result():
    """No cases means no tasks, no errors, and no report."""
    dataset = BenchmarkDataset.model_construct(name="empty", cases=[])
    result = _pipeline(max_concurrency=4).run(dataset, output_type=TextOutput)
    assert result.records == []
    assert result.failures == []
    assert result.report is None


def test_invalid_concurrency_rejected():
    """Zero, negative, non-integer, and boolean limits fail at construction."""
    for bad in (0, -1, 2.5, "4", True, None):
        try:
            ExperimentPipeline(
                ExperimentRunner(EchoProvider()), EvaluationFramework(), max_concurrency=bad
            )
        except ValueError as exc:
            assert "max_concurrency" in str(exc)
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_valid_concurrency_accepted():
    """Positive integers from sequential upward construct cleanly."""
    for good in (1, 2, 4, 64):
        pipeline = ExperimentPipeline(
            ExperimentRunner(EchoProvider()), EvaluationFramework(), max_concurrency=good
        )
        assert pipeline.max_concurrency == good


def test_fail_fast_parallel_reraises():
    """Fail-fast still stops the run when a case breaks unexpectedly."""
    runner = ExperimentRunner(EchoProvider())
    original = runner.run

    def broken(request, *, output_type):
        raise RuntimeError("kaput")

    runner.run = broken
    pipeline = ExperimentPipeline(runner, EvaluationFramework(), fail_fast=True, max_concurrency=4)
    try:
        pipeline.run(_dataset(), output_type=TextOutput)
    except RuntimeError as exc:
        assert "kaput" in str(exc)
        return
    raise AssertionError("expected RuntimeError")


def test_fail_fast_does_not_wait_for_blocked_cases():
    """Fail-fast reacts to the failure while an earlier case stays blocked."""
    gate = threading.Event()
    finished = []
    lock = threading.Lock()

    class GateFailProvider(ReasoningProvider):
        """Test double blocking case-000 until the test releases it."""

        name = "gate-fail"

        def generate(self, *, system, prompt, context, output_type):
            """Hold the first case on a gate; answer everything else."""
            if "case-000" in prompt:
                assert gate.wait(timeout=60)
            with lock:
                finished.append(prompt)
            return TextOutput(answer="ok")

    runner = ExperimentRunner(GateFailProvider())
    original = runner.run

    def broken(request, *, output_type):
        if "case-001" in request.prompt:
            raise RuntimeError("kaput")
        return original(request, output_type=output_type)

    runner.run = broken
    pipeline = ExperimentPipeline(runner, EvaluationFramework(), fail_fast=True, max_concurrency=2)
    try:
        pipeline.run(_dataset(size=2), output_type=TextOutput)
    except RuntimeError as exc:
        assert "kaput" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
    assert not any("case-000" in prompt for prompt in finished)
    gate.set()


def test_deterministic_verdicts_across_runs():
    """Repeated parallel runs agree on order and verdicts, not wall-clock values."""
    dataset = _dataset()
    first = _pipeline(max_concurrency=4).run(dataset, output_type=TextOutput)
    second = _pipeline(max_concurrency=4).run(dataset, output_type=TextOutput)
    assert [record.case_id for record in first.records] == [
        record.case_id for record in second.records
    ]
    assert _tallies(first) == _tallies(second)


def test_rolling_window_starts_later_cases_early():
    """A freed worker picks up the next case while an early case stays blocked."""
    gate = threading.Event()
    case2_done = threading.Event()

    class RollingProvider(ReasoningProvider):
        """Test double blocking case-000 while signaling case-002 completion."""

        name = "rolling"

        def generate(self, *, system, prompt, context, output_type):
            """Hold the first case on a gate; flag when the third finishes."""
            if "case-000" in prompt:
                assert gate.wait(timeout=60)
            if "case-002" in prompt:
                case2_done.set()
            return TextOutput(answer="ok")

    holder = {}
    pipeline = ExperimentPipeline(
        ExperimentRunner(RollingProvider()), EvaluationFramework(), max_concurrency=2
    )

    def target():
        holder["result"] = pipeline.run(_dataset(size=3), output_type=TextOutput)

    worker = threading.Thread(target=target)
    worker.start()
    try:
        assert case2_done.wait(timeout=60)
        assert not gate.is_set()
    finally:
        gate.set()
        worker.join(timeout=60)
    assert not worker.is_alive()
    result = holder["result"]
    assert [record.case_id for record in result.records] == ["case-000", "case-001", "case-002"]
    assert result.failures == []


def test_fail_fast_never_submits_after_observed_failure():
    """Fail-fast raises before any replenishment once a failure is observed."""
    gate = threading.Event()
    started = []
    lock = threading.Lock()

    class SlowSuccessProvider(ReasoningProvider):
        """Test double blocking case-000 while tracking every start."""

        name = "slow-success"

        def generate(self, *, system, prompt, context, output_type):
            """Hold the first case on a gate; record all starts."""
            if "case-000" in prompt:
                assert gate.wait(timeout=60)
            with lock:
                started.append(prompt)
            return TextOutput(answer="ok")

    runner = ExperimentRunner(SlowSuccessProvider())
    original = runner.run

    def broken(request, *, output_type):
        if "case-001" in request.prompt:
            raise RuntimeError("kaput")
        return original(request, output_type=output_type)

    runner.run = broken
    pipeline = ExperimentPipeline(runner, EvaluationFramework(), fail_fast=True, max_concurrency=2)
    try:
        pipeline.run(_dataset(size=3), output_type=TextOutput)
    except RuntimeError as exc:
        assert "kaput" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
    finally:
        gate.set()
    assert not any("case-002" in prompt for prompt in started)
