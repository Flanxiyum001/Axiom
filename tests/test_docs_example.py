"""The worked example stays runnable against the current codebase."""

import os
import subprocess
import sys


def test_end_to_end_example_runs():
    """The example script exits zero and prints a benchmark report."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script = os.path.join(repo_root, "experiments", "examples", "end_to_end_benchmark.py")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(repo_root, "backend")
    completed = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=repo_root,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert "Benchmark: example_benchmark" in completed.stdout
    assert "Cases: 2" in completed.stdout
