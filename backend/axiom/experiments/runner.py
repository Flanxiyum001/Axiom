from __future__ import annotations

import time
from datetime import datetime
from typing import Generic

from pydantic import BaseModel, Field

from axiom.domain.interfaces import ReasoningProvider, T
from axiom.domain.models import RunStatus, utcnow


class ExperimentRequest(BaseModel):
    system: str
    prompt: str
    context: dict[str, str] = Field(default_factory=dict)


class ExperimentResult(BaseModel, Generic[T]):
    output: T | None = None
    status: RunStatus = RunStatus.COMPLETED
    latency_ms: float = 0.0
    provider: str = ""
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None


class ExperimentRunner:
    def __init__(self, provider: ReasoningProvider) -> None:
        self.provider = provider

    def run(self, request: ExperimentRequest, *, output_type: type[T]) -> ExperimentResult[T]:
        started_at = utcnow()
        begin = time.perf_counter()
        result_type = ExperimentResult[output_type]
        try:
            output = self.provider.generate(
                system=request.system,
                prompt=request.prompt,
                context=dict(request.context),
                output_type=output_type,
            )
            if output is None:
                raise ProviderError("Provider returned no output")
            return result_type(
                output=output,
                status=RunStatus.COMPLETED,
                latency_ms=(time.perf_counter() - begin) * 1000.0,
                provider=self.provider.name,
                model=_model_name(self.provider),
                started_at=started_at,
                completed_at=utcnow(),
            )
        except Exception as exc:
            return result_type(
                output=None,
                status=RunStatus.FAILED,
                latency_ms=(time.perf_counter() - begin) * 1000.0,
                provider=self.provider.name,
                model=_model_name(self.provider),
                error=f"{type(exc).__name__}: {exc}",
                started_at=started_at,
                completed_at=utcnow(),
            )


def _model_name(provider: ReasoningProvider) -> str | None:
    model = getattr(provider, "model", None)
    return model if isinstance(model, str) else None
