# ChipSynthBench

ChipSynthBench scores RTL candidates using safety, no-regression, longevity and transparent PPA proxy metrics.

## What It Does

ChipSynthBench measures whether RTL candidates become safer, smaller and faster without regression. It evaluates multiple candidate RTL designs against a baseline, checking safety gates, regression status, and three transparent proxy metrics:

- **Area proxy**: Structural complexity estimate (assignments, registers, operators, mux expressions, FSM states)
- **Timing-depth proxy**: Longest boolean/operator chain estimate
- **Power-toggle proxy**: Safety-critical signal toggle risk estimate

## Important Limitations

ChipSynthBench uses RTL-level proxy metrics. It does not guarantee real silicon performance, real power consumption, timing signoff, area after synthesis, fabrication readiness or physical safety.

These results are RTL-level structural proxy metrics, not real synthesis, STA, or power analysis. Area, timing-depth, and power proxy scores are based on RTL text heuristics (assignment count, expression depth, signal toggle patterns). They do not represent gate-level area, clock frequency, dynamic/leakage power, or any physical measurement. Real results require EDA synthesis, STA, and power estimation tools.

## Usage

```bash
# Demo run (7 candidates)
python -m chipgate synth --demo

# Full run with all 10 built-in candidates
python -m chipgate synth

# JSON output
python -m chipgate synth --json

# HTML report
python -m chipgate synth --html synthbench_report.html

# Show ranked candidates
python -m chipgate synth --rank

# Run from benchmark directory
python -m chipgate synth benchmarks/synthbench_v0 --json

# Combined
python -m chipgate synth --demo --rank --html demo_report.html
```

## Candidate Categories

| # | Category | Description | Expected Safety |
|---|----------|-------------|-----------------|
| 1 | Baseline safe DTL gate | Standard verified gate | PASS |
| 2 | Fast but unsafe gate | No verification chain | FAIL |
| 3 | Safe but larger gate | FSM with extra safety inputs | PASS |
| 4 | Safe and smaller gate | Minimal structure | PASS |
| 5 | Safe low-toggle gate | Compact ternary style | PASS |
| 6 | Unsafe bypass regression | Missing policy_ok | FAIL |
| 7 | Missing kill-switch regression | No emergency stop | FAIL |
| 8 | Missing verifier regression | No independent check | FAIL |
| 9 | Safe FSM candidate | State machine verification | PASS |
| 10 | Best tradeoff candidate | Safe, compact, clean | PASS |

## Design Score Rules

A candidate can only be ranked as improved if all three checks pass:

1. `safety_status = SYNTHBENCH_PASS`
2. `longevity_status = SYNTHBENCH_PASS`
3. `no_regression_status = NO_REGRESSION_PASS`

The `safe_improvement_score` is then computed as:

```
weighted(area_improvement + timing_improvement + power_improvement) - verification_cost_penalty
```

Unsafe designs **cannot** rank above safe designs even if they look smaller or faster.

## Metrics

| Metric | Description |
|--------|-------------|
| `safety_status` | ChipGate scan pass/fail |
| `longevity_status` | Safety pattern analysis pass/fail |
| `no_regression_status` | Regression check vs baseline |
| `area_proxy` | Weighted structural complexity score |
| `timing_depth_proxy` | Longest expression chain estimate |
| `power_toggle_proxy` | Safety signal toggle risk score |
| `safe_improvement_score` | Weighted PPA improvement minus cost |
| `estimated_verification_cost` | Cost model units (scan/lint/sim/formal/synth) |
| `replay_match_rate` | Deterministic replay consistency |
| `evidence_packs_created` | SHA-256 evidence records |

## Output Files

- **JSON**: Full structured output with all candidate details, PPA comparisons, and rankings
- **HTML**: Self-contained report with summary cards, ranking table, PPA comparison panels, evidence hashes, and limitations
- **Benchmark files**: `benchmarks/synthbench_v0/` contains candidate RTL and manifest

## Future Integrations

- Yosys synthesis report
- Verilator simulation
- cocotb simulation
- SymbiYosys formal checks
- OpenROAD/OpenLane physical reports

External tools are skipped gracefully if not installed.