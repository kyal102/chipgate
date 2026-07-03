"""
ChipGate status constants.

All status strings used across the ChipGate benchmarks, scanners, and CI.
Organised by phase and category.
"""

# ── Core Scan / Lint / Formal / Safety ───────────────────────────────────────

SIMULATION_PASS = "SIMULATION_PASS"
SIMULATION_FAIL = "SIMULATION_FAIL"
RTL_SCAN_PASS = "RTL_SCAN_PASS"
RTL_SCAN_FAIL = "RTL_SCAN_FAIL"
RTL_LINT_PASS = "RTL_LINT_PASS"
RTL_LINT_FAIL = "RTL_LINT_FAIL"
LINT_PASS = "LINT_PASS"
LINT_FAIL = "LINT_FAIL"
LINT_SKIPPED_TOOL_MISSING = "LINT_SKIPPED_TOOL_MISSING"
FORMAL_READY = "FORMAL_READY"
FORMAL_NOT_READY = "FORMAL_NOT_READY"
FORMAL_PASS = "FORMAL_PASS"
FORMAL_FAIL = "FORMAL_FAIL"
FORMAL_SKIPPED_TOOL_MISSING = "FORMAL_SKIPPED_TOOL_MISSING"

# ── Safety Gate ──────────────────────────────────────────────────────────────

SAFETY_GATE_PRESENT = "SAFETY_GATE_PRESENT"
KILL_SWITCH_MISSING = "KILL_SWITCH_MISSING"
KILL_SWITCH_BYPASS = "KILL_SWITCH_BYPASS"
TIMEOUT_BYPASS = "TIMEOUT_BYPASS"
RESET_MISSING = "RESET_MISSING"
UNGATED_OUTPUT = "UNGATED_OUTPUT"
UNSAFE_BYPASS_PATH = "UNSAFE_BYPASS_PATH"
UNSAFE_ACCEPTED = "UNSAFE_ACCEPTED"
UNSAFE_BLOCKED = "UNSAFE_BLOCKED"
ASSERTION_MISSING = "ASSERTION_MISSING"
SAFE_STATE_HELD = "SAFE_STATE_HELD"
SAFE_STATE_VIOLATION = "SAFE_STATE_VIOLATION"
FAILSAFE_ESCAPED = "FAILSAFE_ESCAPED"
DUPLICATE_PIN_ASSIGNMENT = "DUPLICATE_PIN_ASSIGNMENT"
CLOCK_MISSING = "CLOCK_MISSING"
FAULT_DETECTED = "FAULT_DETECTED"
NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
PIN_CONSTRAINT_PASS = "PIN_CONSTRAINT_PASS"
PIN_CONSTRAINT_FAIL = "PIN_CONSTRAINT_FAIL"

# ── ChipBench ────────────────────────────────────────────────────────────────

CHIPBENCH_PASS = "CHIPBENCH_PASS"
CHIPBENCH_FAIL = "CHIPBENCH_FAIL"
SAFE_ACCEPTED = "SAFE_ACCEPTED"
SAFE_REJECTED = "SAFE_REJECTED"
HEAVY_CHECK_AVOIDED = "HEAVY_CHECK_AVOIDED"
HEAVY_CHECK_REQUIRED = "HEAVY_CHECK_REQUIRED"
REPLAY_MATCH = "REPLAY_MATCH"
REPLAY_DRIFT = "REPLAY_DRIFT"

CHIPBENCH_PUBLIC_WORDING = (
    "ChipGate is a model-free benchmark that checks RTL structure and "
    "verification-gated safety patterns. "
    "It does not guarantee hardware correctness, silicon readiness, physical safety, "
    "regulatory conformance or experimental validity."
)
CHIPBENCH_LIMITATION = (
    "These results are structural RTL checks only. They do not guarantee silicon "
    "correctness, timing signoff, power safety, area optimality, or regulatory "
    "compliance. Real verification requires synthesis, STA, DRC/LVS signoff, "
    "and physical measurement."
)
PUBLIC_WORDING = CHIPBENCH_PUBLIC_WORDING

# ── Bench modes ──────────────────────────────────────────────────────────────

REGRESSION_DETECTED = "REGRESSION_DETECTED"
NO_REGRESSION_PASS = "NO_REGRESSION_PASS"
SAFE_IMPROVED_DESIGN = "SAFE_IMPROVED_DESIGN"
UNSAFE_IMPROVEMENT_REJECTED = "UNSAFE_IMPROVEMENT_REJECTED"
BEST_TRADEOFF_CANDIDATE = "BEST_TRADEOFF_CANDIDATE"
HIGH_TOGGLE_WARNING = "HIGH_TOGGLE_WARNING"

# ── PASS / FAIL / ALL status sets are defined at the end of this file ──
#     after all individual status constants are defined.
_PASS_EXTRA = {
    # SynthBench
    "SYNTHBENCH_PASS", "SYNTHESIS_PASS", "AREA_IMPROVED", "TIMING_IMPROVED",
    "POWER_PROXY_IMPROVED",
    # SiliconBench
    "SILICON_READINESS_PASS", "ASIC_FLOW_READY", "RESET_RECOVERY_PASS",
    # FPGA
    "FPGA_BENCH_PASS", "FPGA_FLOW_PASS", "FPGA_SYNTH_PASS", "BITSTREAM_READY",
    "BOARD_PROFILE_VALID", "BOARD_EVIDENCE_ATTACHED",
    # TinyTapeout
    "TINYTAPEOUT_PREP_PASS", "TT_PINOUT_VALID", "TT_WRAPPER_CREATED",
    "TT_TESTBENCH_CREATED", "TT_DOCS_CREATED", "TT_INFO_YAML_CREATED",
    "TT_SUBMISSION_CHECK_PASS", "TT_EVIDENCE_PACK_CREATED",
    "TT_READY_FOR_MANUAL_REVIEW",
    # Physical
    "PHYSICAL_BENCH_PASS", "DRC_CLEAN", "LVS_CLEAN", "TIMING_REPORT_PASS",
    "PLACE_ROUTE_PASS", "OPENLANE_CONFIG_PASS", "OPENROAD_RUN_PASS", "GDS_HASH_CREATED",
    # Longevity
    "LONGEVITY_PASS",
    # CI
    "CI_PASS",
    # FormalGate-Lite
    "FORMALGATE_PASS", "FORMAL_PROPERTY_PASS",
    "PROPERTY_FILE_CREATED", "FORMAL_EVIDENCE_CREATED",
    # MutationBench
    "MUTATIONBENCH_PASS", "MUTATION_DETECTED", "MUTATION_BLOCKED",
    "MUTATION_REPLAY_MATCH",
    "UNSAFE_BYPASS_DETECTED", "KILL_SWITCH_MUTATION_DETECTED",
    "TIMEOUT_MUTATION_DETECTED", "RESET_MUTATION_DETECTED",
    "FSM_ESCAPE_DETECTED", "SHADOW_SIGNAL_DETECTED",
    "PRIVATE_LEAK_DETECTED",
}
_FAIL_EXTRA = {
    # SynthBench
    "SYNTHBENCH_FAIL", "SYNTHESIS_FAIL", "AREA_REGRESSED", "TIMING_REGRESSED",
    "POWER_PROXY_REGRESSED",
    # SiliconBench
    "SILICON_READINESS_FAIL", "ASIC_FLOW_FAIL", "RESET_RECOVERY_FAIL",
    # FPGA
    "FPGA_BENCH_FAIL", "FPGA_FLOW_FAIL", "FPGA_SYNTH_FAIL", "BITSTREAM_FAIL",
    "BOARD_PROFILE_INVALID", "BOARD_EVIDENCE_FAIL", "BOARD_EVIDENCE_MISSING",
    # TinyTapeout
    "TINYTAPEOUT_PREP_FAIL", "TT_PINOUT_INVALID", "TT_WRAPPER_MISSING",
    "TT_SUBMISSION_CHECK_FAIL", "TT_PRIVATE_LEAK_DETECTED",
    "TT_SAFETY_PROPERTY_MISSING",
    # Physical
    "PHYSICAL_BENCH_FAIL", "DRC_VIOLATIONS_FOUND", "LVS_MISMATCH_FOUND",
    "TIMING_REPORT_FAIL", "PLACE_ROUTE_FAIL", "OPENLANE_CONFIG_FAIL", "GDS_MISSING",
    # Longevity
    "LONGEVITY_FAIL",
    # CI
    "CI_FAIL",
    # FormalGate-Lite
    "FORMALGATE_FAIL", "FORMAL_PROPERTY_FAIL",
    "PROPERTY_FILE_MISSING",
    # MutationBench
    "MUTATIONBENCH_FAIL", "MUTATION_ESCAPED", "UNSAFE_BYPASS_ESCAPED",
    "MUTATION_REPLAY_DRIFT", "NEEDS_RULE_HARDENING",
}
_ALL_EXTRA = [
    "NEEDS_HUMAN_REVIEW", "NEEDS_MANUAL_REVIEW", "UNSAFE_BLOCKED",
    "HIGH_TOGGLE_WARNING", "LINT_SKIPPED_TOOL_MISSING",
    "FORMAL_NOT_READY", "FORMAL_SKIPPED_TOOL_MISSING",
    "SYNTHESIS_SKIPPED_TOOL_MISSING", "ASIC_FLOW_SKIPPED_TOOL_MISSING",
    "FPGA_FLOW_SKIPPED_TOOL_MISSING", "FPGA_SYNTH_SKIPPED_TOOL_MISSING",
    "BITSTREAM_SKIPPED_TOOL_MISSING", "DRC_SKIPPED_NO_REPORT",
    "LVS_SKIPPED_NO_REPORT", "TIMING_REPORT_SKIPPED",
    "PLACE_ROUTE_SKIPPED_TOOL_MISSING", "OPENROAD_SKIPPED_TOOL_MISSING",
    "NEEDS_OFFICIAL_OPENLANE_RUN", "NEEDS_OFFICIAL_TINYTAPEOUT_CHECK",
    "HEAVY_CHECK_AVOIDED", "HEAVY_CHECK_REQUIRED",
    "CI_PARTIAL", "TOOLCHAIN_FOUND", "TOOLCHAIN_MISSING",
    "VERILATOR_CI_SKIPPED", "YOSYS_CI_SKIPPED",
    "SYMBIYOSYS_CI_SKIPPED", "OPENLANE_CI_SKIPPED", "OPENROAD_CI_SKIPPED",
    "CI_ARTIFACTS_CREATED", "EVIDENCE_PACK_CREATED",
    # FormalGate-Lite
    "FORMAL_PROPERTY_SKIPPED", "FORMAL_INCONCLUSIVE", "FORMAL_TIMEOUT",
    "FORMAL_COUNTEREXAMPLE_FOUND", "FORMAL_SOLVER_MISSING",
    "NEEDS_DEEP_FORMAL_REVIEW", "NEEDS_PHYSICAL_SIGNOFF",
    # MutationBench
    "MUTATION_GENERATED", "MUTATION_ESCAPED", "MUTATION_BLOCKED",
    "UNSAFE_BYPASS_ESCAPED", "MUTATION_REPLAY_DRIFT",
    "NEEDS_RULE_HARDENING",
]


def _build_pass_statuses():
    base = {
        RTL_SCAN_PASS, RTL_LINT_PASS, LINT_PASS, FORMAL_READY, FORMAL_PASS,
        SIMULATION_PASS,
        SAFETY_GATE_PRESENT, SAFE_STATE_HELD, PIN_CONSTRAINT_PASS,
        NO_REGRESSION_PASS, SAFE_IMPROVED_DESIGN, BEST_TRADEOFF_CANDIDATE,
        CHIPBENCH_PASS, SAFE_ACCEPTED, REPLAY_MATCH,
    }
    extras = {globals()[n] for n in _PASS_EXTRA if n in globals()}
    return frozenset(base | extras)


def _build_fail_statuses():
    base = {
        RTL_SCAN_FAIL, RTL_LINT_FAIL, LINT_FAIL, FORMAL_FAIL,
        SIMULATION_FAIL,
        KILL_SWITCH_MISSING, KILL_SWITCH_BYPASS, TIMEOUT_BYPASS, RESET_MISSING,
        UNGATED_OUTPUT, UNSAFE_BYPASS_PATH, UNSAFE_ACCEPTED, ASSERTION_MISSING,
        SAFE_STATE_VIOLATION, FAILSAFE_ESCAPED, DUPLICATE_PIN_ASSIGNMENT,
        CLOCK_MISSING, FAULT_DETECTED, PIN_CONSTRAINT_FAIL,
        REGRESSION_DETECTED, UNSAFE_IMPROVEMENT_REJECTED,
        CHIPBENCH_FAIL, SAFE_REJECTED, REPLAY_DRIFT,
    }
    extras = {globals()[n] for n in _FAIL_EXTRA if n in globals()}
    return frozenset(base | extras)


def _build_all_statuses():
    base = set(PASS_STATUSES | FAIL_STATUSES)
    extras = {globals()[n] for n in _ALL_EXTRA if n in globals()}
    extras.update({NEEDS_HUMAN_REVIEW, NEEDS_MANUAL_REVIEW, UNSAFE_BLOCKED,
                    HIGH_TOGGLE_WARNING, LINT_SKIPPED_TOOL_MISSING,
                    FORMAL_NOT_READY, FORMAL_SKIPPED_TOOL_MISSING})
    return sorted(base | extras)

# ── SynthBench ───────────────────────────────────────────────────────────────

SYNTHESIS_PASS = "SYNTHESIS_PASS"
SYNTHESIS_FAIL = "SYNTHESIS_FAIL"
SYNTHESIS_SKIPPED_TOOL_MISSING = "SYNTHESIS_SKIPPED_TOOL_MISSING"
SYNTHBENCH_PASS = "SYNTHBENCH_PASS"
SYNTHBENCH_FAIL = "SYNTHBENCH_FAIL"
SYNTHBENCH_PUBLIC_WORDING = (
    "SynthBench runs structural checks and synthesis proxy metrics. "
    "It does not guarantee silicon correctness, timing signoff, real power, "
    "real area, or fabrication readiness."
)
SYNTHBENCH_LIMITATION = (
    "SynthBench uses Yosys cell counts as a synthesis proxy. These are not "
    "foundry-correlated area measurements. No STA, no power analysis, "
    "no DRC/LVS signoff."
)
AREA_IMPROVED = "AREA_IMPROVED"
AREA_REGRESSED = "AREA_REGRESSED"
TIMING_IMPROVED = "TIMING_IMPROVED"
TIMING_REGRESSED = "TIMING_REGRESSED"
POWER_PROXY_IMPROVED = "POWER_PROXY_IMPROVED"
POWER_PROXY_REGRESSED = "POWER_PROXY_REGRESSED"
NEEDS_REAL_SYNTHESIS = "NEEDS_REAL_SYNTHESIS"

# ── SiliconBench ─────────────────────────────────────────────────────────────

SILICON_READINESS_PASS = "SILICON_READINESS_PASS"
SILICON_READINESS_FAIL = "SILICON_READINESS_FAIL"
SILICON_PUBLIC_WORDING = (
    "SiliconBench checks tool-flow readiness. It does not guarantee "
    "silicon correctness, fabrication readiness, timing signoff, real power, "
    "real area, or open-source tool-flow results."
)
SILICON_LIMITATION = (
    "SiliconBench performs tool-flow readiness checks. It verifies that "
    "lint, synthesis, and formal tools can be invoked. It does not "
    "verify that any hardware design is correct, manufacturable, or safe. "
    "These are not silicon results."
)
ASIC_FLOW_READY = "ASIC_FLOW_READY"
ASIC_FLOW_FAIL = "ASIC_FLOW_FAIL"
ASIC_FLOW_SKIPPED_TOOL_MISSING = "ASIC_FLOW_SKIPPED_TOOL_MISSING"
RESET_RECOVERY_PASS = "RESET_RECOVERY_PASS"
RESET_RECOVERY_FAIL = "RESET_RECOVERY_FAIL"

# ── FPGABench ────────────────────────────────────────────────────────────────

FPGA_BENCH_PASS = "FPGA_BENCH_PASS"
FPGA_BENCH_FAIL = "FPGA_BENCH_FAIL"
FPGA_PUBLIC_WORDING = (
    "FPGABench checks FPGA tool-flow readiness. It does not guarantee real "
    "hardware behaviour, timing signoff, power consumption, or bitstream "
    "correctness on any physical FPGA."
)
FPGA_LIMITATION = (
    "FPGABench is a tool-flow readiness check. It does not place, route, "
    "or program any physical FPGA. No real timing, power, or resource "
    "utilisation data from an actual device is produced."
)
FPGA_FLOW_PASS = "FPGA_FLOW_PASS"
FPGA_FLOW_FAIL = "FPGA_FLOW_FAIL"
FPGA_FLOW_SKIPPED_TOOL_MISSING = "FPGA_FLOW_SKIPPED_TOOL_MISSING"
FPGA_SYNTH_PASS = "FPGA_SYNTH_PASS"
FPGA_SYNTH_FAIL = "FPGA_SYNTH_FAIL"
FPGA_SYNTH_SKIPPED_TOOL_MISSING = "FPGA_SYNTH_SKIPPED_TOOL_MISSING"
BITSTREAM_READY = "BITSTREAM_READY"
BITSTREAM_FAIL = "BITSTREAM_FAIL"
BITSTREAM_SKIPPED_TOOL_MISSING = "BITSTREAM_SKIPPED_TOOL_MISSING"
BOARD_PROFILE_VALID = "BOARD_PROFILE_VALID"
BOARD_PROFILE_INVALID = "BOARD_PROFILE_INVALID"
BOARD_EVIDENCE_ATTACHED = "BOARD_EVIDENCE_ATTACHED"
BOARD_EVIDENCE_FAIL = "BOARD_EVIDENCE_FAIL"
BOARD_EVIDENCE_MISSING = "BOARD_EVIDENCE_MISSING"

# ── TinyTapeoutPrep ──────────────────────────────────────────────────────────

TINYTAPEOUT_PREP_PASS = "TINYTAPEOUT_PREP_PASS"
TINYTAPEOUT_PREP_FAIL = "TINYTAPEOUT_PREP_FAIL"
TINYTAPEOUT_PUBLIC_WORDING = (
    "TinyTapeoutPrep checks whether a DTL gate design meets TinyTapeout "
    "submission requirements. It does not guarantee the design is correct, safe, "
    "or ready for fabrication."
)
TINYTAPEOUT_LIMITATION = (
    "TinyTapeoutPrep performs structural checks against TinyTapeout "
    "submission rules. It does not run synthesis, timing analysis, DRC/LVS, "
    "or any real physical verification. This does not mean the design "
    "is correct or safe. The final TinyTapeout shuttle check "
    "must be performed through the official TinyTapeout process."
)
TT_PINOUT_VALID = "TT_PINOUT_VALID"
TT_PINOUT_INVALID = "TT_PINOUT_INVALID"
TT_WRAPPER_CREATED = "TT_WRAPPER_CREATED"
TT_WRAPPER_MISSING = "TT_WRAPPER_MISSING"
TT_TESTBENCH_CREATED = "TT_TESTBENCH_CREATED"
TT_DOCS_CREATED = "TT_DOCS_CREATED"
TT_INFO_YAML_CREATED = "TT_INFO_YAML_CREATED"
TT_SUBMISSION_CHECK_PASS = "TT_SUBMISSION_CHECK_PASS"
TT_SUBMISSION_CHECK_FAIL = "TT_SUBMISSION_CHECK_FAIL"
TT_EVIDENCE_PACK_CREATED = "TT_EVIDENCE_PACK_CREATED"
TT_PRIVATE_LEAK_DETECTED = "TT_PRIVATE_LEAK_DETECTED"
TT_SAFETY_PROPERTY_MISSING = "TT_SAFETY_PROPERTY_MISSING"
TT_READY_FOR_MANUAL_REVIEW = "TT_READY_FOR_MANUAL_REVIEW"
NEEDS_OFFICIAL_TINYTAPEOUT_CHECK = "NEEDS_OFFICIAL_TINYTAPEOUT_CHECK"

# ── Longevity ────────────────────────────────────────────────────────────────

LONGEVITY_PASS = "LONGEVITY_PASS"
LONGEVITY_FAIL = "LONGEVITY_FAIL"

# ── Evidence ─────────────────────────────────────────────────────────────────

EVIDENCE_PACK_CREATED = "EVIDENCE_PACK_CREATED"

# ── OpenLanePhysicalBench ────────────────────────────────────────────────────

PHYSICAL_BENCH_PASS = "PHYSICAL_BENCH_PASS"
PHYSICAL_BENCH_FAIL = "PHYSICAL_BENCH_FAIL"
PHYSICAL_PUBLIC_WORDING = (
    "OpenLanePhysicalBench checks physical-flow readiness. It does not guarantee "
    "silicon correctness, fabrication readiness, timing signoff, real power, "
    "real area, or physical safety."
)
PHYSICAL_LIMITATION = (
    "OpenLanePhysicalBench is a physical-flow readiness check. It parses "
    "DRC/LVS/timing/area reports and hashes GDS artifacts. It does not run "
    "a full OpenLane flow or verify that a design is tapeout-ready."
)
DRC_CLEAN = "DRC_CLEAN"
DRC_VIOLATIONS_FOUND = "DRC_VIOLATIONS_FOUND"
DRC_SKIPPED_NO_REPORT = "DRC_SKIPPED_NO_REPORT"
LVS_CLEAN = "LVS_CLEAN"
LVS_MISMATCH_FOUND = "LVS_MISMATCH_FOUND"
LVS_SKIPPED_NO_REPORT = "LVS_SKIPPED_NO_REPORT"
TIMING_REPORT_PASS = "TIMING_REPORT_PASS"
TIMING_REPORT_FAIL = "TIMING_REPORT_FAIL"
TIMING_REPORT_SKIPPED = "TIMING_REPORT_SKIPPED"
PLACE_ROUTE_PASS = "PLACE_ROUTE_PASS"
PLACE_ROUTE_FAIL = "PLACE_ROUTE_FAIL"
PLACE_ROUTE_SKIPPED_TOOL_MISSING = "PLACE_ROUTE_SKIPPED_TOOL_MISSING"
OPENLANE_CONFIG_PASS = "OPENLANE_CONFIG_PASS"
OPENLANE_CONFIG_FAIL = "OPENLANE_CONFIG_FAIL"
OPENROAD_RUN_PASS = "OPENROAD_RUN_PASS"
OPENROAD_SKIPPED_TOOL_MISSING = "OPENROAD_SKIPPED_TOOL_MISSING"
GDS_HASH_CREATED = "GDS_HASH_CREATED"
GDS_MISSING = "GDS_MISSING"
NEEDS_OFFICIAL_OPENLANE_RUN = "NEEDS_OFFICIAL_OPENLANE_RUN"

# ── RealToolchainCI (Phase 11) ──────────────────────────────────────────────

CI_PASS = "CI_PASS"
CI_FAIL = "CI_FAIL"
CI_PARTIAL = "CI_PARTIAL"
TOOLCHAIN_FOUND = "TOOLCHAIN_FOUND"
TOOLCHAIN_MISSING = "TOOLCHAIN_MISSING"

VERILATOR_CI_PASS = "VERILATOR_CI_PASS"
VERILATOR_CI_FAIL = "VERILATOR_CI_FAIL"
VERILATOR_CI_SKIPPED = "VERILATOR_CI_SKIPPED"

YOSYS_CI_PASS = "YOSYS_CI_PASS"
YOSYS_CI_FAIL = "YOSYS_CI_FAIL"
YOSYS_CI_SKIPPED = "YOSYS_CI_SKIPPED"

SYMBIYOSYS_CI_PASS = "SYMBIYOSYS_CI_PASS"
SYMBIYOSYS_CI_FAIL = "SYMBIYOSYS_CI_FAIL"
SYMBIYOSYS_CI_SKIPPED = "SYMBIYOSYS_CI_SKIPPED"

OPENLANE_CI_PASS = "OPENLANE_CI_PASS"
OPENLANE_CI_FAIL = "OPENLANE_CI_FAIL"
OPENLANE_CI_SKIPPED = "OPENLANE_CI_SKIPPED"

OPENROAD_CI_PASS = "OPENROAD_CI_PASS"
OPENROAD_CI_FAIL = "OPENROAD_CI_FAIL"
OPENROAD_CI_SKIPPED = "OPENROAD_CI_SKIPPED"

CI_ARTIFACTS_CREATED = "CI_ARTIFACTS_CREATED"
CI_PUBLIC_WORDING = (
    "RealToolchainCI records available open-source hardware toolchain checks "
    "and their outputs. Passing CI does not guarantee silicon correctness, "
    "fabrication readiness, physical safety, timing signoff, real power or "
    "real area."
)
CI_LIMITATION = (
    "These CI results record which toolchain stages were available and which "
    "checks passed. They do not guarantee silicon correctness, fabrication "
    "readiness, physical safety, timing signoff, real power, real area, or "
    "regulatory conformance. A stage marked SKIPPED means the tool was not "
    "installed, not that the design failed. Real results require foundry "
    "PDK, DRC/LVS signoff, and physical measurement."
)

# ── FormalGate-Lite (Phase 12) ──────────────────────────────────────────

FORMALGATE_PASS = "FORMALGATE_PASS"
FORMALGATE_FAIL = "FORMALGATE_FAIL"
FORMAL_PROPERTY_PASS = "FORMAL_PROPERTY_PASS"
FORMAL_PROPERTY_FAIL = "FORMAL_PROPERTY_FAIL"
FORMAL_PROPERTY_SKIPPED = "FORMAL_PROPERTY_SKIPPED"
FORMAL_INCONCLUSIVE = "FORMAL_INCONCLUSIVE"
FORMAL_TIMEOUT = "FORMAL_TIMEOUT"
FORMAL_COUNTEREXAMPLE_FOUND = "FORMAL_COUNTEREXAMPLE_FOUND"
FORMAL_SOLVER_MISSING = "FORMAL_SOLVER_MISSING"
PROPERTY_FILE_CREATED = "PROPERTY_FILE_CREATED"
PROPERTY_FILE_MISSING = "PROPERTY_FILE_MISSING"
FORMAL_EVIDENCE_CREATED = "FORMAL_EVIDENCE_CREATED"
NEEDS_DEEP_FORMAL_REVIEW = "NEEDS_DEEP_FORMAL_REVIEW"
NEEDS_PHYSICAL_SIGNOFF = "NEEDS_PHYSICAL_SIGNOFF"
FORMALGATE_PUBLIC_WORDING = (
    "FormalGate-Lite runs structural formal property checks on small DTL-gated "
    "RTL designs. It does not prove chip correctness, fabrication readiness, "
    "timing signoff, physical safety, or real-world actuation safety."
)
FORMALGATE_LIMITATION = (
    "FormalGate-Lite generates SBY property files and optionally runs bounded "
    "model checks. Passing does not mean the design is verified, correct, or "
    "safe. A SKIPPED property means the solver was not available, not that the "
    "property was verified."
)

# ── MutationBench (Phase 13) ─────────────────────────────────────────

MUTATIONBENCH_PASS = "MUTATIONBENCH_PASS"
MUTATIONBENCH_FAIL = "MUTATIONBENCH_FAIL"
MUTATION_GENERATED = "MUTATION_GENERATED"
MUTATION_DETECTED = "MUTATION_DETECTED"
MUTATION_ESCAPED = "MUTATION_ESCAPED"
MUTATION_BLOCKED = "MUTATION_BLOCKED"
MUTATION_REPLAY_MATCH = "MUTATION_REPLAY_MATCH"
MUTATION_REPLAY_DRIFT = "MUTATION_REPLAY_DRIFT"
UNSAFE_BYPASS_DETECTED = "UNSAFE_BYPASS_DETECTED"
UNSAFE_BYPASS_ESCAPED = "UNSAFE_BYPASS_ESCAPED"
KILL_SWITCH_MUTATION_DETECTED = "KILL_SWITCH_MUTATION_DETECTED"
TIMEOUT_MUTATION_DETECTED = "TIMEOUT_MUTATION_DETECTED"
RESET_MUTATION_DETECTED = "RESET_MUTATION_DETECTED"
FSM_ESCAPE_DETECTED = "FSM_ESCAPE_DETECTED"
SHADOW_SIGNAL_DETECTED = "SHADOW_SIGNAL_DETECTED"
PRIVATE_LEAK_DETECTED = "PRIVATE_LEAK_DETECTED"
NEEDS_RULE_HARDENING = "NEEDS_RULE_HARDENING"
MUTATIONBENCH_PUBLIC_WORDING = (
    "MutationBench stress-tests ChipGate by attacking safe RTL with "
    "thousands of unsafe mutations and bypass attempts. It does not prove "
    "full chip correctness, physical safety, fabrication readiness, timing "
    "closure or real-world security."
)
MUTATIONBENCH_LIMITATION = (
    "MutationBench generates known-unsafe RTL variants and checks "
    "whether ChipGate detects them. Passing does not prove the design "
    "is secure, physically safe, fabricated, timing-closed or fully "
    "verified. Escaped mutations indicate potential rule gaps that need "
    "hardening."
)

# ── Build the status sets now that all constants are defined ──────────────

PASS_STATUSES = _build_pass_statuses()
FAIL_STATUSES = _build_fail_statuses()
ALL_STATUSES = _build_all_statuses()