"""DTL Verified Design Passport — Main Orchestrator.

Provides the high-level pipeline functions that tie together all
passport subsystems: artifact intake, classification, gate execution,
badge determination, report generation, verification, and export.

DTL Verified Design Passport does not prove that a design is safe,
correct, certified, fabrication-ready, commercially validated or
production-ready.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from .passport_schema import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    SCHEMA_VERSION,
)
from .passport_builder import build_passport
from .passport_manifest import (
    load_passport_from_file,
    verify_passport,
)
from .passport_replay import replay_passport
from .passport_badges import generate_badge_json, generate_badge_svg
from .passport_manifest import compute_dict_hash
from .passport_report import (
    generate_passport_json_report,
    generate_passport_html_report,
)
from .passport_export import prepare_handoff_pack
from .passport_examples import (
    DEMO_RTL_SAFE,
    DEMO_ADAPTER_INPUT,
)


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------


def run_passport_pipeline(
    artifact_id: str = "demo_artifact_001",
    file_path: str = "",
    content: str = "",
    adapter_input: Optional[Dict] = None,
    requested_gates: Optional[List[str]] = None,
    output_json: str = "",
    output_html: str = "",
    output_pack: str = "",
) -> Dict[str, Any]:
    """Run the full passport pipeline for a single artifact.

    Steps:
    1. Build passport (intake -> classify -> risk -> gates -> badge)
    2. Generate JSON report if requested
    3. Generate HTML report if requested
    4. Prepare handoff pack if requested

    Returns the complete result dict from build_passport, plus
    any generated report paths.
    """
    result = build_passport(
        artifact_id=artifact_id,
        file_path=file_path,
        content=content,
        adapter_input=adapter_input,
        requested_gates=requested_gates,
    )

    if output_json:
        json_report = generate_passport_json_report(result)
        os.makedirs(os.path.dirname(output_json) if os.path.dirname(output_json) else ".", exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as fh:
            fh.write(json_report)
        result["json_report_path"] = output_json

    if output_html:
        html_report = generate_passport_html_report(result, output_path=output_html)
        result["html_report_path"] = output_html
        result["html_report"] = html_report

    if output_pack:
        passport = result["passport"]
        badge = result["badge"]
        html_path = result.get("html_report_path", "")
        json_path = result.get("json_report_path", "")
        files = prepare_handoff_pack(
            passport, badge, output_pack,
            html_report=html_path,
            json_report=json_path,
        )
        result["handoff_pack"] = files

    return result


def run_demo(output_json: str = "", output_html: str = "") -> Dict[str, Any]:
    """Run a demonstration passport evaluation.

    Uses the built-in demo RTL artifact (safe DTL gate).
    Returns the complete result dict.
    """
    return run_passport_pipeline(
        artifact_id="demo_artifact_001",
        content=DEMO_RTL_SAFE,
        output_json=output_json,
        output_html=output_html,
    )


def verify_passport_file(file_path: str) -> Dict[str, Any]:
    """Load and verify a passport from a JSON file.

    Returns:
        Dict with verification result plus replay status.
    """
    passport_data = load_passport_from_file(file_path)
    if not passport_data:
        return {
            "replay_match": False,
            "replay_status": "PASSPORT_REPLAY_DRIFT",
            "error": "Could not load passport from file",
        }

    verification = verify_passport(passport_data)
    replay = replay_passport(passport_data)

    return {
        "replay_match": replay["replay_match"],
        "replay_status": replay["replay_status"],
        "certificate_match": replay["certificate_match"],
        "verification": verification,
        "errors": replay["errors"],
    }


def export_badge_for_passport(
    passport_file: str,
    output_dir: str = "",
) -> Dict[str, Any]:
    """Export badge files for a passport.

    Loads the passport, generates badge JSON and SVG, writes to
    output_dir.

    Returns the badge dict plus file paths.
    """
    passport_data = load_passport_from_file(passport_file)
    if not passport_data:
        return {"error": "Could not load passport from file"}

    badge_type = passport_data.get("badge", "UNVERIFIED")
    artifact_id = passport_data.get("artifact_id", "")

    passport_hash = compute_dict_hash({
        "passport_id": passport_data.get("passport_id", ""),
        "artifact_id": artifact_id,
        "badge": badge_type,
    })

    badge_json = generate_badge_json(artifact_id, badge_type, "Exported badge", passport_hash)
    badge_svg = generate_badge_svg(badge_type, artifact_id)

    result: Dict[str, Any] = badge_json.copy()
    result["svg_content"] = badge_svg

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "BADGE.json")
        svg_path = os.path.join(output_dir, "BADGE.svg")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(badge_json, fh, indent=2)
        with open(svg_path, "w", encoding="utf-8") as fh:
            fh.write(badge_svg)
        result["json_path"] = json_path
        result["svg_path"] = svg_path

    return result


def run_replay_for_artifact(
    artifact_id: str = "replay_001",
    file_path: str = "",
    content: str = "",
    adapter_input: Optional[Dict] = None,
    requested_gates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a passport and immediately replay it.

    Returns the build result plus replay status.
    """
    result = build_passport(
        artifact_id=artifact_id,
        file_path=file_path,
        content=content,
        adapter_input=adapter_input,
        requested_gates=requested_gates,
    )

    passport = result["passport"]
    replay = replay_passport(passport)
    result["replay"] = replay

    return result
