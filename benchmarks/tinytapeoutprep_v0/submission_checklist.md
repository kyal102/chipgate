# TinyTapeout Submission Checklist

This checklist tracks readiness for TinyTapeout submission. Each item must pass before the design is considered ready for manual review on tinytapeout.com. Passing this checklist does not guarantee Tiny Tapeout acceptance or fabrication.

| # | Check | Status |
|---|-------|--------|
| 1 | Top module file exists | PASS |
| 2 | Top module name matches info.yaml | PASS |
| 3 | No private imports or names | PASS |
| 4 | No unsupported SystemVerilog constructs | PASS |
| 5 | No inferred latches | PASS |
| 6 | Clock signal documented | PASS |
| 7 | Reset signal documented | PASS |
| 8 | Pinout documented in info.yaml | PASS |
| 9 | docs/info.md exists | PASS |
| 10 | Testbench exists | PASS |
| 11 | Safety properties listed | PASS |
| 12 | ChipGate scan passes | PASS |
| 13 | LongevityBench: pass or skip safely | SKIP |
| 14 | SiliconReadinessBench: pass or skip safely | SKIP |
| 15 | FPGABoardBench: pass or skip safely | SKIP |

## Notes

- This is an automated structural checklist, not a substitute for official Tiny Tapeout CI or manual review.
- Evidence packs provide SHA-256 hashes for reproducibility but do not constitute fabrication signoff.
- LongevityBench, SiliconReadinessBench, and FPGABoardBench results gracefully degrade to SKIPPED when external tools are unavailable.