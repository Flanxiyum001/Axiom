"""Audit local submission artifacts without credentials or network access."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "docs/demo-walkthrough.md",
    "docs/hackathon-submission.md",
    "docs/hackathon-readiness.md",
    "docs/tool-feedback.md",
    "frontend/package.json",
    "scripts/smoke_nebius_reasoning.py",
)
EDITABLE_DRAFTS = (
    "docs/hackathon-submission.md",
    "docs/hackathon-readiness.md",
    "docs/tool-feedback.md",
)


def main() -> int:
    print("AXIOM local submission-artifact audit")
    missing = []
    for relative_path in REQUIRED_FILES:
        present = (ROOT / relative_path).is_file()
        print(f"{'present' if present else 'MISSING'}: {relative_path}")
        if not present:
            missing.append(relative_path)

    unresolved_lines = sum(
        "ACTION REQUIRED" in line
        for relative_path in EDITABLE_DRAFTS
        if (ROOT / relative_path).is_file()
        for line in (ROOT / relative_path).read_text(encoding="utf-8").splitlines()
    )
    print(f"Unresolved ACTION REQUIRED lines in editable drafts: {unresolved_lines}")
    print(
        "External checks not performed: demo/test-build URL, public video, "
        "Devpost submission, GitHub license badge, CI, and deployment safety."
    )
    print("Submission readiness: NOT VERIFIED")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
