"""
ChipGate OpenLanePhysicalBench — GDS artifact hashing.

Manages GDS file hashing and artifact hash tables for the physical
flow evidence pack. If a GDS file exists, it is hashed. If not,
RTL, wrapper, config, pinout, report fixtures, and replay commands
are hashed instead.

Does not claim a valid tapeout-ready GDS unless the official flow
produced one and all checks passed.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ArtifactHash:
    """A single artifact hash entry."""
    label: str
    sha256: str
    size_bytes: int = 0
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "path": self.path,
        }


@dataclass
class GDSHashResult:
    """Result of GDS artifact hashing."""
    gds_found: bool = False
    gds_hash: str = ""
    gds_path: str = ""
    gds_size_bytes: int = 0
    artifact_hashes: List[ArtifactHash] = field(default_factory=list)
    total_hash_count: int = 0

    def to_dict(self) -> dict:
        return {
            "gds_found": self.gds_found,
            "gds_hash": self.gds_hash[:32] + "..." if self.gds_hash else "",
            "gds_path": self.gds_path,
            "gds_size_bytes": self.gds_size_bytes,
            "artifact_hashes": [a.to_dict() for a in self.artifact_hashes],
            "total_hash_count": self.total_hash_count,
        }


def _sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def _sha256_string(text: str) -> str:
    """Compute SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path: str) -> Optional[ArtifactHash]:
    """Hash a file and return an ArtifactHash, or None if file missing."""
    p = Path(path)
    if not p.exists():
        return None
    data = p.read_bytes()
    return ArtifactHash(
        label=p.name,
        sha256=_sha256_bytes(data),
        size_bytes=len(data),
        path=str(p),
    )


def hash_content(label: str, content: str) -> ArtifactHash:
    """Hash a string content and return an ArtifactHash."""
    data = content.encode("utf-8")
    return ArtifactHash(
        label=label,
        sha256=_sha256_bytes(data),
        size_bytes=len(data),
    )


def hash_gds_file(gds_path: str) -> ArtifactHash:
    """Hash a GDS file specifically.

    Args:
        gds_path: Path to a .gds or .gdsii file.

    Returns:
        ArtifactHash with the file hash, or an empty hash if file missing.
    """
    p = Path(gds_path)
    if not p.exists():
        return ArtifactHash(label=p.name, sha256="", size_bytes=0, path=gds_path)
    data = p.read_bytes()
    return ArtifactHash(
        label=p.name,
        sha256=_sha256_bytes(data),
        size_bytes=len(data),
        path=str(p),
    )


def hash_all_artifacts(
    rtl_content: str = "",
    wrapper_content: str = "",
    config_content: str = "",
    pinout_content: str = "",
    report_fixtures: Optional[Dict[str, str]] = None,
    replay_command: str = "",
    gds_path: Optional[str] = None,
) -> GDSHashResult:
    """Hash all available artifacts for the physical flow evidence pack.

    If a GDS file exists at gds_path, it is hashed. Regardless, all
    text-based artifacts (RTL, wrapper, config, pinout, reports, replay
    command) are hashed.

    Does not claim a valid tapeout-ready GDS unless the official flow
    produced one and all checks passed.

    Args:
        rtl_content: Core RTL Verilog text.
        wrapper_content: Wrapper Verilog text.
        config_content: OpenLane config file text.
        pinout_content: Pinout JSON text.
        report_fixtures: Dict of report label -> report text.
        replay_command: Replay command string.
        gds_path: Optional path to a GDS file.

    Returns:
        GDSHashResult with all hashes.
    """
    result = GDSHashResult()
    hashes: List[ArtifactHash] = []

    # Hash text artifacts
    if rtl_content:
        hashes.append(hash_content("rtl", rtl_content))
    if wrapper_content:
        hashes.append(hash_content("wrapper", wrapper_content))
    if config_content:
        hashes.append(hash_content("config", config_content))
    if pinout_content:
        hashes.append(hash_content("pinout", pinout_content))

    # Hash report fixtures
    if report_fixtures:
        for label, text in report_fixtures.items():
            if text:
                hashes.append(hash_content(f"report_{label}", text))

    # Hash replay command
    if replay_command:
        hashes.append(hash_content("replay_command", replay_command))

    # Hash GDS if present
    if gds_path:
        gds_hash = hash_gds_file(gds_path)
        if gds_hash.sha256:
            result.gds_found = True
            result.gds_hash = gds_hash.sha256
            result.gds_path = gds_hash.path
            result.gds_size_bytes = gds_hash.size_bytes
            hashes.append(gds_hash)

    result.artifact_hashes = hashes
    result.total_hash_count = len(hashes)
    return result