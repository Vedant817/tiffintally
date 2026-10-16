"""Record actual offline checks in a disposable clean clone of HEAD."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    phase = sys.argv[1]
    root = Path(__file__).resolve().parents[1]
    python = str(Path(sys.executable).resolve())
    ruff = str(Path(python).parent / ("ruff.exe" if os.name == "nt" else "ruff"))
    clone = Path(tempfile.mkdtemp(prefix="tiffintally-qa-")) / "repo"
    subprocess.run(
        ["git", "clone", "--local", str(root), str(clone)], check=True, capture_output=True
    )
    installation = None
    if phase == "final":
        installation = subprocess.run(
            ["uv", "sync", "--frozen", "--all-extras", "--dev", "--link-mode", "hardlink"],
            cwd=clone,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if installation.returncode:
            print(installation.stdout + installation.stderr)
            return installation.returncode
        executable_directory = clone / ".venv" / ("Scripts" if os.name == "nt" else "bin")
        python = str(executable_directory / ("python.exe" if os.name == "nt" else "python"))
        ruff = str(executable_directory / ("ruff.exe" if os.name == "nt" else "ruff"))
    env = dict(
        os.environ,
        EXTRACTOR_BACKEND="off",
        TIFFINTALLY_TELEMETRY="0",
        TELEMETRY_LOG=str(clone.parent / "telemetry.jsonl"),
    )
    commands = [
        [ruff, "check", "."],
        [ruff, "format", "--check", "."],
        [python, "-m", "pytest", "-q"],
        [python, "scripts/check_claims.py"],
    ]
    if phase in {"phase2", "final"}:
        commands += [
            [
                python,
                "-m",
                "pytest",
                "tests/test_daily_invariants.py",
                "-q",
                f"--hypothesis-seed={seed}",
            ]
            for seed in (0, 1, 42, 271)
        ]
    if phase in {"phase4", "phase5", "phase6", "final"}:
        commands += [
            [python, "-m", "tiffintally.cli", "eval", "--out", str(clone.parent / "offline-eval")],
            [python, "scripts/leakage_report.py", "--check-known"],
            [
                python,
                "scripts/compare.py",
                "evals/final/regex/test.jsonl",
                "evals/final/regex/test.jsonl",
            ],
            [python, "scripts/publish_results.py", "--check"],
        ]
    if phase in {"phase5", "phase6", "final"}:
        commands += [
            [
                python,
                "scripts/run_baselines.py",
                "--system",
                system,
                "--out",
                str(clone.parent / "baseline-qa"),
            ]
            for system in ("regex", "hybrid", "adapter")
        ]
    lines = [
        f"# {phase}: clean-clone QA",
        "",
        f"Clone: `{clone}`",
        "",
        "Original auditor probe sources: NOT SUPPLIED. Reconstructed probes are identified in tests/probes/README.md.",
        "",
    ]
    if installation:
        lines += [
            "## PASS: uv sync --frozen --all-extras --dev --link-mode hardlink",
            "",
            "```text",
            installation.stdout + installation.stderr,
            "```",
            "",
        ]
    passed = True
    for command in commands:
        result = subprocess.run(
            command,
            cwd=clone,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines += [
            f"## {'PASS' if result.returncode == 0 else 'FAIL'}: {' '.join(command)}",
            "",
            "```text",
            result.stdout + result.stderr,
            "```",
            "",
        ]
        passed &= result.returncode == 0
    lines += [
        "Executed checks: " + ("PASS" if passed else "FAIL"),
        "",
        "This is a separate QA pass by the same agent, not an independent human review. "
        "Missing original probes and human acceptance items are not certified by these commands.",
    ]
    destination = root / "evidence" / f"{phase}-qa.md"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(destination, "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
