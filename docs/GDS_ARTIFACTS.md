# GDS Artifact Hashing in ChipGate

## Overview

ChipGate's OpenLanePhysicalBench (Phase 10) uses SHA-256 hashing to create
an integrity chain for all artifacts involved in the physical flow pipeline.
This document explains what gets hashed, when a GDS hash is created versus a
`GDS_MISSING` status, how the evidence pack is structured, and what the
hashes do and do not guarantee.

## How GDS Artifact Hashing Works

The `chipgate/gds_artifacts.py` module manages all artifact hashing for the
physical flow. It computes SHA-256 hex digests of file contents and string
contents, producing a structured hash table for the evidence pack.

### Hash Functions

| Function | Input | Output |
|----------|-------|--------|
| `hash_file(path)` | File on disk | `ArtifactHash` with SHA-256 of file bytes |
| `hash_content(label, text)` | Label string + content string | `ArtifactHash` with SHA-256 of UTF-8 bytes |
| `hash_gds_file(gds_path)` | GDS file path | `ArtifactHash` with SHA-256 of GDS bytes |
| `hash_all_artifacts(...)` | All artifact inputs | `GDSHashResult` with all hashes combined |

### Data Structures

**ArtifactHash** — A single hash entry:

```json
{
    "label": "rtl",
    "sha256": "a1b2c3d4...",
    "size_bytes": 2048,
    "path": ""
}
```

**GDSHashResult** — Aggregate result for the physical flow:

```json
{
    "gds_found": true,
    "gds_hash": "e5f6a7b8c9d0...",
    "gds_path": "/path/to/design.gds",
    "gds_size_bytes": 524288,
    "artifact_hashes": [...],
    "total_hash_count": 7
}
```

## What Gets Hashed

### When GDS Is Present

If a `.gds` or `.gdsii` file exists at the specified path, the following
artifacts are hashed in order:

| Order | Label | Source |
|-------|-------|--------|
| 1 | `rtl` | Core RTL Verilog text |
| 2 | `wrapper` | TinyTapeout wrapper Verilog text |
| 3 | `config` | OpenLane configuration file text |
| 4 | `pinout` | Pinout JSON text |
| 5 | `report_*` | Each parsed report fixture (DRC, LVS, timing, area) |
| 6 | `replay_command` | Replay command string for reproducibility |
| 7 | GDS filename | GDS file bytes |

Result: `GDS_HASH_CREATED` status.

### When GDS Is Missing

If no `.gds` file exists at the specified path, the following text artifacts
are still hashed:

| Order | Label | Source |
|-------|-------|--------|
| 1 | `rtl` | Core RTL Verilog text |
| 2 | `wrapper` | TinyTapeout wrapper Verilog text |
| 3 | `config` | OpenLane configuration file text |
| 4 | `pinout` | Pinout JSON text |
| 5 | `report_*` | Each parsed report fixture (DRC, LVS, timing, area) |
| 6 | `replay_command` | Replay command string for reproducibility |

Result: `GDS_MISSING` status.

**Key point**: Hashing text artifacts even when GDS is missing provides an
integrity chain for all available materials. It does not substitute for a
GDS file or imply fabrication readiness.

## GDS_HASH_CREATED vs GDS_MISSING

| Status | Condition | What It Means |
|--------|-----------|---------------|
| `GDS_HASH_CREATED` | A `.gds` file was found and hashed | SHA-256 of the GDS file bytes was recorded. Does not mean the GDS is valid, DRC-clean, or tapeout-ready. |
| `GDS_MISSING` | No `.gds` file was found | All text artifacts (RTL, wrapper, config, pinout, reports, replay) were hashed instead. Does not mean the design is incomplete or invalid — GDS may not have been generated yet. |

## SHA-256 Integrity Chain

Each artifact hash is an independent SHA-256 digest. The evidence pack
records all hashes together, creating a reproducible integrity snapshot:

1. **RTL hash** — Pins the exact Verilog source used.
2. **Wrapper hash** — Pins the TinyTapeout wrapper.
3. **Config hash** — Pins the OpenLane configuration.
4. **Pinout hash** — Pins the pin mapping definition.
5. **Report hashes** — Pin the parsed DRC, LVS, timing, and area data.
6. **Replay command hash** — Pins the exact command needed to reproduce
   the benchmark run.
7. **GDS hash** (if present) — Pins the GDS file bytes.

Re-running the benchmark with the same inputs produces the same hashes,
enabling deterministic replay verification.

## Evidence Pack Structure for Physical Flow

The evidence pack for OpenLanePhysicalBench includes:

```json
{
    "benchmark_name": "OpenLanePhysicalBench",
    "benchmark_version": "...",
    "timestamp_utc": "...",
    "overall_status": "PHYSICAL_BENCH_PASS",
    "design_results": [
        {
            "design_id": "...",
            "safety_status": "...",
            "openlane_config_status": "...",
            "openroad_run_status": "...",
            "drc_status": "...",
            "lvs_status": "...",
            "timing_status": "...",
            "gds_status": "...",
            "overall_status": "...",
            "drc_result": {...},
            "lvs_result": {...},
            "timing_result": {...},
            "area_stats": {...},
            "evidence_record": {
                "created": true,
                "gds_found": false,
                "gds_hash": "",
                "artifact_hashes": [...],
                "artifact_hash_count": 6,
                "manual_review_items": [...]
            }
        }
    ],
    "toolchain_report": {...},
    "metrics": {...},
    "manual_review_items": [...],
    "public_wording": "OpenLanePhysicalBench checks whether...",
    "limitation": "Passing OpenLanePhysicalBench does not mean...",
    "artifacts_dir": "/tmp/chipgate_physical_..."
}
```

The `public_wording` and `limitation` fields are mandatory in every evidence
pack and must not be omitted when results are shared.

## No Claim of Tapeout Readiness from Hash Alone

A SHA-256 hash is an integrity checksum, not a quality certificate:

- **A hash proves**: The artifact bytes at the time of hashing are
  reproducibly verifiable.
- **A hash does not guarantee**: The artifact is correct, DRC-clean, LVS-clean,
  timing-closed, power-characterised, or suitable for fabrication.
- **Multiple hashes**: Having many hashes in an evidence pack provides a
  comprehensive integrity snapshot. It does not substitute for professional
  EDA signoff or foundry qualification.
- **GDS hash specifically**: Even a valid SHA-256 of a GDS file only proves
  the file contents are reproducible. It does not validate the layout, verify
  design rules, or confirm fabrication readiness.

## Public Disclaimer

> OpenLanePhysicalBench checks whether a tiny DTL gate design can move from open-silicon preparation toward a reproducible ASIC physical-flow readiness review. It does not guarantee silicon correctness, fabrication readiness, timing signoff, real power, real area, physical durability, regulatory conformance or safety-critical deployment.

## See Also

- [OPENLANE_PHYSICAL_BENCH.md](OPENLANE_PHYSICAL_BENCH.md) — Full benchmark documentation
- [PHYSICAL_FLOW_LIMITATIONS.md](PHYSICAL_FLOW_LIMITATIONS.md) — Detailed limitation language
- [OPEN_SILICON_LIMITATIONS.md](OPEN_SILICON_LIMITATIONS.md) — Open silicon limitations
