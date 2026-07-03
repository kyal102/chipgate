#!/usr/bin/env python3
"""
Generate DTL proposals JSONL for Phase 4 DTL-connected proof run.

Simulates an external DTL system that reviews each benchmark case:
- Unsafe cases ("block"): ~85% caught (corrected to safe), ~15% missed (still unsafe)
- Safe cases ("pass"): always pass through unchanged

The catch/miss decision is deterministic via SHA-256(case_id) % 100 to ensure
reproducibility across runs (Python's built-in hash() is randomized per process
since 3.3, so we use hashlib instead).

Output: /home/z/my-project/chipgate/download/results/dtl_proposals.jsonl
"""

import hashlib
import json
import os
import sys

# Ensure chipgate package is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from chipgate.bench_cases import generate_all_cases


# ── Safe RTL template for DTL corrections ────────────────────────────────────

SAFE_RTL_TEMPLATE = """\
module dtl_corrected_{case_id} (
    input  clk,
    input  rst_n,
    input  ai_output,
    input  verifier_ok,
    input  policy_ok,
    input  kill_switch,
    output reg actuator_enable
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) actuator_enable <= 1'b0;
        else actuator_enable <= ai_output && verifier_ok && policy_ok && !kill_switch;
    end
endmodule"""


# ── Constants ─────────────────────────────────────────────────────────────────

OUTPUT_PATH = os.path.join(PROJECT_ROOT, "download", "results", "dtl_proposals.jsonl")
ADAPTER_NAME = "external_dtl_sim"
ADAPTER_VERSION = "1.0.0"
PROPOSAL_SOURCE = "external_dtl"

# hash(case_id) % 100 < DTL_CATCH_THRESHOLD means DTL catches the issue
DTL_CATCH_THRESHOLD = 85


def deterministic_hash(case_id: str) -> int:
    """Deterministic hash of case_id using SHA-256, mapped to 0-99."""
    digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % 100


def build_proposal(case, proposal_index):
    """Build a single DTL proposal dict for the given bench case."""
    case_id = case.case_id
    proposal_id = f"dtl-{proposal_index:03d}"

    if case.expected_gate_result == "block":
        # Unsafe case — DTL may catch or miss
        h = deterministic_hash(case_id)
        if h < DTL_CATCH_THRESHOLD:
            # DTL catches the unsafe pattern and proposes a safe correction
            proposed_rtl = SAFE_RTL_TEMPLATE.format(case_id=case_id)
            route_label = "safe_to_proceed"
            reason = "DTL: unsafe pattern detected and corrected"
        else:
            # DTL misses the unsafe pattern — passes the original unsafe RTL
            proposed_rtl = case.rtl_after
            route_label = "unsafe_path"
            reason = "DTL: unsafe pattern not detected"
    else:
        # Safe case — always pass through
        proposed_rtl = case.rtl_after
        route_label = "safe_to_proceed"
        reason = "DTL: design passes safety check"

    return {
        "case_id": case_id,
        "proposal_id": proposal_id,
        "proposed_rtl": proposed_rtl,
        "proposal_source": PROPOSAL_SOURCE,
        "adapter_name": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "route_label": route_label,
        "reason": reason,
    }


def main():
    cases = generate_all_cases()

    # Counters
    total = 0
    safe_corrections = 0      # unsafe cases caught by DTL
    unsafe_misses = 0         # unsafe cases missed by DTL
    safe_passes = 0           # safe cases passed through

    proposals = []
    for idx, case in enumerate(cases, start=1):
        proposal = build_proposal(case, idx)
        proposals.append(proposal)
        total += 1

        if case.expected_gate_result == "block":
            if proposal["route_label"] == "safe_to_proceed":
                safe_corrections += 1
            else:
                unsafe_misses += 1
        else:
            safe_passes += 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Write JSONL
    with open(OUTPUT_PATH, "w") as f:
        for proposal in proposals:
            f.write(json.dumps(proposal, ensure_ascii=False) + "\n")

    # Print summary
    print("=" * 60)
    print("DTL Proposals Generation — Phase 4 DTL-Connected Proof Run")
    print("=" * 60)
    print(f"  Total proposals:       {total}")
    print(f"  Safe corrections:      {safe_corrections}  (unsafe cases caught by DTL)")
    print(f"  Unsafe passes:          {unsafe_misses}  (unsafe cases missed by DTL)")
    print(f"  Safe passes:            {safe_passes}  (safe cases passed through)")
    print(f"  DTL catch rate:         {safe_corrections / (safe_corrections + unsafe_misses) * 100:.1f}%"
          if (safe_corrections + unsafe_misses) > 0
          else "  DTL catch rate:         N/A")
    print("-" * 60)
    print(f"  Output file:           {OUTPUT_PATH}")
    print(f"  Adapter:               {ADAPTER_NAME} v{ADAPTER_VERSION}")
    print(f"  Determinism:           SHA-256(case_id) % 100 < {DTL_CATCH_THRESHOLD}")
    print("=" * 60)


if __name__ == "__main__":
    main()
