"""
ChipGate evidence-pack output.

Generates a JSON evidence pack that summarizes the verification results
for a scanned design. This pack serves as a reproducible record of what
was checked, what was found, and the overall status.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .scanner import ScanResult
from . import statuses as st


def generate_evidence_pack(
    scan_result: ScanResult,
    include_lint: Optional[Dict] = None,
    include_simulation: Optional[Dict] = None,
    include_formal: Optional[Dict] = None,
    include_safety: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Generate a comprehensive evidence pack from scan results.

    The evidence pack includes:
    - Metadata (timestamp, version, tool info)
    - File and module information
    - All rules checked and their results
    - All findings with severity
    - Status list
    - Risky signals
    - Required gates
    - Optional: lint, simulation, formal, safety analysis results
    - Replay command for deterministic re-verification
    - Certificate hash for integrity
    - Public wording disclaimer
    """
    from . import __version__

    timestamp = datetime.now(timezone.utc).isoformat()

    pack: Dict[str, Any] = {
        "chipgate_version": __version__,
        "timestamp_utc": timestamp,
        "public_wording": st.PUBLIC_WORDING,
        "file": scan_result.file,
        "module_name": scan_result.module_name,
        "statuses": scan_result.statuses,
        "rules_checked": scan_result.rules_checked,
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "description": f.description,
                "line_number": f.line_number,
                "signal_name": f.signal_name,
                "detail": f.detail,
            }
            for f in scan_result.findings
        ],
        "risky_signals": scan_result.risky_signals,
        "required_gates": scan_result.required_gates,
        "replay_command": scan_result.replay_command,
        "certificate_hash": scan_result.certificate_hash,
    }

    # Attach optional results
    if include_lint:
        pack["lint"] = include_lint
    if include_simulation:
        pack["simulation"] = include_simulation
    if include_formal:
        pack["formal"] = include_formal
    if include_safety:
        pack["safety_analysis"] = include_safety

    # Compute evidence pack hash
    pack["evidence_pack_hash"] = hashlib.sha256(
        json.dumps(pack, sort_keys=True).encode()
    ).hexdigest()

    return pack


def save_evidence_pack(
    scan_result: ScanResult,
    output_path: Optional[str] = None,
    include_lint: Optional[Dict] = None,
    include_simulation: Optional[Dict] = None,
    include_formal: Optional[Dict] = None,
    include_safety: Optional[Dict] = None,
) -> str:
    """
    Generate and save an evidence pack to a JSON file.

    Returns the path to the saved file.
    """
    pack = generate_evidence_pack(
        scan_result,
        include_lint=include_lint,
        include_simulation=include_simulation,
        include_formal=include_formal,
        include_safety=include_safety,
    )

    if output_path is None:
        # Generate default path: same directory as scanned file, with .evidence.json suffix
        source = Path(scan_result.file)
        output_path = str(source.parent / f"{source.stem}.evidence.json")

    Path(output_path).write_text(
        json.dumps(pack, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def validate_evidence_pack(pack_path: str) -> Dict[str, Any]:
    """
    Validate an existing evidence pack:
    - Checks that the hash matches the content
    - Checks required fields are present
    - Returns a validation report.
    """
    path = Path(pack_path)
    if not path.exists():
        return {"valid": False, "errors": [f"Evidence pack not found: {pack_path}"]}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"Invalid JSON: {e}"]}

    errors = []
    warnings = []

    # Check required fields
    required_fields = [
        "chipgate_version", "timestamp_utc", "file", "statuses",
        "findings", "rules_checked", "risky_signals", "required_gates",
        "replay_command", "certificate_hash", "public_wording",
    ]
    for field_name in required_fields:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    # Verify hash integrity
    if "certificate_hash" in data and "evidence_pack_hash" in data:
        stored_hash = data.get("evidence_pack_hash", "")
        # Recompute without the hash field itself
        check_data = {k: v for k, v in data.items() if k != "evidence_pack_hash"}
        computed_hash = hashlib.sha256(
            json.dumps(check_data, sort_keys=True).encode()
        ).hexdigest()
        if stored_hash != computed_hash:
            errors.append("Evidence pack hash mismatch — file may have been tampered with.")
    else:
        warnings.append("Hash fields missing — integrity cannot be verified.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }