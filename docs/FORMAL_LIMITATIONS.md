# FormalGate-Lite: Formal Limitations

This document describes the formal limitations of FormalGate-Lite in detail.
It is intended for anyone evaluating, using, or citing FormalGate-Lite results.

---

## Mandatory Limitation Statement

> Passing FormalGate-Lite does not mean the design is fully verified, fabricated,
> timing-closed, physically tested, certified or safe for real-world actuation. It
> only means the selected formal properties passed under the configured model and
> available tools.

This statement must be included whenever FormalGate-Lite results are shared,
published, or used for decision-making.

---

## Table of Contents

- [Core Limitation: Bounded vs Unbounded](#core-limitation-bounded-vs-unbounded)
- [Limited Property Suite](#limited-property-suite)
- [SKIPPED Means Solver Not Installed (Not FAIL)](#skipped-means-solver-not-installed-not-fail)
- [No Claim of Real Power, Real Area, or Real Timing](#no-claim-of-real-power-real-area-or-real-timing)
- [No External Vendor Comparisons](#no-external-vendor-comparisons)
- [No Medical, Defence, or Robotics Certification](#no-medical-defence-or-robotics-certification)
- [No Fabrication Readiness Claim](#no-fabrication-readiness-claim)
- [No Physical Safety Certification](#no-physical-safety-certification)
- [Bounded Model Checking Limitations](#bounded-model-checking-limitations)
- [Solver-Dependent Results May Vary](#solver-dependent-results-may-vary)
- [Scalability: Designed for Small Designs](#scalability-designed-for-small-designs)
- [Missing Tool Graceful Degradation](#missing-tool-graceful-degradation)
- [Honest Claims](#honest-claims)
- [What Is Required for Real Formal Verification](#what-is-required-for-real-formal-verification)

---

## Core Limitation: Bounded vs Unbounded

FormalGate-Lite performs **bounded model checking (BMC)** by default. BMC proves
that a property holds for all input sequences up to a fixed number of clock
cycles (the bound). It does **not** perform unbounded (inductive or k-inductive)
proof.

Consequences of bounded-only checking:

- A bug that requires more cycles to manifest than the configured bound will not
  be caught.
- Passing all properties at depth N proves correctness only for those N cycles,
  not for all time.
- Increasing the bound improves coverage but does not eliminate the fundamental
  limitation: BMC alone cannot prove unbounded correctness.

FormalGate-Lite is explicitly a **lite** tool. It does not aspire to replace
unbounded formal engines, inductive proof strategies, or assume-guarantee
reasoning used in professional formal verification flows.

---

## Limited Property Suite

FormalGate-Lite checks a fixed set of structural and safety properties derived
from the DTL (Design, Test, Lockout) gating pattern. The current property suite
includes, but is not limited to:

- Kill switch deassertion forces safe output within bounded cycles
- Reset recovery reaches a known-safe state
- Gating signals cannot be simultaneously bypassed
- No combinational loops
- Output does not toggle when all gating signals are deasserted
- No transparent latches inferred
- FSM state reachability
- Output defaults to safe state
- No ungated path from input to actuation output

This suite is **not exhaustive**. There are entire categories of formal
properties that FormalGate-Lite does **not** check, including but not limited to:

- Protocol correctness (AXI, APB, Wishbone, custom protocols)
- Data integrity and error detection/correction logic
- Arithmetic overflow and underflow
- Clock domain crossing correctness
- Bus contention and tri-state driver conflicts
- Power-domain isolation properties
- Security properties (side-channel resistance, fault injection resilience)
- Functional equivalence between abstraction levels
- Temporal properties beyond simple safety (liveness, fairness, absence of
  starvation)

A design that passes all FormalGate-Lite properties may still contain bugs in
any of these unchecked categories.

---

## SKIPPED Means Solver Not Installed (Not FAIL)

FormalGate-Lite distinguishes between `FORMAL_PROPERTY_FAIL` and
`FORMAL_PROPERTY_SKIPPED`. These are fundamentally different outcomes.

When a property is marked `FORMAL_PROPERTY_SKIPPED` with reason
`FORMAL_SOLVER_MISSING`, it means:

- SymbiYosys (`sby`) or Yosys was not found on the system PATH.
- The property file was **generated** but **not executed**.
- No proof or disproof was obtained.

It does **not** mean:

- The property failed.
- The design is unsafe.
- The property is irrelevant or trivially true.
- The tool encountered an error during checking.

A run on a system without SBY and Yosys will produce a report where all
properties are SKIPPED. This is expected and normal behavior. Such a report
represents a list of **generated properties**, not a list of **proven
properties**.

Only the following statuses indicate actual property violations:

- `FORMAL_PROPERTY_FAIL`
- `FORMAL_COUNTEREXAMPLE_FOUND`

---

## No Claim of Real Power, Real Area, or Real Timing

FormalGate-Lite operates on the **RTL abstraction level**. It does not perform,
estimate, or claim any of the following:

### Power

- No dynamic power analysis
- No leakage power estimation
- No power-aware formal checking
- No voltage droop or IR drop analysis
- No power-domain-aware verification

### Area

- No gate-level area measurement
- No die area estimation
- No cell count or utilization metrics
- No physical placement or floorplanning verification

### Timing

- No static timing analysis (STA)
- No setup/hold time verification
- No clock domain crossing (CDC) analysis
- No timing closure verification
- No max-frequency determination
- No path delay measurement

Any discussion of power, area, or timing in relation to FormalGate-Lite results
is speculative and outside the scope of what the tool measures or proves.

---

## No External Vendor Comparisons

FormalGate-Lite does not compare to, benchmark against, or make any claims
relative to any external vendor product, tool, workflow, or design methodology.
No performance, capability, or quality comparisons against any third-party
formal verification tool are implied or provided.

---

## No Medical, Defence, or Robotics Certification

FormalGate-Lite is **not** certified, validated, or suitable as evidence for
any regulated application. Specifically:

### Medical Devices

- Does not meet IEC 60601 (medical electrical equipment)
- Does not satisfy FDA guidance for medical device software
- Does not provide evidence for ISO 13485 quality management
- Must not be used as part of a medical device verification argument

### Defence and Aerospace

- Does not meet DO-254 (airborne electronic hardware assurance)
- Does not satisfy MIL-STD-882 (system safety)
- Does not comply with ARP4754A (development assurance for airborne systems)
- Must not be cited in safety cases for defence or aerospace applications

### Robotics and Autonomous Systems

- Does not validate real-time constraints
- Does not verify sensor fusion correctness
- Does not check motion safety envelopes
- Does not prove absence of hazardous autonomous behaviour
- Must not be used as the sole or primary safety argument for robotic systems

### General Safety-Critical Deployment

FormalGate-Lite must not be used as the primary means of demonstrating
functional safety for any system where failure could result in:

- Personal injury or death
- Environmental damage
- Significant property damage
- Loss of critical infrastructure availability

---

## No Fabrication Readiness Claim

FormalGate-Lite does not perform any physical verification. Passing all formal
properties does not mean the design is ready for fabrication. Specifically,
FormalGate-Lite does not check:

- **Design Rule Checking (DRC):** No verification that the layout obeys foundry
  design rules.
- **Layout vs Schematic (LVS):** No verification that the layout matches the
  netlist.
- **Antenna Rule Checking:** No verification of antenna effects.
- **Electromigration (EM) Analysis:** No verification of current density limits.
- **IR Drop Analysis:** No verification of power grid integrity.
- **Fill and Density Rules:** No metal fill or density rule checking.
- **Manufacturability (DFM):** No design-for-manufacturing analysis.
- **Yield Analysis:** No statistical yield estimation.
- **Foundry PDK Compliance:** No verification against any specific process node
  or foundry rules.

A design that passes FormalGate-Lite may have critical physical violations that
make it unmanufacturable.

---

## No Physical Safety Certification

FormalGate-Lite verifies properties against an **abstract RTL model**. The real
world introduces physical effects that are not modelled:

- Voltage droop and supply noise
- Thermal runaway and thermal cycling
- Electromigration and IR drop
- Latch-up and single-event upsets
- Process, voltage, and temperature (PVT) variation
- Package parasitics and bond wire effects
- PCB-level power delivery and signal integrity
- Environmental conditions (humidity, vibration, radiation)

FormalGate-Lite makes **zero claims** about the physical safety of any design
under real-world operating conditions. RTL-level formal checking cannot
substitute for physical testing, environmental qualification, or safety
certification by accredited bodies.

---

## Bounded Model Checking Limitations

FormalGate-Lite uses bounded model checking with a **default depth of 20 clock
cycles**. This bound is configurable but has fundamental implications:

### Depth 20 Default

- Properties are proven only for all input sequences of length 0 through 20
  clock cycles.
- A bug requiring 21 or more cycles to produce a property violation will not be
  detected.
- The bound of 20 is a pragmatic default chosen for runtime on small designs.
  It is not derived from any design-specific analysis.

### Increasing the Bound

- Increasing the bound (e.g., to 50 or 100) improves coverage but
  exponentially increases solver runtime and memory usage.
- A higher bound still does not constitute an unbounded proof.
- There is no automatic determination of a "sufficient" bound for a given
  design.

### What BMC Cannot Do

- **Prove liveness:** BMC cannot prove that a desired state is eventually
  reached (only that a safety property is not violated within the bound).
- **Prove fairness:** BMC cannot prove that no process is starved indefinitely.
- **Handle infinite-state systems:** BMC operates on finite state-space
  abstractions. Designs with unbounded counters, deep FIFOs, or parametrized
  widths may not be fully explored.
- **Handle constraints on environment:** BMC assumes all inputs are free
  (unconstrained) unless explicit assumptions are provided. Missing environment
  constraints can lead to spurious counterexamples.

---

## Solver-Dependent Results May Vary

FormalGate-Lite relies on SymbiYosys as its formal engine and Yosys as its
synthesis backend. Results are inherently dependent on these tools:

### Version Sensitivity

- Different versions of SBY, Yosys, or the underlying SAT/SMT solvers may
  produce different results for the same property and design.
- A property that passes under one solver version may time out or produce
  different results under another.

### Platform Sensitivity

- Solver behavior may vary across operating systems, architectures, and
  hardware configurations.
- Memory limits and timeout behavior are platform-dependent.

### Non-Determinism

- Some solver strategies involve randomization (e.g., random seed selection for
  SAT solving).
- Two runs of the same property on the same system may produce different
  results (e.g., one passes, the other times out).
- Replay stability of solver outcomes is not guaranteed.

### Implications

- FormalGate-Lite results represent a **point-in-time snapshot** on a
  **specific system** with a **specific toolchain version**.
- Results should not be treated as universally reproducible without recording
  the exact tool versions and system configuration.
- The evidence pack includes SHA-256 hashes to allow verification that the
  reported results correspond to the specific artifacts generated, but the
  underlying solver results are not guaranteed to be deterministic.

---

## Scalability: Designed for Small Designs

FormalGate-Lite is designed for **small DTL-gated RTL designs** -- typically
tens to hundreds of lines of SystemVerilog. It is not suitable for:

### Scale Limitations

- **SoC-scale designs:** Designs with millions of gates, multiple clock domains,
  complex bus fabrics, or embedded processors are beyond the intended scope.
- **Large state spaces:** Designs with wide counters, deep memories, or complex
  data paths may cause the solver to exhaust memory or time out.
- **Multi-module hierarchies:** While FormalGate-Lite handles basic hierarchy,
  deeply nested or heavily parameterized designs may not be processed correctly.

### Performance Expectations

- Runtime scales exponentially with design size and bound depth.
- A design that takes seconds at depth 20 may take hours or days at depth 50.
- There is no automatic resource estimation or timeout recommendation for a
  given design.

### When to Use Something Else

For designs larger than a few hundred lines of RTL, or when unbounded proofs
are required, professional formal verification tools with dedicated SAT/SMT
engines, abstraction techniques, and expert-driven property elaboration should
be used instead.

---

## Missing Tool Graceful Degradation

FormalGate-Lite is designed to produce valid results even when external tools
are not installed. This is a deliberate design choice with specific implications:

### Behavior Without SBY/Yosys

- Property files (.sby) are generated but not executed.
- All properties are marked `FORMAL_PROPERTY_SKIPPED` with reason
  `FORMAL_SOLVER_MISSING`.
- The evidence pack contains property files and SHA-256 hashes but no solver
  logs or proof artifacts.
- The HTML report and JSON output are still produced with correct structure.

### Behavior Without Verilator

- Verilator is used for optional pre-check linting.
- Its absence does not affect formal property generation or checking.
- Lint-related properties (if any) are skipped gracefully.

### What Graceful Degradation Does Not Mean

- It does not mean the properties were verified.
- It does not mean the design is safe.
- It does not mean the SKIPPED results are equivalent to PASS results.
- It means the tool produced its best possible output given the available
  toolchain.

### Recommended Practice

For meaningful formal verification results, install SymbiYosys and Yosys before
running FormalGate-Lite. Use `python -m chipgate formal --toolchain-status` to
check toolchain availability before interpreting results.

---

## Honest Claims

This section describes what you can and cannot honestly claim based on
FormalGate-Lite results.

### What You Can Honestly Claim

- **Property generation:** FormalGate-Lite generated SBY property files for a
  set of DTL-gated designs.
- **Specific outcomes:** Specific properties passed, failed, were skipped, or
  were inconclusive (with documented reasons for each).
- **Evidence provenance:** An evidence pack with SHA-256 hashes was generated,
  allowing verification that the reported results correspond to the specific
  artifacts.
- **Point-in-time report:** The formal report reflects specific property
  outcomes at a specific point in time, on a specific system, with a specific
  toolchain version.
- **Structural observations:** Structural properties (no combinational loops,
  no latch inference, gating signal structure) were observed in the RTL.
- **No solver required for generation:** Property files were generated
  regardless of whether a solver was installed.
- **Graceful operation:** The tool ran to completion and produced structured
  output, even when external tools were missing.

### What You Cannot Honestly Claim

- **Design correctness:** You cannot claim the design is functionally correct.
- **Design safety:** You cannot claim the design is safe for any real-world
  application.
- **Fabrication readiness:** You cannot claim the design is ready for tapeout
  or fabrication.
- **Timing closure:** You cannot claim the design meets any timing target.
- **Formal verification complete:** You cannot claim the design has been
  "formally verified" in any professional or regulatory sense.
- **PASS means proven:** You cannot claim that `FORMAL_PROPERTY_PASS` means the
  property is proven for all time (it is proven only up to the bound).
- **SKIPPED means verified:** You cannot claim that a SKIPPED property was
  verified, checked, or is trivially true.
- **Equivalence to professional tools:** You cannot claim that FormalGate-Lite
  results are equivalent to, a substitute for, or comparable with results from
  professional formal verification tools.
- **Certification evidence:** You cannot cite FormalGate-Lite results as
  evidence in any certification, safety case, or regulatory submission.
- **Bug-free design:** You cannot claim the design contains no bugs.

### Example of Honest vs Dishonest Wording

| Honest | Dishonest |
|--------|-----------|
| "FormalGate-Lite checked 10 properties on design X; 8 passed, 1 failed, 1 was skipped (solver missing)." | "Design X passed formal verification." |
| "The kill-switch property passed bounded model checking at depth 20." | "The kill switch is formally proven correct." |
| "No combinational loops were detected in the RTL structure." | "The design has no structural hazards." |
| "Property files were generated for manual SBY execution." | "The design was formally verified." |

---

## What Is Required for Real Formal Verification

Real formal verification -- the kind that can support tapeout decisions,
regulatory submissions, and safety cases -- requires substantially more than
what FormalGate-Lite provides. Below is a non-exhaustive list of what a
complete formal verification effort entails.

### Property Development

- **Comprehensive property elaboration** by qualified verification engineers
  who understand the design intent, interface protocols, and failure modes.
- **Cover properties** that exercise all design intent, not just safety
  invariants. Covers ensure that the formal engine explores the relevant state
  space.
- **Assume properties** that accurately model the environment, interface
  constraints, and legal input sequences. Without correct assumptions, the
  formal engine may explore infeasible input spaces and produce spurious
  counterexamples.

### Proof Strategies

- **Unbounded (inductive) proofs** that establish correctness for all time,
  not just for a bounded number of cycles.
- **K-induction** with appropriate base cases and inductive steps.
- **Assume-guarantee reasoning** for compositional verification of large
  designs.
- **Abstraction and refinement** to handle designs that are too large for
  direct state-space exploration.

### Tooling and Infrastructure

- **Industrial formal verification tools** with optimized SAT/SMT engines,
  model checking algorithms, and theorem prover integration.
- **Constraint solvers** for modeling complex environmental assumptions.
- **Simulation correlation** to ensure formal properties align with simulation
  testbench behavior.
- **Regression infrastructure** for tracking property results across design
  revisions.

### Process and Review

- **Formal signoff review** by qualified verification experts who examine
  property completeness, assumption validity, and proof strength.
- **Traceability** from design requirements to formal properties to proof
  results.
- **Documentation** sufficient for regulatory review or safety case
  construction.

### Physical and System-Level Verification

- **Static timing analysis** for timing closure.
- **Physical verification** (DRC, LVS, antenna, EM, IR drop) for fabrication
  readiness.
- **Environmental testing** (thermal, vibration, radiation) for physical
  safety.
- **System-level testing** for integration, performance, and real-world
  behavior.
- **Foundry-qualified PDK** for any physical safety or fabrication claims.

### What FormalGate-Lite Provides Toward This List

FormalGate-Lite provides:

- A starting set of safety-oriented properties for DTL-gated designs.
- SBY-compatible property files that can be used as input to a real formal
  verification flow.
- Structural observations that may guide further property development.
- An evidence pack format that demonstrates the provenance of results.

FormalGate-Lite does **not** provide any of the other items on this list. It
is a lightweight property generation and optional bounded-checking tool, not a
replacement for professional formal verification, physical signoff, or safety
certification.

---

## Summary

FormalGate-Lite is a useful tool for generating and optionally checking a
baseline set of formal safety properties on small DTL-gated RTL designs. Its
results have clear, well-defined meaning and clear, well-defined limitations.

When using or citing FormalGate-Lite results, always include the mandatory
limitation statement, distinguish between PASS, FAIL, and SKIPPED, and avoid
any claim that goes beyond what the tool actually checks and proves.