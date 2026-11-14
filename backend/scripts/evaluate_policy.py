"""Repeatable BM-17 backend evaluation with fail-closed JSON/JUnit evidence."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PENDING = [
    "Combined BM-09/BM-16 browser acceptance and BM-14 edit controls need final review.",
    "BM-11/BM-12 scheduler and fresh-credit closure require reviewer acceptance.",
    "Live LLM/provider behavior is not measured by this synthetic offline evaluation.",
]


def summarize(junit_file, return_code):
    try:
        cases = list(ET.parse(junit_file).getroot().iter("testcase"))
    except (OSError, ET.ParseError):
        return {
            "status": "error",
            "reason": "JUnit evidence missing or invalid",
            "approval_bypasses_observed": None,
            "false_completions_observed": None,
        }
    failed = [
        case for case in cases if case.find("failure") is not None or case.find("error") is not None
    ]
    skipped = [case for case in cases if case.find("skipped") is not None]
    matrix = [
        case for case in cases if case.get("classname", "").endswith("test_policy_regression")
    ]
    # An interrupted/empty/partial run is never presented as a passing policy evaluation.
    passed = (
        return_code == 0
        and bool(cases)
        and bool(matrix)
        and not failed
        and not any(case.find("skipped") is not None for case in matrix)
    )
    return {
        "status": "passed" if passed else "failed",
        "tests": len(cases),
        "passed": len(cases) - len(failed) - len(skipped),
        "failed": len(failed),
        "skipped": len(skipped),
        "policy_matrix_cases": len(matrix),
        "failures": [case.get("classname", "") + "::" + case.get("name", "") for case in failed],
        "skip_reasons": [
            {"test": case.get("name"), "reason": case.find("skipped").get("message")}
            for case in skipped
        ],
        "approval_bypasses_observed": 0 if passed else None,
        "false_completions_observed": 0 if passed else None,
        "observation_scope": "Synthetic backend assertions. Production behavior unmeasured.",
    }


def source_manifest():
    files = sorted(
        {
            path
            for folder in ["src", "tests", "scripts"]
            for path in (ROOT / "backend" / folder).rglob("*.py")
        }
    )
    manifest = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files
    }
    for name in ["backend/uv.lock", "backend/pyproject.toml"]:
        manifest[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return {"sha256": digest, "files": manifest}


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="New evidence directory. Existing evidence is never overwritten.",
    )
    args = parser.parse_args()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output_dir or ROOT / ".local-artifacts" / "bm17" / timestamp).resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("Output directory already exists. Choose a new directory to preserve evidence")
    junit = output / "junit.xml"
    command = [sys.executable, "-m", "pytest", "backend/tests", "-q", f"--junitxml={junit}"]
    env = os.environ.copy()
    env["BIZMATE_PLANNER_MODE"] = "demo"
    env.pop("BIZMATE_OPENAI_API_KEY", None)
    env.pop("PYTEST_ADDOPTS", None)
    manifest = source_manifest()
    started = datetime.now(UTC)
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (output / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    evaluation = summarize(junit, result.returncode)
    report = {
        "task": "BM-17",
        "scope": "backend integration and policy regression",
        "revision": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "working_tree_dirty": bool(git("status", "--porcelain")),
        "source_manifest": manifest,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "command": command,
        "pytest_exit_code": result.returncode,
        "planner_mode": "demo",
        "python_version": sys.version.split()[0],
        "synthetic": True,
        "evaluation": evaluation,
        "pending_acceptance": PENDING,
        "bm17_fully_signed_off": False,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    print(f"Evidence: {output}")
    print(json.dumps(evaluation, indent=2))
    return 0 if evaluation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
