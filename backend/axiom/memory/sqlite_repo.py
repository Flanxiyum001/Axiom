from __future__ import annotations

import sqlite3
import threading

from axiom.domain.interfaces import MemoryRepository
from axiom.domain.models import (
    Evaluation,
    Evidence,
    ExperimentPlan,
    ExperimentRun,
    ExperimentSpec,
    Hypothesis,
    ResearchHistory,
    ResearchObjective,
)


class SqliteRepository(MemoryRepository):
    def __init__(self, db_path: str = "axiom.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS objectives (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS hypotheses (id TEXT PRIMARY KEY, objective_id TEXT NOT NULL, iteration INTEGER NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_hypotheses_objective ON hypotheses (objective_id);
                CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, hypothesis_id TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_plans_hypothesis ON plans (hypothesis_id);
                CREATE TABLE IF NOT EXISTS specs (id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_specs_plan ON specs (plan_id);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs (experiment_id);
                CREATE TABLE IF NOT EXISTS evaluations (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, baseline_run_id TEXT, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_evaluations_run ON evaluations (run_id);
                CREATE TABLE IF NOT EXISTS evidence_items (id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL, hypothesis_id TEXT NOT NULL, objective_id TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_evidence_evaluation ON evidence_items (evaluation_id);
                """
            )
            self._conn.commit()

    def save_objective(self, objective: ResearchObjective) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO objectives (id, data) VALUES (?, ?)",
                (objective.id, objective.model_dump_json()),
            )
            self._conn.commit()

    def get_objective(self, objective_id: str) -> ResearchObjective | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM objectives WHERE id = ?", (objective_id,)
            ).fetchone()
        if row is None:
            return None
        return ResearchObjective.model_validate_json(row["data"])

    def list_objectives(self) -> list[ResearchObjective]:
        with self._lock:
            rows = self._conn.execute("SELECT data FROM objectives").fetchall()
        return [ResearchObjective.model_validate_json(r["data"]) for r in rows]

    def save_hypothesis(self, hypothesis: Hypothesis) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO hypotheses (id, objective_id, iteration, data) VALUES (?, ?, ?, ?)",
                (hypothesis.id, hypothesis.objective_id, hypothesis.iteration, hypothesis.model_dump_json()),
            )
            self._conn.commit()

    def get_hypothesis(self, hypothesis_id: str) -> Hypothesis | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM hypotheses WHERE id = ?", (hypothesis_id,)
            ).fetchone()
        if row is None:
            return None
        return Hypothesis.model_validate_json(row["data"])

    def list_hypotheses(self, objective_id: str) -> list[Hypothesis]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM hypotheses WHERE objective_id = ? ORDER BY iteration",
                (objective_id,),
            ).fetchall()
        return [Hypothesis.model_validate_json(r["data"]) for r in rows]

    def save_plan(self, plan: ExperimentPlan) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO plans (id, hypothesis_id, data) VALUES (?, ?, ?)",
                (plan.id, plan.hypothesis_id, plan.model_dump_json()),
            )
            self._conn.commit()

    def get_plan(self, plan_id: str) -> ExperimentPlan | None:
        with self._lock:
            row = self._conn.execute("SELECT data FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if row is None:
            return None
        return ExperimentPlan.model_validate_json(row["data"])

    def save_spec(self, spec: ExperimentSpec) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO specs (id, plan_id, data) VALUES (?, ?, ?)",
                (spec.id, spec.plan_id, spec.model_dump_json()),
            )
            self._conn.commit()

    def get_spec(self, spec_id: str) -> ExperimentSpec | None:
        with self._lock:
            row = self._conn.execute("SELECT data FROM specs WHERE id = ?", (spec_id,)).fetchone()
        if row is None:
            return None
        return ExperimentSpec.model_validate_json(row["data"])

    def save_run(self, run: ExperimentRun) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO runs (id, experiment_id, data) VALUES (?, ?, ?)",
                (run.id, run.experiment_id, run.model_dump_json()),
            )
            self._conn.commit()

    def get_run(self, run_id: str) -> ExperimentRun | None:
        with self._lock:
            row = self._conn.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return ExperimentRun.model_validate_json(row["data"])

    def list_runs(self, experiment_id: str) -> list[ExperimentRun]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM runs WHERE experiment_id = ?", (experiment_id,)
            ).fetchall()
        return [ExperimentRun.model_validate_json(r["data"]) for r in rows]

    def save_evaluation(self, evaluation: Evaluation) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO evaluations (id, run_id, baseline_run_id, data) VALUES (?, ?, ?, ?)",
                (evaluation.id, evaluation.run_id, evaluation.baseline_run_id, evaluation.model_dump_json()),
            )
            self._conn.commit()

    def get_evaluation(self, evaluation_id: str) -> Evaluation | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM evaluations WHERE id = ?", (evaluation_id,)
            ).fetchone()
        if row is None:
            return None
        return Evaluation.model_validate_json(row["data"])

    def list_evaluations(self, hypothesis_id: str) -> list[Evaluation]:
        plan = self._plan_for_hypothesis(hypothesis_id)
        if plan is None:
            return []
        spec_ids = self._spec_ids_for_plan(plan.id)
        run_ids: set[str] = set()
        with self._lock:
            for spec_id in spec_ids:
                rows = self._conn.execute(
                    "SELECT id FROM runs WHERE experiment_id = ?", (spec_id,)
                ).fetchall()
                run_ids.update(r["id"] for r in rows)
            if not run_ids:
                return []
            placeholders = ",".join("?" for _ in run_ids)
            rows = self._conn.execute(
                f"SELECT data FROM evaluations WHERE run_id IN ({placeholders})",
                tuple(run_ids),
            ).fetchall()
        return [Evaluation.model_validate_json(r["data"]) for r in rows]

    def save_evidence(self, evidence: Evidence) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO evidence_items (id, evaluation_id, hypothesis_id, objective_id, data) VALUES (?, ?, ?, ?, ?)",
                (evidence.id, evidence.evaluation_id, evidence.hypothesis_id, evidence.objective_id, evidence.model_dump_json()),
            )
            self._conn.commit()

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM evidence_items WHERE id = ?", (evidence_id,)
            ).fetchone()
        if row is None:
            return None
        return Evidence.model_validate_json(row["data"])

    def next_hypothesis_number(self, objective_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(iteration) AS m FROM hypotheses WHERE objective_id = ?",
                (objective_id,),
            ).fetchone()
        if row is None or row["m"] is None:
            return 0
        return int(row["m"]) + 1

    def history_for_objective(self, objective_id: str) -> list[ResearchHistory]:
        objective = self.get_objective(objective_id)
        if objective is None:
            return []
        histories: list[ResearchHistory] = []
        for hypothesis in self.list_hypotheses(objective_id):
            plan = self._plan_for_hypothesis(hypothesis.id)
            if plan is None:
                continue
            spec = self._spec_for_plan(plan.id)
            if spec is None:
                continue
            runs = self.list_runs(spec.id)
            baseline_runs = self._runs_for_spec_baseline(plan.id, spec.id)
            all_runs = baseline_runs + runs
            evaluation = self._evaluation_for_runs([r.id for r in all_runs])
            evidence = self._evidence_for_evaluation(evaluation.id) if evaluation else None
            histories.append(
                ResearchHistory(
                    objective=objective,
                    hypothesis=hypothesis,
                    plan=plan,
                    spec=spec,
                    runs=all_runs,
                    evaluation=evaluation,
                    evidence=evidence,
                )
            )
        return histories

    def _plan_for_hypothesis(self, hypothesis_id: str) -> ExperimentPlan | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM plans WHERE hypothesis_id = ? ORDER BY rowid LIMIT 1",
                (hypothesis_id,),
            ).fetchone()
        if row is None:
            return None
        return ExperimentPlan.model_validate_json(row["data"])

    def _spec_ids_for_plan(self, plan_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id FROM specs WHERE plan_id = ?", (plan_id,)
            ).fetchall()
        return [r["id"] for r in rows]

    def _spec_for_plan(self, plan_id: str) -> ExperimentSpec | None:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM specs WHERE plan_id = ?", (plan_id,)
            ).fetchall()
        if not rows:
            return None
        candidates = [ExperimentSpec.model_validate_json(r["data"]) for r in rows]
        for spec in candidates:
            if spec.environment.get("__AXIOM_LEVER_MODE__", "candidate") == "candidate":
                return spec
        return candidates[0]

    def _runs_for_spec_baseline(self, plan_id: str, candidate_spec_id: str) -> list[ExperimentRun]:
        runs: list[ExperimentRun] = []
        for spec_id in self._spec_ids_for_plan(plan_id):
            if spec_id == candidate_spec_id:
                continue
            runs.extend(self.list_runs(spec_id))
        return runs

    def _evaluation_for_runs(self, run_ids: list[str]) -> Evaluation | None:
        if not run_ids:
            return None
        with self._lock:
            placeholders = ",".join("?" for _ in run_ids)
            row = self._conn.execute(
                f"SELECT data FROM evaluations WHERE run_id IN ({placeholders}) ORDER BY rowid DESC LIMIT 1",
                tuple(run_ids),
            ).fetchone()
        if row is None:
            return None
        return Evaluation.model_validate_json(row["data"])

    def _evidence_for_evaluation(self, evaluation_id: str) -> Evidence | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM evidence_items WHERE evaluation_id = ? ORDER BY rowid DESC LIMIT 1",
                (evaluation_id,),
            ).fetchone()
        if row is None:
            return None
        return Evidence.model_validate_json(row["data"])
