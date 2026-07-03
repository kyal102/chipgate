"""Command-line interface for ChipGate Lite.

Usage:
    python -m chipgate design.v [more.v ...]   check Verilog files
    python -m chipgate --demo                  run on the bundled examples
    python -m chipgate --json design.v         machine-readable report
    python -m chipgate --schema-demo           print the DesignGuard
                                               request/response schema demo

Exit codes: 0 = CHIPGATE_PASS, 1 = CHIPGATE_FAIL, 2 = CHIPGATE_NEEDS_REVIEW.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from chipgate.rtl_check import check_file, exit_code, format_report

_EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="chipgate",
        description="ChipGate Lite: deterministic structural sanity checks for Verilog RTL.",
    )
    parser.add_argument("files", nargs="*", help="Verilog source files to check")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--demo", action="store_true", help="check the bundled example files")
    parser.add_argument("--schema-demo", action="store_true",
                        help="print the JARVI3 DesignGuard request/response schema demo")
    args = parser.parse_args(argv)

    if args.schema_demo:
        from designguard_lite import run_lite_demo
        print(json.dumps(run_lite_demo(), indent=2))
        return 0

    files = list(args.files)
    if args.demo:
        files += [
            os.path.join(_EXAMPLES_DIR, "good_counter.v"),
            os.path.join(_EXAMPLES_DIR, "bad_alu.v"),
        ]
    if not files:
        parser.print_help()
        return 0

    worst = 0
    reports = []
    for path in files:
        report = check_file(path)
        reports.append(report)
        if not args.json:
            print(format_report(report))
            print()
        code = exit_code(report)
        if code == 1 or (code == 2 and worst != 1):
            worst = code
    if args.json:
        print(json.dumps(reports if len(reports) > 1 else reports[0], indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
