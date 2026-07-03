#!/usr/bin/env python3
"""Run FPGABoardBench demo and save JSON + HTML reports."""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chipgate.fpgabench import run_fpgabench, check_fpga_toolchain, format_fpga_toolchain_status
from chipgate.fpga_report import generate_fpga_html

# ── Run demo ──────────────────────────────────────────────────────────────────
print("Running FPGABoardBench demo...")
result = run_fpgabench(demo=True, board_profile_name="generic_fpga")

# ── Print summary ─────────────────────────────────────────────────────────────
print(f"\nFPGABoardBench v{result.benchmark_version}")
print(f"Timestamp: {result.timestamp_utc}")
print(f"Board Profile: {result.board_profile}")
print(f"Designs Tested: {result.designs_tested}")
print(f"Safety Pass Rate: {result.safety_precheck_pass_rate:.0%}")
print(f"Pin Constraint Pass Rate: {result.pin_constraint_pass_rate:.0%}")
print(f"FPGA Synth Pass Rate: {result.fpga_synth_pass_rate:.0%}")
print(f"Place-Route Pass Rate: {result.place_route_pass_rate:.0%}")
print(f"Bitstream Ready Rate: {result.bitstream_ready_rate:.0%}")
print(f"Board Evidence Attached: {result.board_evidence_attached_count}")
print(f"Evidence Packs Created: {result.evidence_packs_created}")
print(f"Artifact Hashes: {result.artifact_hash_count}")
print(f"Toolchain Coverage: {result.toolchain_coverage:.0%}")
print(f"Overall: {result.overall_status}")

# ── Design table ──────────────────────────────────────────────────────────────
print(f"\n{'Design':<35s} {'Safety':<8s} {'Pin':<8s} {'Synth':<10s} {'PnR':<10s} {'Bitstrm':<10s} {'Overall':<16s}")
print("-" * 105)
for d in result.design_results:
    did = d["design_id"]
    sp = "PASS" if d["safety_precheck_status"] == "RTL_SCAN_PASS" else "FAIL"
    print(f"{did:<35s} {sp:<8s} {d['pin_constraint_status'][:8]:<8s} "
          f"{d['fpga_synth_status'][:10]:<10s} {d['place_route_status'][:10]:<10s} "
          f"{d['bitstream_status'][:10]:<10s} {d['overall_status'][:16]:<16s}")

# ── Save JSON report ──────────────────────────────────────────────────────────
download_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "download")
os.makedirs(download_dir, exist_ok=True)

json_path = os.path.join(download_dir, "fpgabench_demo.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(result.to_dict(), f, indent=2, sort_keys=True, default=str)
print(f"\nJSON report saved: {json_path}")

# ── Save HTML report ──────────────────────────────────────────────────────────
html_path = os.path.join(download_dir, "fpgabench_report.html")
html = generate_fpga_html(result.to_dict())
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML report saved: {html_path}")

# ── Save toolchain status ─────────────────────────────────────────────────────
tc = check_fpga_toolchain()
tc_path = os.path.join(download_dir, "fpga_toolchain_status.json")
with open(tc_path, "w", encoding="utf-8") as f:
    json.dump(tc, f, indent=2, sort_keys=True)
print(f"Toolchain status saved: {tc_path}")

print("\n--- Toolchain Status ---")
print(format_fpga_toolchain_status(tc))

print("\nDone.")