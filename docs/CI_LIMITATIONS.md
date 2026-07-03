# RealToolchainCI Limitations

This document states what RealToolchainCI (Phase 11) does and does not
guarantee. These limitations apply to all CI results, stage statuses,
toolchain detection reports, HTML reports, JSON output, and artifact
manifests.

---

## Core Limitation

> Passing RealToolchainCI does not guarantee silicon correctness, fabrication
> readiness, physical safety, timing signoff, real power or real area.

RealToolchainCI is a tool-flow readiness check. It verifies that the
ChipGate Python package passes its unit tests, that hygiene checks
are clean, and that optional open-source EDA tools can be invoked
successfully against a safe reference design. It does not verify that
any hardware design is correct, manufacturable, or safe.

## SKIPPED Means Tool Not Installed

A stage marked with a `*_SKIPPED` status means the corresponding tool was
not installed or not found on the system. It does **not** mean:

- The design failed the stage
- The design has a defect
- The stage was attempted and produced an error
- The CI pipeline is broken

A `CI_PARTIAL` result with multiple SKIPPED stages on a minimal CI runner
is expected and normal. Only `*_FAIL` statuses indicate actual problems.

## No Claim of Real Power, Real Area, Real Timing

RealToolchainCI does not measure, estimate, or claim:

- **Real power consumption** -- No dynamic power analysis, no leakage power
  analysis, no thermal analysis, no IR drop analysis.
- **Real area** -- No gate-level area measurement after synthesis, no
  physical die area measurement, no utilisation analysis. The Yosys `stat`
  command reports cell counts from the internal ABC library, which are not
  foundry-correlated area measurements.
- **Real timing** -- No static timing analysis signoff, no clock tree
  synthesis, no setup/hold verification, no clock domain crossing analysis.

All metrics produced by RealToolchainCI are tool-invocation outcomes and
structural checks. They do not represent physical measurements from a
fabricated device or a signoff-quality EDA flow.

## No NVIDIA Comparison

RealToolchainCI does not compare to, benchmark against, or make any claims
relative to any NVIDIA product, tool, workflow, or design methodology. No
performance comparison to any commercial EDA tool or proprietary chip
design flow is implied or stated.

## No Medical, Defence, or Robotics Certification

RealToolchainCI is not certified, validated, or suitable as evidence for
any regulated application:

- **Medical devices** -- Does not meet IEC 60601, FDA guidance, or medical
  device regulatory requirements. A `CI_PASS` result must never be used as
  evidence of medical device safety.
- **Defence and aerospace** -- Does not meet DO-254, MIL-STD-882, or
  equivalent standards. Must not be used as a sole verification artifact
  for safety-critical avionics, weapons systems, or defence hardware.
- **Robotics and autonomous systems** -- Does not validate real-time
  constraints, sensor fusion correctness, motion safety envelopes, or
  hardware/software interactions required for safe robotic operation.
- **Safety-critical deployment** -- Must not be used as the primary means
  of demonstrating functional safety for any system where failure could
  result in personal injury, death, environmental damage, significant
  property damage, or loss of critical infrastructure.

## English-Only, Public-Safe Wording

All output from RealToolchainCI uses English-only, public-safe language.
The `public_wording` and `limitation` fields are included in every JSON
output and HTML report. These fields must not be omitted when results are
shared, published, or used for decision-making.

The mandatory wording is:

> RealToolchainCI records available open-source hardware toolchain checks
> and their outputs. Passing CI does not guarantee silicon correctness,
> fabrication readiness, physical safety, timing signoff, real power or
> real area.

The limitation text is:

> These CI results record which toolchain stages were available and which
> checks passed. They do not guarantee silicon correctness, fabrication
> readiness, physical safety, timing signoff, real power, real area, or
> regulatory conformance. A stage marked SKIPPED means the tool was not
> installed, not that the design failed. Real results require foundry
> PDK, DRC/LVS signoff, and physical measurement.

## CI Results Are Tool-Flow Readiness Checks, Not Silicon Results

RealToolchainCI verifies:

- The ChipGate Python package passes its own unit tests
- No private imports, secrets, `shell=True`, non-English content, or
  forbidden overclaim phrases exist in the public codebase
- Demo commands execute without error
- Installed EDA tools can be invoked against a reference design

RealToolchainCI does **not** verify:

- Functional correctness of any hardware design
- Synthesis quality, timing signoff, or power optimisation
- Physical layout correctness or DRC/LVS cleanliness
- Fabrication readiness or tapeout suitability
- Post-silicon behaviour or measured performance

## Honest Claims

You can honestly claim:

- ChipGate passed its Python unit tests and hygiene checks.
- Specific EDA tools were detected and invoked successfully.
- An artifact manifest with SHA-256 hashes was generated.
- The CI report shows specific stage outcomes at a specific point in
  time on a specific system.
- No private imports, secrets, or overclaim phrases were found in the
  scanned source files.

You cannot honestly claim:

- The design is correct, safe, or ready for fabrication.
- The design has been verified for any safety-critical application.
- The CI results represent real power, real area, or real timing.
- The CI results are comparable to any commercial EDA tool output.
- A SKIPPED stage means the design was tested and failed.

## What Is Required for Real Results

Real silicon results require:

- Foundry-qualified PDK with technology files and cell libraries
- Complete timing analysis (STA) with signoff corners
- Power analysis (dynamic and leakage) with IR drop
- DRC and LVS signoff in the target foundry process
- Physical verification (RC extraction, antenna checks)
- Device qualification testing
- Regulatory compliance review (if applicable)
- Professional tapeout signoff
- Post-silicon validation and physical measurement

RealToolchainCI provides none of these. It is a pre-silicon tool-flow
readiness filter, not a replacement for professional EDA flows or
physical signoff.