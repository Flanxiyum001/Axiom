"""Example experiment: batch-size lever on the synthetic CPU benchmark.

Runnable standalone:

    AXIOM_LEVER_MODE=baseline python experiments/examples/batch_size_latency.py

Emits the AXIOM metrics protocol JSON as the last stdout line.
"""

import json
import os
import time

METRIC = "latency_ms"
MODE = os.environ.get("AXIOM_LEVER_MODE", "baseline")

BASE_TICKS = 400_000
if MODE == "candidate":
    ticks = 240_000  # simulated batched inference path
else:
    ticks = BASE_TICKS

samples = []
for i in range(3):
    start = time.perf_counter()
    acc = 0
    x = 1
    for _ in range(ticks):
        acc = (acc * 31 + x) % 1_000_003
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    samples.append(elapsed_ms)
    print(f"iter {i}: {elapsed_ms:.3f} ms", flush=True)

print(
    json.dumps(
        {
            "metrics": [
                {"name": METRIC, "value": v, "unit": "ms", "iteration": i}
                for i, v in enumerate(samples)
            ]
        }
    )
)
