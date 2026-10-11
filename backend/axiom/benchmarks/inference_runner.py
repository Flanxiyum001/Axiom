"""Opt-in, request-capped Nemotron prompt benchmark. Defaults to dry-run; no GPU jobs."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from axiom.benchmarks.loader import load_file
from axiom.benchmarks.models import BenchmarkCase, BenchmarkDataset
from axiom.comparison.comparison import compare_metric
from axiom.comparison.models import CaseComparison, MetadataDifference, RunComparison
from axiom.domain.models import Direction
from axiom.regression.detection import detect_from_comparison
from axiom.regression.models import MetricThresholds, RegressionConfig, RegressionReport

DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MAX_REQUESTS = 10
HARD_MAX_REQUESTS = 40
MAX_REPETITIONS = 4
DEFAULT_DATASET_PATH = Path(__file__).parent / "datasets" / "nemotron_prompt_ab_v1.json"
VARIANTS = ("baseline", "candidate")


class StructuredAnswer(BaseModel):
    """Minimal response contract used to measure output validity."""

    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)


class InferenceBenchmarkConfig(BaseModel):
    """Safety limits and non-secret parameters for one run."""

    model: str = DEFAULT_MODEL
    repetitions: int = Field(default=1, ge=1, le=MAX_REPETITIONS)
    max_requests: int = Field(default=DEFAULT_MAX_REQUESTS, ge=1, le=HARD_MAX_REQUESTS)
    timeout_seconds: float = Field(default=30.0, gt=0, le=120.0)


class InferenceAttempt(BaseModel):
    """One request result; never contains credentials or raw prompts."""

    case_id: str
    variant: Literal["baseline", "candidate"]
    repetition: int = Field(ge=1)
    latency_ms: float = Field(ge=0)
    request_succeeded: bool
    output_valid: bool
    answer: str | None = None
    answer_correct: bool | None = None
    confidence: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    error_type: str | None = None
    error_message: str | None = None


class VariantSummary(BaseModel):
    """Aggregate quality and cost measurements for one prompt variant."""

    variant: Literal["baseline", "candidate"]
    request_count: int
    successful_requests: int
    valid_outputs: int
    correct_answers: int
    success_rate: float
    output_valid_rate: float
    accuracy: float | None
    mean_latency_ms: float | None
    mean_total_tokens: float | None


class InferenceBenchmarkReport(BaseModel):
    """Portable raw-results and regression report with no secret material."""

    schema_version: str = "1.0"
    benchmark: str
    dataset_description: str = ""
    model: str
    base_url: str
    repetitions: int
    max_requests: int
    request_count: int
    started_at: datetime
    finished_at: datetime
    baseline: VariantSummary
    candidate: VariantSummary
    attempts: list[InferenceAttempt]
    comparison: RunComparison
    regression: RegressionReport
    limitations: list[str] = Field(default_factory=list)


def load_default_dataset() -> BenchmarkDataset:
    """Load the bundled fixed-answer prompt set."""
    return load_file(DEFAULT_DATASET_PATH)


def required_request_count(dataset: BenchmarkDataset, repetitions: int) -> int:
    """Count baseline and candidate calls before any request is started."""
    if repetitions < 1 or repetitions > MAX_REPETITIONS:
        raise ValueError(f"repetitions must be between 1 and {MAX_REPETITIONS}")
    return len(dataset.cases) * len(VARIANTS) * repetitions


def _safe_base_url(base_url: str) -> str:
    """Remove URL credentials, query parameters and fragments from reports."""
    parsed = urlsplit(base_url)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parsed.scheme, host, path, "", ""))


def _normalize_answer(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    return re.sub(r"[\s,.$]", "", value)


def _prompt_for(case: BenchmarkCase, variant: str) -> str:
    if variant == "baseline":
        return (
            f"Answer the task accurately. Task: {case.input}\n"
            'Return one JSON object with keys "answer" (a string) and '
            '"confidence" (a number from 0 to 1). No text outside JSON.'
        )
    if variant == "candidate":
        return (
            "Answer accurately and concisely. Check calculations silently.\n"
            f"Task: {case.input}\n"
            'Return one JSON object with keys "answer" (string) and '
            '"confidence" (number from 0 to 1). No extra text.'
        )
    raise ValueError(f"Unknown prompt variant: {variant!r}")


def _usage_value(usage: Any, name: str) -> int | None:
    value = getattr(usage, name, None) if usage is not None else None
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _run_one(
    *,
    client: Any,
    model: str,
    case: BenchmarkCase,
    variant: Literal["baseline", "candidate"],
    repetition: int,
) -> InferenceAttempt:
    prompt = _prompt_for(case, variant)
    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Follow the requested output format exactly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        latency_ms = max(0.0, (time.perf_counter() - start) * 1000.0)
        return InferenceAttempt(
            case_id=case.id,
            variant=variant,
            repetition=repetition,
            latency_ms=latency_ms,
            request_succeeded=False,
            output_valid=False,
            answer_correct=False if case.expected_output is not None else None,
            error_type=type(exc).__name__,
            error_message="Inference request failed; inspect local client logs if needed.",
        )

    latency_ms = max(0.0, (time.perf_counter() - start) * 1000.0)
    usage = getattr(response, "usage", None)
    choices = getattr(response, "choices", None) or []
    message = getattr(choices[0], "message", None) if choices else None
    content = getattr(message, "content", None) if message is not None else None
    usage_fields = {
        "prompt_tokens": _usage_value(usage, "prompt_tokens"),
        "completion_tokens": _usage_value(usage, "completion_tokens"),
        "total_tokens": _usage_value(usage, "total_tokens"),
    }
    if not isinstance(content, str) or not content.strip():
        return InferenceAttempt(
            case_id=case.id, variant=variant, repetition=repetition,
            latency_ms=latency_ms, request_succeeded=True, output_valid=False,
            answer_correct=False if case.expected_output is not None else None,
            error_type="empty_response", error_message="The provider returned no text content.",
            **usage_fields,
        )

    try:
        answer = StructuredAnswer.model_validate_json(content)
    except (ValidationError, ValueError):
        try:
            json.loads(content)
        except json.JSONDecodeError:
            error_type, error_message = "invalid_json", "Response content was not valid JSON."
        else:
            error_type, error_message = "invalid_schema", "JSON did not match the required answer schema."
        return InferenceAttempt(
            case_id=case.id, variant=variant, repetition=repetition,
            latency_ms=latency_ms, request_succeeded=True, output_valid=False,
            answer_correct=False if case.expected_output is not None else None,
            error_type=error_type, error_message=error_message, **usage_fields,
        )

    correct = None
    if case.expected_output is not None:
        correct = _normalize_answer(answer.answer) == _normalize_answer(case.expected_output)
    return InferenceAttempt(
        case_id=case.id, variant=variant, repetition=repetition,
        latency_ms=latency_ms, request_succeeded=True, output_valid=True,
        answer=answer.answer, answer_correct=correct, confidence=answer.confidence,
        **usage_fields,
    )


def _mean(values: list[float]) -> float | None:
    return math.fsum(values) / len(values) if values else None


def _summary(
    attempts: list[InferenceAttempt],
    variant: Literal["baseline", "candidate"],
) -> VariantSummary:
    if not attempts:
        raise ValueError(f"No attempts collected for {variant}")
    expected = [a.answer_correct for a in attempts if a.answer_correct is not None]
    token_values = [a.total_tokens for a in attempts if a.total_tokens is not None]
    mean_tokens = (
        _mean([float(value) for value in token_values])
        if len(token_values) == len(attempts) else None
    )
    successful = sum(a.request_succeeded for a in attempts)
    valid = sum(a.output_valid for a in attempts)
    correct = sum(value is True for value in expected)
    return VariantSummary(
        variant=variant,
        request_count=len(attempts),
        successful_requests=successful,
        valid_outputs=valid,
        correct_answers=correct,
        success_rate=100.0 * successful / len(attempts),
        output_valid_rate=100.0 * valid / len(attempts),
        accuracy=100.0 * correct / len(expected) if expected else None,
        mean_latency_ms=_mean([a.latency_ms for a in attempts]),
        mean_total_tokens=mean_tokens,
    )


def _case_value(attempts: list[InferenceAttempt], name: str) -> float | None:
    if not attempts:
        return None
    if name == "latency_ms":
        return _mean([a.latency_ms for a in attempts])
    if name == "success_rate":
        return 100.0 * sum(a.request_succeeded for a in attempts) / len(attempts)
    if name == "output_valid_rate":
        return 100.0 * sum(a.output_valid for a in attempts) / len(attempts)
    if name == "accuracy":
        scored = [a.answer_correct for a in attempts if a.answer_correct is not None]
        return 100.0 * sum(value is True for value in scored) / len(scored) if scored else None
    if name == "tokens":
        values = [a.total_tokens for a in attempts if a.total_tokens is not None]
        return _mean([float(value) for value in values]) if len(values) == len(attempts) else None
    raise ValueError(f"Unsupported benchmark metric: {name!r}")


def _make_comparison(
    *,
    dataset: BenchmarkDataset,
    run_id: str,
    baseline: VariantSummary,
    candidate: VariantSummary,
    attempts: list[InferenceAttempt],
    model: str,
) -> RunComparison:
    directions = {
        "latency_ms": Direction.MINIMIZE,
        "success_rate": Direction.MAXIMIZE,
        "output_valid_rate": Direction.MAXIMIZE,
        "accuracy": Direction.MAXIMIZE,
        "tokens": Direction.MINIMIZE,
    }
    values_a = {
        "latency_ms": baseline.mean_latency_ms,
        "success_rate": baseline.success_rate,
        "output_valid_rate": baseline.output_valid_rate,
        "accuracy": baseline.accuracy,
        "tokens": baseline.mean_total_tokens,
    }
    values_b = {
        "latency_ms": candidate.mean_latency_ms,
        "success_rate": candidate.success_rate,
        "output_valid_rate": candidate.output_valid_rate,
        "accuracy": candidate.accuracy,
        "tokens": candidate.mean_total_tokens,
    }
    metrics = [
        compare_metric(name, values_a[name], values_b[name], direction)
        for name, direction in directions.items()
    ]
    warnings: list[str] = []
    failed = sum(not a.request_succeeded for a in attempts)
    invalid = sum(a.request_succeeded and not a.output_valid for a in attempts)
    missing_usage = sum(a.total_tokens is None for a in attempts)
    if failed:
        warnings.append(f"{failed} inference request(s) failed.")
    if invalid:
        warnings.append(f"{invalid} response(s) failed output-schema validation.")
    if missing_usage:
        warnings.append(f"Token usage was unavailable for {missing_usage} request(s).")

    cases: list[CaseComparison] = []
    for case in dataset.cases:
        base_case = [a for a in attempts if a.case_id == case.id and a.variant == "baseline"]
        cand_case = [a for a in attempts if a.case_id == case.id and a.variant == "candidate"]
        case_metrics = [
            compare_metric(
                name,
                _case_value(base_case, name),
                _case_value(cand_case, name),
                direction,
            )
            for name, direction in directions.items()
        ]
        cases.append(CaseComparison(
            case_id=case.id,
            present_a=bool(base_case),
            present_b=bool(cand_case),
            metrics=case_metrics,
        ))
    return RunComparison(
        run_a_id=f"{run_id}-baseline",
        run_b_id=f"{run_id}-candidate",
        benchmark=dataset.name,
        dataset_version="1",
        label_a="baseline prompt v1",
        label_b="candidate prompt v1",
        providers_a=["nebius-token-factory"],
        providers_b=["nebius-token-factory"],
        models_a=[model],
        models_b=[model],
        metadata_differences=[
            MetadataDifference(
                field="prompt_variant",
                value_a="baseline prompt v1",
                value_b="candidate prompt v1",
            )
        ],
        metrics=metrics,
        cases=cases,
        missing_in_b=[],
        missing_in_a=[],
        warnings=warnings,
    )


def run_inference_benchmark(
    *,
    dataset: BenchmarkDataset,
    client: Any,
    config: InferenceBenchmarkConfig | None = None,
    base_url: str = DEFAULT_BASE_URL,
) -> InferenceBenchmarkReport:
    """Run prompt variants through an injected OpenAI-compatible client.

    This function never reads credentials or creates a live client itself.
    """
    active = config or InferenceBenchmarkConfig()
    required = required_request_count(dataset, active.repetitions)
    if required > active.max_requests:
        raise ValueError(
            f"Benchmark requires {required} requests, exceeding max_requests={active.max_requests}; "
            "increase the limit intentionally or reduce repetitions. No requests were sent."
        )

    started_at = datetime.now(UTC)
    run_id = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    attempts: list[InferenceAttempt] = []
    for repetition in range(1, active.repetitions + 1):
        for index, case in enumerate(dataset.cases):
            variants = VARIANTS if (index + repetition) % 2 == 1 else tuple(reversed(VARIANTS))
            for variant in variants:
                attempts.append(_run_one(
                    client=client,
                    model=active.model,
                    case=case,
                    variant=variant,
                    repetition=repetition,
                ))

    baseline = _summary([a for a in attempts if a.variant == "baseline"], "baseline")
    candidate = _summary([a for a in attempts if a.variant == "candidate"], "candidate")
    comparison = _make_comparison(
        dataset=dataset,
        run_id=run_id,
        baseline=baseline,
        candidate=candidate,
        attempts=attempts,
        model=active.model,
    )
    thresholds = RegressionConfig(per_metric={
        "latency_ms": MetricThresholds(warn_pct=10.0, fail_pct=25.0),
        "success_rate": MetricThresholds(warn_abs=5.0, fail_abs=15.0),
        "output_valid_rate": MetricThresholds(warn_abs=5.0, fail_abs=15.0),
        "accuracy": MetricThresholds(warn_abs=5.0, fail_abs=15.0),
        "tokens": MetricThresholds(warn_pct=20.0, fail_pct=40.0),
    })
    regression = detect_from_comparison(comparison, thresholds)
    return InferenceBenchmarkReport(
        benchmark=dataset.name,
        dataset_description=dataset.description,
        model=active.model,
        base_url=_safe_base_url(base_url),
        repetitions=active.repetitions,
        max_requests=active.max_requests,
        request_count=len(attempts),
        started_at=started_at,
        finished_at=datetime.now(UTC),
        baseline=baseline,
        candidate=candidate,
        attempts=attempts,
        comparison=comparison,
        regression=regression,
        limitations=[
            "Exploratory prompt A/B test, not a statistical significance test.",
            "Network/provider load affects latency; interpret small changes cautiously.",
            "Accuracy is exact-match against the bundled fixed answers.",
            "Live mode sends Token Factory inference requests but never launches GPU jobs.",
        ],
    )


def write_report(report: InferenceBenchmarkReport, path: str | Path) -> Path:
    """Write JSON atomically and refuse to overwrite an existing report."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {target}")
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(report.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark two Nemotron prompt variants. Default mode is dry-run."
    )
    parser.add_argument("--live", action="store_true", help="Explicitly send live Token Factory requests.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH, help="Benchmark dataset JSON.")
    parser.add_argument("--model", default=None, help="Model id; defaults to NEBIUS_MODEL or Nemotron.")
    parser.add_argument("--repetitions", type=int, default=1, help="Repetitions per variant (1-4).")
    parser.add_argument(
        "--max-requests", type=int, default=DEFAULT_MAX_REQUESTS,
        help=f"Request limit (1-{HARD_MAX_REQUESTS}); checked before the first request.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0, help="Per-request timeout (max 120s).")
    parser.add_argument("--output", type=Path, default=None, help="Live result JSON path; must not exist.")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)
    args = _build_parser().parse_args(argv)
    try:
        dataset = load_file(args.dataset)
        config = InferenceBenchmarkConfig(
            model=args.model or os.environ.get("NEBIUS_MODEL") or DEFAULT_MODEL,
            repetitions=args.repetitions,
            max_requests=args.max_requests,
            timeout_seconds=args.timeout_seconds,
        )
        required = required_request_count(dataset, config.repetitions)
        if required > config.max_requests:
            raise ValueError(
                f"This dataset requires {required} requests, exceeding --max-requests={config.max_requests}. "
                "No requests were sent."
            )
    except (ValueError, OSError, ValidationError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    base_url = os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL)
    if not args.live:
        print(json.dumps({
            "mode": "dry-run",
            "dataset": dataset.name,
            "model": config.model,
            "base_url": _safe_base_url(base_url),
            "cases": len(dataset.cases),
            "repetitions_per_variant": config.repetitions,
            "requests_required": required,
            "max_requests": config.max_requests,
            "api_calls_made": 0,
            "next_step": "Add --live to explicitly send the planned requests.",
        }, indent=2))
        return 0

    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        print("Live mode requires NEBIUS_API_KEY in the environment or local .env file.", file=sys.stderr)
        return 2

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=config.timeout_seconds,
        max_retries=0,
    )
    try:
        report = run_inference_benchmark(
            dataset=dataset, client=client, config=config, base_url=base_url
        )
        output_path = args.output or (
            Path("artifacts/benchmarks")
            / f"nemotron-prompt-ab-{report.started_at.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        )
        saved = write_report(report, output_path)
    except Exception as exc:
        print(f"Benchmark failed: {type(exc).__name__}. Credential details were not emitted.", file=sys.stderr)
        return 1

    print(json.dumps({
        "mode": "live",
        "report_path": str(saved),
        "model": report.model,
        "request_count": report.request_count,
        "baseline": report.baseline.model_dump(mode="json"),
        "candidate": report.candidate.model_dump(mode="json"),
        "regression_status": report.regression.status.value,
        "regression_reasons": report.regression.reasons,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
