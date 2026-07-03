"""
ChipGate formal-verification evidence-pack output.

Generates a JSON evidence pack that summarises the formal verification
results for a scanned design. This pack serves as a reproducible record of
what was checked, which properties passed or failed, the toolchain that was
used, and the overall formal status.

Does not guarantee silicon correctness, fabrication readiness, timing
signoff, physical safety, real power or real area.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


BENCHMARK_NAME = "ChipGate"
BENCHMARK_VERSION = "0.1.0"
PUBLIC_WORDING = (
    "ChipGate is a model-free benchmark that checks RTL structure and "
    "verification-gated safety patterns. "
    "It does not guarantee hardware correctness, silicon readiness, physical safety, "
    "regulatory conformance or experimental validity."
)


@dataclass
class FormalEvidenceRecord:
    """Evidence record for a formal verification run."""

    benchmark_name: str = ""
    benchmark_version: str = ""
    design_id: str = ""
    rtl_hash: str = ""
    property_name: str = ""
    property_hash: str = ""
    formal_tool: str = ""
    formal_tool_version: str = ""
    formal_result: str = ""
    certificate_hash: str = ""
    public_wording: str = ""

    def to_dict(self) -> dict:
        return {
            "benchmark_name": self.benchmark_name,
            "benchmark_version": self.benchmark_version,
            "design_id": self.design_id,
            "rtl_hash": self.rtl_hash,
            "property_name": self.property_name,
            "property_hash": self.property_hash,
            "formal_tool": self.formal_tool,
            "formal_tool_version": self.formal_tool_version,
            "formal_result": self.formal_result,
            "certificate_hash": self.certificate_hash,
            "public_wording": self.public_wording,
        }


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _sha256_string(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_file(path: str) -> str:
    """Return the SHA-256 hex digest of a file's contents, or empty string."""
    p = Path(path)
    if not p.exists():
        return ""
    return _sha256_bytes(p.read_bytes())


def _extract_formal_tool_info(toolchain_status: dict) -> tuple:
    """Extract formal tool name and version from toolchain status dict.

    Returns:
        Tuple of (tool_name, tool_version).
    """
    if not toolchain_status:
        return ("", "")
    for tool_name in ("sby", "symbiyosys", "yosys"):
        info = toolchain_status.get(tool_name)
        if info and isinstance(info, dict) and info.get("found"):
            return (tool_name, info.get("version", ""))
    # Fallback: scan all entries for anything formal-related
    for name, info in toolchain_status.items():
        if isinstance(info, dict) and info.get("found"):
            version = info.get("version", "")
            if version:
                return (name, version)
    return ("", "")


def _formal_result_to_string(formal_result) -> str:
    """Normalise a formal result object to a status string.

    Accepts FormalResult, FormalPropertyResult, or a plain dict with a
    ``status`` / ``passed`` key.
    """
    if formal_result is None:
        return ""
    # dataclass with .status attribute (FormalResult)
    if hasattr(formal_result, "status"):
        return str(formal_result.status)
    # dataclass with .passed attribute (FormalPropertyResult)
    if hasattr(formal_result, "passed"):
        return "PASS" if formal_result.passed else "FAIL"
    # dict
    if isinstance(formal_result, dict):
        if "status" in formal_result:
            return str(formal_result["status"])
        if "passed" in formal_result:
            return "PASS" if formal_result["passed"] else "FAIL"
    return str(formal_result)


def _formal_result_to_output(formal_result) -> str:
    """Extract the output / evidence text from a formal result object."""
    if formal_result is None:
        return ""
    if hasattr(formal_result, "output"):
        return formal_result.output or ""
    if isinstance(formal_result, dict):
        return formal_result.get("output", "")
    return ""


def _build_certificate_hash(
    rtl_hash: str,
    property_name: str,
    formal_result_str: str,
    formal_output: str,
    toolchain_status: dict,
) -> str:
    """Build the certificate hash from formal result output.

    The certificate hash is computed over the formal verification output
    (not the design file) together with the RTL hash and property name
    to bind the certificate to a specific design + property + result.
    """
    tool_name, tool_version = _extract_formal_tool_info(toolchain_status)
    payload = json.dumps(
        {
            "rtl_hash": rtl_hash,
            "property_name": property_name,
            "formal_result": formal_result_str,
            "formal_output": formal_output,
            "formal_tool": tool_name,
            "formal_tool_version": tool_version,
        },
        sort_keys=True,
    )
    return _sha256_string(payload)


def _build_property_hash(property_name: str, design_id: str) -> str:
    """Build a deterministic hash for a property within a design."""
    payload = json.dumps(
        {"property_name": property_name, "design_id": design_id},
        sort_keys=True,
    )
    return _sha256_string(payload)


def create_formal_evidence(
    design_path: str,
    formal_result,
    property_results: list = None,
    toolchain_status: dict = None,
    commit_sha: str = "",
    workflow_name: str = "",
    run_id: str = "",
    work_dir: str = "",
) -> Dict[str, Any]:
    """
    Create a formal evidence pack.

    Args:
        design_path: Path to the RTL file.
        formal_result: FormalPropertyResult or FormalResult.
        property_results: List of per-property FormalPropertyResult dicts.
        toolchain_status: Dict from detect_toolchain().
        commit_sha: Git commit SHA (empty if unavailable).
        workflow_name: CI workflow name.
        run_id: CI run ID.
        work_dir: Working directory path.
    """
    if property_results is None:
        property_results = []
    if toolchain_status is None:
        toolchain_status = {}

    timestamp = datetime.now(timezone.utc).isoformat()
    design_p = Path(design_path)
    design_id = design_p.stem if design_p.exists() else os.path.basename(design_path)
    rtl_hash = _hash_file(design_path)

    formal_result_str = _formal_result_to_string(formal_result)
    formal_output = _formal_result_to_output(formal_result)
    tool_name, tool_version = _extract_formal_tool_info(toolchain_status)

    # Build per-property evidence records
    records: List[Dict[str, Any]] = []
    if property_results:
        for pr in property_results:
            pr_dict = pr if isinstance(pr, dict) else (pr.to_dict() if hasattr(pr, "to_dict") else {})
            prop_name = pr_dict.get("property_name", "")
            prop_hash = _build_property_hash(prop_name, design_id)
            prop_result_str = _formal_result_to_string(pr)
            prop_output = _formal_result_to_output(pr)
            cert_hash = _build_certificate_hash(
                rtl_hash=rtl_hash,
                property_name=prop_name,
                formal_result_str=prop_result_str,
                formal_output=prop_output,
                toolchain_status=toolchain_status,
            )
            record = FormalEvidenceRecord(
                benchmark_name=BENCHMARK_NAME,
                benchmark_version=BENCHMARK_VERSION,
                design_id=design_id,
                rtl_hash=rtl_hash,
                property_name=prop_name,
                property_hash=prop_hash,
                formal_tool=tool_name,
                formal_tool_version=tool_version,
                formal_result=prop_result_str,
                certificate_hash=cert_hash,
                public_wording=PUBLIC_WORDING,
            )
            records.append(record.to_dict())

    # If no per-property records, build one aggregate record from formal_result
    if not records:
        aggregate_prop_name = "aggregate"
        aggregate_cert_hash = _build_certificate_hash(
            rtl_hash=rtl_hash,
            property_name=aggregate_prop_name,
            formal_result_str=formal_result_str,
            formal_output=formal_output,
            toolchain_status=toolchain_status,
        )
        aggregate_record = FormalEvidenceRecord(
            benchmark_name=BENCHMARK_NAME,
            benchmark_version=BENCHMARK_VERSION,
            design_id=design_id,
            rtl_hash=rtl_hash,
            property_name=aggregate_prop_name,
            property_hash=_build_property_hash(aggregate_prop_name, design_id),
            formal_tool=tool_name,
            formal_tool_version=tool_version,
            formal_result=formal_result_str,
            certificate_hash=aggregate_cert_hash,
            public_wording=PUBLIC_WORDING,
        )
        records.append(aggregate_record.to_dict())

    # Determine overall status
    if hasattr(formal_result, "status"):
        overall_status = str(formal_result.status)
    elif hasattr(formal_result, "passed"):
        overall_status = "PASS" if formal_result.passed else "FAIL"
    elif isinstance(formal_result, dict):
        overall_status = str(formal_result.get("status", formal_result.get("passed", "")))
    else:
        overall_status = str(formal_result) if formal_result else "UNKNOWN"

    evidence: Dict[str, Any] = {
        "timestamp_utc": timestamp,
        "design_path": str(design_path),
        "design_id": design_id,
        "rtl_hash": rtl_hash,
        "overall_status": overall_status,
        "formal_tool": tool_name,
        "formal_tool_version": tool_version,
        "toolchain_status": toolchain_status,
        "commit_sha": commit_sha,
        "workflow_name": workflow_name,
        "run_id": run_id,
        "work_dir": work_dir,
        "public_wording": PUBLIC_WORDING,
        "evidence_records": records,
        "evidence_records_count": len(records),
    }

    # Compute evidence pack hash (excluding the hash field itself)
    evidence["evidence_pack_hash"] = _sha256_string(
        json.dumps(
            {k: v for k, v in evidence.items() if k != "evidence_pack_hash"},
            sort_keys=True,
            default=str,
        )
    )

    return evidence


def save_formal_evidence(
    evidence: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """
    Save a formal evidence pack to a JSON file.

    Args:
        evidence: Dict from create_formal_evidence().
        output_path: Optional file path. Defaults to <design_id>.formal_evidence.json.

    Returns:
        The path to the saved file.
    """
    if output_path is None:
        design_id = evidence.get("design_id", "formal")
        if not design_id:
            design_id = "formal"
        output_path = f"{design_id}.formal_evidence.json"

    p = Path(output_path)
    p.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return str(p)


def validate_formal_evidence_pack(pack_path: str) -> Dict[str, Any]:
    """
    Validate an existing formal evidence pack:
    - Checks that the evidence pack hash matches the content.
    - Checks required fields are present.
    - Returns a validation report.
    """
    path = Path(pack_path)
    if not path.exists():
        return {"valid": False, "errors": [f"Evidence pack not found: {pack_path}"]}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"Invalid JSON: {e}"]}

    errors: List[str] = []
    warnings: List[str] = []

    # Check required fields
    required_fields = [
        "timestamp_utc",
        "design_path",
        "design_id",
        "rtl_hash",
        "overall_status",
        "formal_tool",
        "public_wording",
        "evidence_records",
        "evidence_pack_hash",
    ]
    for field_name in required_fields:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    # Verify evidence pack hash integrity
    if "evidence_pack_hash" in data:
        stored_hash = data["evidence_pack_hash"]
        check_data = {k: v for k, v in data.items() if k != "evidence_pack_hash"}
        computed_hash = _sha256_string(
            json.dumps(check_data, sort_keys=True, default=str)
        )
        if stored_hash != computed_hash:
            errors.append(
                "Evidence pack hash mismatch — file may have been tampered with."
            )
    else:
        warnings.append("evidence_pack_hash field missing — integrity cannot be verified.")

    # Validate individual evidence records
    for idx, record in enumerate(data.get("evidence_records", [])):
        record_required = [
            "benchmark_name", "benchmark_version", "design_id", "rtl_hash",
            "property_name", "property_hash", "formal_tool", "formal_tool_version",
            "formal_result", "certificate_hash", "public_wording",
        ]
        for rf in record_required:
            if rf not in record:
                errors.append(f"Evidence record {idx}: missing required field: {rf}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def get_formal_evidence_packs(ci_data: Dict) -> list:
    """Extract formal evidence records from CI data.

    Scans the stages list in *ci_data* for entries whose stage name contains
    "formal" and returns their evidence / artifacts information.

    Args:
        ci_data: CI result dict containing a ``stages`` key.

    Returns:
        List of evidence-related dicts extracted from formal stages.
    """
    packs: list = []
    for stage in ci_data.get("stages", []):
        stage_name = stage.get("stage_name", "")
        if "formal" not in stage_name.lower():
            continue
        pack: Dict[str, Any] = {
            "stage": stage_name,
            "status": stage.get("status", ""),
        }
        if stage.get("artifacts"):
            pack["artifacts"] = stage["artifacts"]
        if stage.get("output"):
            pack["output"] = stage["output"]
        if stage.get("evidence_records"):
            pack["evidence_records"] = stage["evidence_records"]
        packs.append(pack)
    return packs
