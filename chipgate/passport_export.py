"""DTL Verified Design Passport — Export Decision Engine.

Handles export policy application and handoff pack generation.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .passport_schema import (
    PASSPORT_PUBLIC_WORDING,
    PASSPORT_LIMITATION,
    SCHEMA_VERSION,
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
)
from .passport_manifest import compute_hash, save_passport_to_file
from .passport_badges import generate_badge_json, generate_badge_svg, determine_badge


# ---------------------------------------------------------------------------
# Handoff pack generation
# ---------------------------------------------------------------------------


def prepare_handoff_pack(
    passport_data: Dict[str, Any],
    badge_data: Dict[str, str],
    output_dir: str,
    html_report: str = "",
    json_report: str = "",
) -> Dict[str, str]:
    """Prepare a handoff pack directory with all passport artifacts.

    Creates the following structure::

        design_passport_pack/
          README_DESIGN_PASSPORT.md
          PASSPORT_SUMMARY.md
          PASSPORT_SCHEMA.json
          PASSPORT.json
          BADGE.json
          BADGE.svg
          EVIDENCE_MANIFEST.json
          REPLAY_COMMANDS.md
          LIMITATIONS.md
          reports/

    Returns a dict mapping file names to their absolute paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    reports_dir = os.path.join(output_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    files_created: Dict[str, str] = {}

    def _write(name: str, content: str, subdir: str = "") -> str:
        path = os.path.join(output_dir, subdir, name) if subdir else os.path.join(output_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        files_created[name] = path
        return path

    # README
    _write("README_DESIGN_PASSPORT.md", _render_readme(passport_data))

    # Summary
    _write("PASSPORT_SUMMARY.md", _render_summary(passport_data, badge_data))

    # Schema
    schema_content = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "type": "design_passport",
        "description": "DTL Verified Design Passport schema",
    }, indent=2)
    _write("PASSPORT_SCHEMA.json", schema_content)

    # Passport
    passport_json = json.dumps(passport_data, indent=2, sort_keys=True)
    _write("PASSPORT.json", passport_json)

    # Badge JSON
    badge_json = json.dumps(badge_data, indent=2, sort_keys=True)
    _write("BADGE.json", badge_json)

    # Badge SVG
    badge_type = badge_data.get("badge", "UNVERIFIED")
    artifact_id = badge_data.get("artifact_id", "")
    svg = generate_badge_svg(badge_type, artifact_id)
    _write("BADGE.svg", svg)

    # Evidence manifest
    evidence_manifest = {
        "passport_id": passport_data.get("passport_id", ""),
        "artifact_id": passport_data.get("artifact_id", ""),
        "evidence_packs": passport_data.get("evidence_packs", []),
        "artifact_hashes": passport_data.get("artifact_hashes", {}),
    }
    _write("EVIDENCE_MANIFEST.json", json.dumps(evidence_manifest, indent=2))

    # Replay commands
    _write("REPLAY_COMMANDS.md", _render_replay_commands(passport_data))

    # Limitations
    _write("LIMITATIONS.md", _render_limitations())

    # Reports
    if html_report and os.path.isfile(html_report):
        import shutil
        shutil.copy2(html_report, os.path.join(reports_dir, "_report.html"))
        files_created["reports/_report.html"] = os.path.join(reports_dir, "_report.html")
    if json_report and os.path.isfile(json_report):
        import shutil
        shutil.copy2(json_report, os.path.join(reports_dir, "_report.json"))
        files_created["reports/_report.json"] = os.path.join(reports_dir, "_report.json")

    return files_created


# ---------------------------------------------------------------------------
# Internal renderers
# ---------------------------------------------------------------------------


def _render_readme(passport_data: Dict[str, Any]) -> str:
    """Render the README for the handoff pack."""
    pid = passport_data.get("passport_id", "")
    aid = passport_data.get("artifact_id", "")
    atype = passport_data.get("artifact_type", "")
    status = passport_data.get("passport_status", "")
    export = passport_data.get("export_decision", "")
    return f"""# DTL Verified Design Passport — Handoff Pack

## Passport ID
{pid}

## Artifact
- ID: {aid}
- Type: {atype}

## Status
- Passport Status: {status}
- Export Decision: {export}

## Contents
- `PASSPORT.json` — Full passport data
- `BADGE.json` — Badge status
- `BADGE.svg` — Badge image
- `EVIDENCE_MANIFEST.json` — Evidence pack references
- `REPLAY_COMMANDS.md` — Replay instructions
- `LIMITATIONS.md` — Limitations and disclaimers
- `reports/` — Generated reports

{PASSPORT_LIMITATION}
"""


def _render_summary(passport_data: Dict[str, Any], badge_data: Dict[str, str]) -> str:
    """Render the passport summary markdown."""
    pid = passport_data.get("passport_id", "")
    aid = passport_data.get("artifact_id", "")
    atype = passport_data.get("artifact_type", "")
    risk = passport_data.get("risk_level", "")
    status = passport_data.get("passport_status", "")
    export = passport_data.get("export_decision", "")
    badge = badge_data.get("badge", "")
    reason = badge_data.get("reason", "")
    gates_passed = passport_data.get("gates_passed", [])
    gates_failed = passport_data.get("gates_failed", [])
    review_items = passport_data.get("manual_review_items", [])
    return f"""# Passport Summary

| Field | Value |
|-------|-------|
| Passport ID | {pid} |
| Artifact ID | {aid} |
| Artifact Type | {atype} |
| Risk Level | {risk} |
| Passport Status | {status} |
| Export Decision | {export} |
| Badge | {badge} |
| Badge Reason | {reason} |

## Gates Passed
{chr(10).join(f'- {g}' for g in gates_passed) if gates_passed else '- None'}

## Gates Failed
{chr(10).join(f'- {g}' for g in gates_failed) if gates_failed else '- None'}

## Manual Review Items
{chr(10).join(f'- {item}' for item in review_items) if review_items else '- None'}

{PASSPORT_LIMITATION}
"""


def _render_replay_commands(passport_data: Dict[str, Any]) -> str:
    """Render replay commands documentation."""
    cmd = passport_data.get("replay_command", "")
    pid = passport_data.get("passport_id", "")
    return f"""# Replay Commands

## Replay This Passport

To replay this passport verification:

```bash
{cmd}
```

## Verify Passport Integrity

```bash
python -m chipgate passport --verify-passport <path-to-passport.json>
```

## Export Badge

```bash
python -m chipgate passport --export-badge
```

Passport ID: {pid}

{PASSPORT_LIMITATION}
"""


def _render_limitations() -> str:
    """Render the limitations document."""
    return f"""# Limitations

{PASSPORT_LIMITATION}

## What This Passport Does NOT Prove

- Design correctness
- Fabrication readiness
- Timing closure
- Physical safety
- Commercial viability
- Medical safety
- Defence safety
- Robotics safety
- Real-world actuator safety
- Independent validation
- Production readiness
- Deployment suitability

## What This Passport Records

- What was checked (configured gates)
- What passed
- What failed
- What evidence exists
- What replay command can reproduce the decision
- Whether export/build/simulation should be allowed, blocked or sent to review

## Important

This passport is a structured verification record.  It is not a certification.
Badge states are labels only and do not constitute safety guarantees.
"""
