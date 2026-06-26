# JARVI3 Chip DesignGuard Lite

Public-safe demonstration package for the JARVI3 ChipGate / DesignGuard request and response format.

Repository target: <https://github.com/kyal102/chipgate>

## What This Is

This package demonstrates the JSON format used by JARVI3 Chip DesignGuard. It is a standalone public demo that shows how a chip-design artifact is classified, routed, given an export decision, and documented with limitations.

## What This Is Not

- It does not require the private ChipGate installation.
- It does not import or contain private JARVI3 code.
- It does not import or contain private DTL logic.
- It does not run real gate checks.
- It does not prove real silicon, ASIC timing, fabrication readiness, production readiness, safety certification, or universal chip performance.
- It does not claim DTL beats all chips, beats NVIDIA, is universally faster, or is safety certified.

## Install

```bash
python -m pip install -e .
```

## Run

```bash
python -m jarvi3_designguard_lite
jarvi3-designguard-lite
```

You can also run the original standalone script:

```bash
python designguard_lite.py
```

## Contents

| File | Description |
|------|-------------|
| `designguard_lite.py` | Standalone demo script with sample request/response |
| `public_adapter.py` | Public adapter interface with expected signatures |
| `jarvi3_designguard_lite/` | Installable module wrapper |
| `demo_request.json` | Sample request JSON |
| `demo_response.json` | Sample response JSON |
| `demo_passport.json` | Sample design passport JSON |
| `BENCHMARK_EVIDENCE.md` | Public-safe summary of the private Phase 31K evidence boundary |
| `LIMITATIONS.md` | Detailed limitations statement |

## Test

```bash
python -m pytest tests -q
```

## Full Version

The full private JARVI3 Labs version adds actual ChipGate execution, EvidencePack, ReplayGate, DesignGuard passport routing, Speed / PPA proof packs, real-toolchain CI awareness, and paid API access.

See `BENCHMARK_EVIDENCE.md` for the current Phase 31K evidence boundary and `LIMITATIONS.md` for the full limitations statement.
