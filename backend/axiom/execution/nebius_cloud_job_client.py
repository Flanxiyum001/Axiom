"""Real Nebius AI Cloud job client.

Implements the NebiusJobClient abstraction using the Nebius Serverless
AI Jobs REST API (https://api.nebius.cloud/ai/v1/jobs).
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

import httpx

from axiom.config import Settings
from axiom.domain.models import Artifact, ExperimentSpec
from axiom.execution.nebius_auth import (
    EnvTokenProvider,
    NebiusAuthProvider,
    StaticTokenProvider,
)
from axiom.execution.nebius_job_client import (
    JobArtifacts,
    JobHandle,
    JobState,
    JobStatus,
    NebiusJobClient,
)

logger = logging.getLogger("axiom.execution.nebius")

# Default Nebius API base URL
DEFAULT_BASE_URL = "https://api.nebius.cloud"
JOBS_API_PATH = "/ai/v1/jobs"

# Mapping from Nebius state strings to our JobStatus enum
NEBIUS_STATE_MAP = {
    "STATE_UNSPECIFIED": JobStatus.SUBMITTED,
    "PROVISIONING": JobStatus.SUBMITTED,
    "STARTING": JobStatus.SUBMITTED,
    "IMAGE_PULLING": JobStatus.SUBMITTED,
    "RUNNING": JobStatus.RUNNING,
    "COMPLETED": JobStatus.COMPLETED,
    "CANCELLING": JobStatus.CANCELLED,
    "CANCELLED": JobStatus.CANCELLED,
    "DELETING": JobStatus.CANCELLED,
    "FAILED": JobStatus.FAILED,
    "ERROR": JobStatus.FAILED,
}


class NebiusHTTPError(RuntimeError):
    """Raised when an HTTP request to Nebius fails."""


class RealNebiusJobClient(NebiusJobClient):
    """Production implementation of NebiusJobClient using the REST API."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        auth_provider: Optional[NebiusAuthProvider] = None,
        base_url: str = DEFAULT_BASE_URL,
        http_client: Optional[httpx.Client] = None,
        request_timeout: float = 60.0,
        project_id: Optional[str] = None,
        container_image: Optional[str] = None,
        artifact_store_uri: Optional[str] = None,
    ) -> None:
        self.settings = settings
        self._auth_provider = auth_provider
        self._base_url = base_url.rstrip("/")
        self._http_client = http_client
        self._request_timeout = request_timeout
        self._project_id = project_id
        self._container_image = container_image
        self._artifact_store_uri = artifact_store_uri

    @property
    def auth_provider(self) -> NebiusAuthProvider:
        if self._auth_provider is not None:
            return self._auth_provider
        return EnvTokenProvider()

    @property
    def http_client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=self._request_timeout)
        return self._http_client

    def _headers(self) -> dict[str, str]:
        token = self.auth_provider.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        try:
            resp = self.http_client.request(
                method,
                url,
                headers=self._headers(),
                json=json,
                params=params,
                timeout=self._request_timeout,
            )
        except httpx.TimeoutException as exc:
            raise NebiusHTTPError(f"Request to {url} timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise NebiusHTTPError(f"Request to {url} failed: {exc}") from exc

        if resp.status_code >= 400:
            try:
                err_body = resp.json()
                message = (
                    err_body.get("message")
                    or err_body.get("error", {}).get("message")
                    or resp.text
                )
            except Exception:
                message = resp.text
            raise NebiusHTTPError(
                f"Nebius API {method} {url} returned {resp.status_code}: {message}"
            )
        return resp.json()

    def submit(self, spec: ExperimentSpec, **kwargs: object) -> JobHandle:
        injected_files = [
            {
                "containerPath": "/app/experiment.py",
                "content": base64.b64encode(spec.code.encode("utf-8")).decode("ascii"),
            }
        ]

        platform, preset = self._map_gpu_config()

        env_vars = []
        for key, value in spec.environment.items():
            env_vars.append({"name": key, "value": str(value)})

        env_vars.append({"name": "AXIOM_EXPERIMENT_ID", "value": spec.id})
        env_vars.append({"name": "AXIOM_PLAN_ID", "value": spec.plan_id})

        timeout_seconds = kwargs.get("timeout_seconds")
        if timeout_seconds is None:
            timeout_seconds = 3600
        timeout_str = f"{int(timeout_seconds)}s"

        metadata = {"name": spec.name}
        if self._project_id:
            metadata["parentId"] = self._project_id

        request_body = {
            "metadata": metadata,
            "spec": {
                "image": self._container_image or "nvidia/cuda:13.1.1-runtime-ubuntu24.04",
                "platform": platform,
                "preset": preset,
                "containerCommand": "python3",
                "args": ["/app/experiment.py"],
                "environmentVariables": env_vars,
                "injectedFiles": injected_files,
                "timeout": timeout_str,
                "disk": {
                    "type": "NETWORK_SSD",
                    "sizeBytes": "268435456000",
                },
            },
        }

        if self._artifact_store_uri:
            request_body["spec"]["volumes"] = [
                {
                    "source": self._artifact_store_uri,
                    "containerPath": "/output",
                    "mode": "READ_WRITE",
                }
            ]

        resp = self._request("POST", JOBS_API_PATH, json=request_body)

        job_id = resp.get("metadata", {}).get("id", "")
        if not job_id:
            raise NebiusHTTPError("Nebius API response missing job ID")

        logger.info("Submitted Nebius job %s for spec %s", job_id, spec.id)
        return JobHandle(job_id=job_id, spec_id=spec.id)

    def _map_gpu_config(self) -> tuple[str, str]:
        if self.settings is None:
            return ("gpu-l40s-a", "1gpu-8vcpu-32gb")

        instance_type = getattr(self.settings, "nebius_gpu_instance_type", "gpu_k8s_a100")
        gpu_count = getattr(self.settings, "nebius_gpu_count", 1)

        if instance_type.startswith("gpu-"):
            platform = instance_type
        else:
            platform = "gpu-l40s-a"

        preset = f"{gpu_count}gpu-8vcpu-32gb"
        return (platform, preset)

    def get_status(self, job_id: str) -> JobState:
        resp = self._request("GET", f"{JOBS_API_PATH}/{job_id}")
        state = resp.get("status", {})
        state_str = state.get("state", "STATE_UNSPECIFIED")
        nebius_status = NEBIUS_STATE_MAP.get(state_str, JobStatus.SUBMITTED)

        exit_code = None
        reason = ""
        state_details = state.get("stateDetails", {})
        if state_details:
            code = state_details.get("code", "")
            message = state_details.get("message", "")
            if code:
                reason = f"{code}: {message}".strip()
            elif message:
                reason = message

        container_status = state.get("containerStatus", {})
        if container_status and "exitCode" in container_status:
            exit_code = container_status["exitCode"]

        return JobState(
            status=nebius_status,
            exit_code=exit_code,
            reason=reason,
        )

    def get_logs(self, job_id: str) -> tuple[str, str]:
        raise NotImplementedError(
            "Nebius job log retrieval is not implemented. "
            "The Nebius Serverless AI Jobs REST API does not expose job logs. "
            "Configure a supported log retrieval backend (e.g., Observability Logs API) "
            "or implement a custom NebiusLogProvider."
        )

    def get_artifacts(self, job_id: str) -> JobArtifacts:
        try:
            stdout, stderr = self.get_logs(job_id)
        except NotImplementedError:
            logger.warning(
                "Log retrieval not implemented for job %s; returning empty logs", job_id
            )
            stdout, stderr = "", ""
        except Exception as exc:
            logger.warning("Failed to retrieve logs for job %s: %s", job_id, exc)
            stdout, stderr = "", ""

        state = self.get_status(job_id)
        exit_code = state.exit_code

        artifacts = []

        return JobArtifacts(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            artifacts=artifacts,
        )

    def cancel(self, job_id: str) -> None:
        self._request("POST", f"{JOBS_API_PATH}/cancel", json={"id": job_id})

    def get_artifact_bytes(self, job_id: str, artifact_name: str) -> bytes:
        if not self._artifact_store_uri:
            raise RuntimeError("No artifact store URI configured")

        raise NotImplementedError(
            "Artifact download from Object Storage is not implemented. "
            "Configure an ArtifactStore implementation for S3 access."
        )
