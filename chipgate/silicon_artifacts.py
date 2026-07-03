"""
ChipGate SiliconReadinessBench artifact hashing and evidence.

For each tool stage, hashes:
  - input RTL
  - generated netlist (if available)
  - report text
  - command used
  - tool version (if available)

Each design creates a reproducible evidence record with SHA-256 hashes.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, statuses as st


def _sha256(text: str) -> str:
    """Compute SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_artifact(
    content: str,
    label: str,
) -> Dict[str, str]:
    """
    Hash a single artifact and return a record.

    Returns:
        {"label": <label>, "sha256": <hash>}
    """
    return {
        "label": label,
        "sha256": _sha256(content),
    }


def hash_design_artifacts(
    rtl_text: str,
    netlist_text: str = "",
    report_text: str = "",
    command: str = "",
    tool_version: str = "",
) -> List[Dict[str, str]]:
    """
    Hash all available artifacts for a single design.

    Returns a list of hash records.
    """
    artifacts = []
    artifacts.append(hash_artifact(rtl_text, "rtl_input"))
    if netlist_text:
        artifacts.append(hash_artifact(netlist_text, "netlist"))
    if report_text:
        artifacts.append(hash_artifact(report_text, "report"))
    if command:
        artifacts.append(hash_artifact(command, "command"))
    if tool_version:
        artifacts.append(hash_artifact(tool_version, "tool_version"))
    return artifacts


def compute_evidence_hash(evidence: Dict[str, Any]) -> str:
    """
    Compute a certificate hash over an entire evidence record.
    Excludes the 'certificate_hash' field itself.
    """
    check_data = {k: v for k, v in evidence.items() if k != "certificate_hash"}
    return _sha256(json.dumps(check_data, sort_keys=True, default=str))


@dataclass
class SiliconEvidenceRecord:
    """
    Evidence record for a single SiliconReadinessBench design.
    """
    benchmark_name: str = "siliconbench_v0"
    benchmark_version: str = ""
    design_id: str = ""
    rtl_hash: str = ""
    chipgate_safety_result: str = ""
    lint_result: str = ""
    synthesis_result: str = ""
    formal_result: str = ""
    fpga_flow_result: str = ""
    asic_flow_result: str = ""
    tool_versions: Dict[str, Optional[str]] = field(default_factory=dict)
    artifact_hashes: List[Dict[str, str]] = field(default_factory=list)
    replay_command: str = ""
    certificate_hash: str = ""
    public_wording: str = ""
    timestamp_utc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "benchmark_name": self.benchmark_name,
            "benchmark_version": self.benchmark_version,
            "design_id": self.design_id,
            "rtl_hash": self.rtl_hash,
            "chipgate_safety_result": self.chipgate_safety_result,
            "lint_result": self.lint_result,
            "synthesis_result": self.synthesis_result,
            "formal_result": self.formal_result,
            "fpga_flow_result": self.fpga_flow_result,
            "asic_flow_result": self.asic_flow_result,
            "tool_versions": self.tool_versions,
            "artifact_hashes": self.artifact_hashes,
            "replay_command": self.replay_command,
            "public_wording": self.public_wording,
            "timestamp_utc": self.timestamp_utc,
        }
        d["certificate_hash"] = compute_evidence_hash(d)
        self.certificate_hash = d["certificate_hash"]
        return d

    def save(self, output_path: str) -> str:
        """Save evidence record to JSON file. Returns the path."""
        d = self.to_dict()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(d, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return output_path


def create_evidence_record(
    design_id: str,
    rtl_text: str,
    safety_result: str,
    lint_result: str,
    synthesis_result: str,
    formal_result: str,
    fpga_flow_result: str,
    asic_flow_result: str,
    tool_versions: Dict[str, Optional[str]],
    replay_command: str,
    extra_artifacts: Optional[List[Dict[str, str]]] = None,
) -> SiliconEvidenceRecord:
    """
    Create a complete evidence record for a design.
    """
    # Hash artifacts
    artifacts = hash_design_artifacts(
        rtl_text=rtl_text,
        report_text=f"{safety_result}|{lint_result}|{synthesis_result}|{formal_result}|{fpga_flow_result}|{asic_flow_result}",
    )
    if extra_artifacts:
        artifacts.extend(extra_artifacts)

    record = SiliconEvidenceRecord(
        benchmark_name="siliconbench_v0",
        benchmark_version=__version__,
        design_id=design_id,
        rtl_hash=_sha256(rtl_text),
        chipgate_safety_result=safety_result,
        lint_result=lint_result,
        synthesis_result=synthesis_result,
        formal_result=formal_result,
        fpga_flow_result=fpga_flow_result,
        asic_flow_result=asic_flow_result,
        tool_versions=tool_versions,
        artifact_hashes=artifacts,
        replay_command=replay_command,
        public_wording=st.SILICON_PUBLIC_WORDING,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )

    # Compute certificate hash
    d = record.to_dict()
    record.certificate_hash = d["certificate_hash"]

    return record