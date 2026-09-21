"""Benchmark schemas: datasets, cases, and per-case evaluation config."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CaseEvaluationConfig(BaseModel):
    """Optional per-case evaluator tuning, decoupled from evaluator classes."""

    latency_budget_ms: float | None = Field(default=None, gt=0)
    token_budget: int | None = Field(default=None, gt=0)
    min_response_length: int | None = Field(default=None, ge=1)


class BenchmarkCase(BaseModel):
    """One runnable unit: input, optional reference, metadata, eval config."""

    id: str = Field(min_length=1)
    input: str = Field(min_length=1)
    expected_output: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    evaluation: CaseEvaluationConfig = Field(default_factory=CaseEvaluationConfig)


class BenchmarkDataset(BaseModel):
    """A named set of uniquely-identified benchmark cases."""

    name: str = Field(min_length=1)
    description: str = ""
    cases: list[BenchmarkCase] = Field(min_length=1)

    @field_validator("cases", mode="after")
    @classmethod
    def _unique_case_ids(cls, cases: list[BenchmarkCase]) -> list[BenchmarkCase]:
        """Reject datasets with duplicated case identifiers."""
        seen: set[str] = set()
        for case in cases:
            if case.id in seen:
                raise ValueError(f"Duplicated case id: {case.id!r}")
            seen.add(case.id)
        return cases

    def case_ids(self) -> list[str]:
        """Identifiers of all cases in dataset order."""
        return [case.id for case in self.cases]

    def get_case(self, case_id: str) -> BenchmarkCase | None:
        """Look up one case by id, returning None when absent."""
        for case in self.cases:
            if case.id == case_id:
                return case
        return None
