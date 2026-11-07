"""Elevated ETW session helper launched only when the ETW source is enabled."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import psutil


def _run(command: list[str]) -> None:
    result = subprocess.run(
        command, capture_output=True, text=True, check=False, timeout=15)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def run_etw_helper(
    session: str,
    provider_file: str,
    etl_path: str,
    ready_file: str,
    stop_file: str,
    result_file: str,
    parent_pid: int,
) -> int:
    created = False
    started = False
    errors = []
    try:
        _run([
            "logman", "create", "trace", session, "-o", etl_path,
            "-f", "bincirc", "-max", "16", "-ul", "-rt", "-pf", provider_file,
        ])
        created = True
        _run(["logman", "start", session, "-ets"])
        started = True
        with open(ready_file, "w", encoding="utf-8") as status:
            status.write("READY")

        while not os.path.exists(stop_file) and psutil.pid_exists(parent_pid):
            time.sleep(0.1)
    except Exception as exc:
        errors.append(str(exc))
        with open(ready_file, "w", encoding="utf-8") as status:
            status.write(f"ERROR\n{exc}")
    finally:
        if started:
            try:
                _run(["logman", "stop", session, "-ets"])
            except Exception as exc:
                errors.append(str(exc))
        if created:
            try:
                _run(["logman", "delete", session])
            except Exception as exc:
                errors.append(str(exc))
        with open(result_file, "w", encoding="utf-8") as status:
            status.write("\n".join(errors))
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--providers", required=True)
    parser.add_argument("--etl", required=True)
    parser.add_argument("--ready", required=True)
    parser.add_argument("--stop", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--parent-pid", required=True, type=int)
    args = parser.parse_args(argv)
    return run_etw_helper(
        args.session, args.providers, args.etl, args.ready,
        args.stop, args.result, args.parent_pid)


if __name__ == "__main__":
    sys.exit(main())
