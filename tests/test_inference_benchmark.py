"""Tests for the opt-in inference benchmark; all provider calls are mocked."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from axiom.benchmarks.inference_runner import (
    DEFAULT_DATASET_PATH,
    InferenceBenchmarkConfig,
    load_default_dataset,
    main,
    run_inference_benchmark,
    write_report,
)
from axiom.regression.models import RegressionStatus


_ANSWERS = {
    "Compute 17 times 24": "408",
    "5 boxes with 6 notebooks": "23",
    "2, 4, 8, 16": "32",
    "3 full weeks": "21",
    "100 and 63": "37",
}


def _response(content: str, prompt_tokens: int = 10, completion_tokens: int = 3):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


class FakeClient:
    def __init__(self, responder=None):
        self.calls = []
        self.responder = responder or self._correct_response

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responder(kwargs)

    @staticmethod
    def _correct_response(kwargs):
        prompt = kwargs["messages"][-1]["content"]
        for fragment, answer in _ANSWERS.items():
            if fragment in prompt:
                return _response(json.dumps({"answer": answer, "confidence": 0.99}))
        return _response(json.dumps({"answer": "unknown", "confidence": 0.5}))


def test_bundled_dataset_has_five_unique_fixed_answer_cases():
    dataset = load_default_dataset()
    assert len(dataset.cases) == 5
    assert len(dataset.case_ids()) == len(set(dataset.case_ids()))
    assert all(case.expected_output is not None for case in dataset.cases)
    assert DEFAULT_DATASET_PATH.exists()


def test_request_limit_is_checked_before_any_client_call():
    dataset = load_default_dataset()
    client = FakeClient()
    with pytest.raises(ValueError, match="No requests were sent"):
        run_inference_benchmark(
            dataset=dataset,
            client=client,
            config=InferenceBenchmarkConfig(repetitions=2, max_requests=10),
        )
    assert client.calls == []


def test_run_collects_latency_validity_accuracy_tokens_and_regression():
    dataset = load_default_dataset()
    client = FakeClient()
    report = run_inference_benchmark(
        dataset=dataset,
        client=client,
        config=InferenceBenchmarkConfig(max_requests=10),
    )
    assert len(client.calls) == 10
    assert report.request_count == 10
    assert report.baseline.success_rate == 100.0
    assert report.candidate.success_rate == 100.0
    assert report.baseline.output_valid_rate == 100.0
    assert report.candidate.output_valid_rate == 100.0
    assert report.baseline.accuracy == 100.0
    assert report.candidate.accuracy == 100.0
    assert report.baseline.mean_latency_ms is not None
    assert report.baseline.mean_total_tokens == 13.0
    assert len(report.comparison.cases) == 5
    assert report.regression.status == RegressionStatus.PASS
    assert all(call["temperature"] == 0.1 for call in client.calls)
    assert all(call["response_format"] == {"type": "json_object"} for call in client.calls)


def test_invalid_json_is_counted_as_failed_validity_not_request_failure():
    dataset = load_default_dataset()
    client = FakeClient(lambda _: _response("this is not json"))
    report = run_inference_benchmark(
        dataset=dataset,
        client=client,
        config=InferenceBenchmarkConfig(max_requests=10),
    )
    assert report.baseline.success_rate == 100.0
    assert report.baseline.output_valid_rate == 0.0
    assert report.baseline.accuracy == 0.0
    assert all(attempt.error_type == "invalid_json" for attempt in report.attempts)
    assert report.regression.status == RegressionStatus.WARNING


def test_request_errors_are_recorded_without_exposing_exception_details():
    dataset = load_default_dataset()

    def fail_with_secret(_):
        raise RuntimeError("simulated error contains secret-never-print")

    report = run_inference_benchmark(
        dataset=dataset,
        client=FakeClient(fail_with_secret),
        config=InferenceBenchmarkConfig(max_requests=10),
    )
    serialized = report.model_dump_json()
    assert report.baseline.success_rate == 0.0
    assert report.regression.status == RegressionStatus.WARNING
    assert "secret-never-print" not in serialized
    assert all(attempt.error_type == "RuntimeError" for attempt in report.attempts)


def test_missing_token_usage_is_explicit_and_warns():
    dataset = load_default_dataset()

    def no_usage(kwargs):
        prompt = kwargs["messages"][-1]["content"]
        answer = next((v for k, v in _ANSWERS.items() if k in prompt), "unknown")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({"answer": answer, "confidence": 0.7})
            ))],
            usage=None,
        )

    report = run_inference_benchmark(
        dataset=dataset,
        client=FakeClient(no_usage),
        config=InferenceBenchmarkConfig(max_requests=10),
    )
    assert report.baseline.mean_total_tokens is None
    assert report.regression.status == RegressionStatus.WARNING
    assert any("Token usage was unavailable" in item for item in report.comparison.warnings)


def test_write_report_is_json_and_never_overwrites(tmp_path: Path):
    report = run_inference_benchmark(
        dataset=load_default_dataset(),
        client=FakeClient(),
        config=InferenceBenchmarkConfig(max_requests=10),
    )
    path = tmp_path / "nested" / "report.json"
    written = write_report(report, path)
    content = json.loads(written.read_text(encoding="utf-8"))
    assert content["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert content["request_count"] == 10
    with pytest.raises(FileExistsError):
        write_report(report, path)


def test_cli_is_dry_run_by_default(monkeypatch, capsys):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    result = main(["--max-requests", "10"])
    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["mode"] == "dry-run"
    assert output["requests_required"] == 10
    assert output["api_calls_made"] == 0


def test_live_mode_requires_key_before_constructing_client(monkeypatch, capsys):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    result = main(["--live", "--max-requests", "10"])
    captured = capsys.readouterr()
    assert result == 2
    assert "NEBIUS_API_KEY" in captured.err
    assert captured.out == ""
