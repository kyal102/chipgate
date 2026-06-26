"""Command-line entry point for JARVI3 Chip DesignGuard Lite."""

from __future__ import annotations

import json

from designguard_lite import run_lite_demo


def main() -> None:
    demo = run_lite_demo()
    print(json.dumps(demo, indent=2))


if __name__ == "__main__":
    main()
