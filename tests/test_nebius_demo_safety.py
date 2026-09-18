import subprocess
import sys
import os
from pathlib import Path

def _run_script(script_path: Path, env: dict) -> subprocess.CompletedProcess:
    """Run a Python script in a subprocess with given environment.
    Returns the CompletedProcess for inspection.
    """
    return subprocess.run([sys.executable, str(script_path)], env=env, capture_output=True, text=True)


def test_nebius_smoke_test_fails_safely_when_credentials_missing(tmp_path: Path) -> None:
    # Ensure NEBIUS env vars are not set
    env = os.environ.copy()
    for var in ["NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL"]:
        env.pop(var, None)
    script = Path(__file__).parents[1] / "experiments" / "examples" / "nebius_smoke_test.py"
    result = _run_script(script, env)
    # Should exit with code 0 and contain the missing env message
    assert result.returncode == 0
    assert "Nebius smoke test not configured" in result.stdout


def test_nebius_research_demo_fails_safely_when_credentials_missing(tmp_path: Path) -> None:
    env = os.environ.copy()
    for var in ["NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL"]:
        env.pop(var, None)
    script = Path(__file__).parents[1] / "experiments" / "examples" / "nebius_research_demo.py"
    result = _run_script(script, env)
    # The demo should exit early with code 0 and print missing env message
    assert result.returncode == 0
    assert "Nebius demo not configured" in result.stdout
