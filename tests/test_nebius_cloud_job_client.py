"""Tests for RealNebiusJobClient using mocked HTTP transport."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from axiom.config import Settings
from axiom.domain.models import ExperimentSpec
from axiom.execution.nebius_auth import StaticTokenProvider
from axiom.execution.nebius_cloud_job_client import RealNebiusJobClient, NebiusHTTPError
from axiom.execution.nebius_job_client import JobStatus


def make_spec() -> ExperimentSpec:
    return ExperimentSpec(
        plan_id="plan_1",
        name="test_exp",
        description="Test experiment",
        code="print('hello')\nprint('{\"metrics\": []}')",
        environment={"KEY": "value"},
    )


def make_client(settings: Settings | None = None, **kwargs) -> RealNebiusJobClient:
    auth = StaticTokenProvider("test-token")
    return RealNebiusJobClient(
        settings=settings,
        auth_provider=auth,
        base_url="https://api.nebius.cloud",
        **kwargs,
    )


def test_real_client_implements_job_client():
    client = make_client()
    from axiom.execution.nebius_job_client import NebiusJobClient
    assert isinstance(client, NebiusJobClient)


def test_submit_builds_correct_job_request():
    settings = Settings(
        nebius_gpu_instance_type="gpu-l40s-a",
        nebius_gpu_count=1,
        nebius_container_image="nvidia/cuda:13.1.1-runtime-ubuntu24.04",
    )
    client = make_client(settings=settings)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/ai/v1/jobs"
        assert request.headers["Authorization"] == "Bearer test-token"
        body = json.loads(request.content)
        assert body["metadata"]["name"] == "test_exp"
        assert body["spec"]["image"] == "nvidia/cuda:13.1.1-runtime-ubuntu24.04"
        assert body["spec"]["platform"] == "gpu-l40s-a"
        assert body["spec"]["preset"] == "1gpu-8vcpu-32gb"
        assert body["spec"]["containerCommand"] == "python3"
        assert body["spec"]["args"] == ["/app/experiment.py"]
        injected = body["spec"]["injectedFiles"][0]
        assert injected["containerPath"] == "/app/experiment.py"
        decoded = base64.b64decode(injected["content"]).decode("utf-8")
        assert "print('hello')" in decoded
        env_names = [e["name"] for e in body["spec"]["environmentVariables"]]
        assert "KEY" in env_names
        assert "AXIOM_EXPERIMENT_ID" in env_names
        return httpx.Response(200, json={"metadata": {"id": "job-123"}})

    transport = httpx.MockTransport(mock_handler)
    client._http_client = httpx.Client(transport=transport)

    spec = make_spec()
    handle = client.submit(spec, timeout_seconds=120)
    assert handle.job_id == "job-123"
    assert handle.spec_id == spec.id

