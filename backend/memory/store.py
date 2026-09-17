from typing import List, Dict, Optional
from ..models.schemas import ExperimentResult
from uuid import UUID

class ExperimentStore:
    def __init__(self):
        self._results: Dict[UUID, ExperimentResult] = {}

    def save_result(self, result: ExperimentResult):
        self._results[result.experiment_id] = result

    def get_result(self, experiment_id: UUID) -> Optional[ExperimentResult]:
        return self._results.get(experiment_id)

    def list_all_results(self) -> List[ExperimentResult]:
        return list(self._results.values())

    def get_successful_experiments(self) -> List[ExperimentResult]:
        return [r for r in self._results.values() if r.status == "completed"]

    def get_failed_experiments(self) -> List[ExperimentResult]:
        return [r for r in self._results.values() if r.status == "failed"]
