# PPA Proxy Metrics

This document describes the transparent proxy metrics used by ChipSynthBench to estimate Performance-Power-Area characteristics of RTL candidates.

## Critical Disclaimer

These are **RTL-level structural proxy metrics**, not real EDA measurements. They do not represent:

- Gate-level area after synthesis
- Clock frequency or timing signoff
- Dynamic or leakage power consumption
- IR drop or thermal analysis
- Physical layout metrics
- Fabrication readiness

Real PPA analysis requires EDA tools (Yosys, OpenROAD, Synopsys Design Compiler, Cadence Innovus, etc.).

## Area Proxy

### What It Measures

Counts structural RTL elements to estimate relative design complexity:

| Element | Weight | Description |
|---------|--------|-------------|
| Assignment | 1.0 | Each `assign` or `<=`/`=` assignment |
| Register | 3.0 | Each `reg` declaration or non-blocking assignment target |
| Operator | 0.5 | Each `&`, `\|`, `^`, `~`, `+`, `-`, `*`, comparison, shift |
| Mux expression | 4.0 | Ternary `?:`, case blocks, if/else chains |
| FSM state | 5.0 | State definitions, state registers |
| Input/Output | 0.5 | Port declarations |
| Wire | 0.3 | Wire-type port declarations |

### Interpretation

- **Lower is better** — fewer structural elements suggest a simpler design
- Area improvements are only meaningful when the candidate also passes safety checks
- A small unsafe design is never preferred over a larger safe design

### Formula

```
weighted_score = sum(element_count * element_weight)
```

## Timing-Depth Proxy

### What It Measures

Estimates the longest combinational logic chain by analysing expression nesting depth in RTL assignments.

### Method

1. Extract all expressions from `assign` statements and `always` blocks
2. Tokenize each expression into operators and operands
3. Estimate chain depth using a stack-based approach (parentheses increase depth)
4. The `weighted_depth` combines 70% max depth + 30% average depth

### Interpretation

- **Lower depth is better** — suggests potentially faster critical paths
- Only meaningful when no safety regression is introduced
- Does not account for clock frequency, pipeline depth, or physical placement

### Formula

```
weighted_depth = 0.7 * max_depth + 0.3 * avg_depth
```

## Power-Toggle Proxy

### What It Measures

Estimates switching activity risk based on safety-critical signal patterns and design complexity.

### Method

1. Count signals matching safety-critical patterns (actuator, kill_switch, verifier_ok, policy_ok, sensor, watchdog, timeout, failsafe, emergency, enable, reset, clk)
2. Estimate toggle frequency based on how often safety signals appear in expressions
3. Factor in always block count (sequential activity) and assignment count (combinational activity)
4. Combine into a weighted score

### Interpretation

- **Lower is better** — fewer toggles suggest lower dynamic power
- This is a rough proxy only, not a real power estimation
- Does not account for clock gating effectiveness, voltage scaling, or physical capacitance

### Formula

```
toggle_risk_score = min(total_toggle_count * 1.5, 100.0)
weighted_power_proxy = 0.6 * toggle_risk + 0.2 * operator_count + 2.0 * register_count + 3.0 * always_block_count
```

## Design Score

The overall `safe_improvement_score` determines candidate ranking.

### Eligibility

A candidate is eligible for ranking only if ALL of:
- `safety_pass = True`
- `longevity_pass = True`
- `no_regression_pass = True`

### Score Formula

```
safe_improvement_score = 0.35 * max(area_imp, 0)
                        + 0.35 * max(timing_imp, 0)
                        + 0.30 * max(power_imp, 0)
                        - 0.001 * verification_cost
```

### Rules

- Unsafe candidates receive score = -infinity (cannot rank)
- Among eligible candidates, higher score ranks higher
- The top eligible candidate is marked as "best tradeoff"
- Negative PPA improvements are treated as 0 (not penalised beyond lost opportunity)

## Verification Cost Model

Estimated cost per candidate using the same cost tiers as DTL-ChipBench:

| Step | Cost Units |
|------|-----------|
| DTL Scan | 1 |
| Lint | 5 |
| Simulation | 25 |
| Formal | 100 |
| Synthesis | 250 |

Safe candidates that pass the gate require the full pipeline (381 units). Unsafe candidates are blocked at scan (1 unit). This is the same transparent workflow-level cost model used throughout ChipGate.

## Future Work

Integration with real EDA tools would replace these proxy metrics with actual measurements:

- **Area**: Yosys `stat` output, gate count
- **Timing**: OpenROAD STA, clock period, slack
- **Power**: OpenROAD power analysis, dynamic/leakage reports

These integrations are optional — the proxy metrics provide value even without external tools installed.