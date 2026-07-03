# DTL-Connected Testing

## Status

Model-connected testing is **future work**. The current benchmark is
model-free and tests the ChipGate/DTL verification gate itself using
deterministic synthetic RTL proposals.

## Architecture

When model-connected testing is implemented, the workflow will be:

```
Proposal generator (external AI model)
        │
        ▼
DTL adapter (external, via JSONL)
        │
        ▼
ChipGate scan (deterministic gate)
        │
        ▼
No-regression check
        │
        ▼
EvidencePack
        │
        ▼
Replay
        │
        ▼
Compare against ungated / ChipGate-only baseline
```

## Adapter Boundary

The public repository provides the adapter interface. Private DTL/JARVI3
code stays outside:

- `chipgate/adapters/base.py` — abstract interface
- `chipgate/adapters/synthetic_adapter.py` — built-in synthetic proposals
- `chipgate/adapters/jsonl_adapter.py` — loads external JSONL proposals
- `chipgate/adapters/external_dtl_adapter.example.py` — template

The private DTL system runs externally and exports proposals via JSONL.
The benchmark then compares modes:

1. **ungated_baseline**: Everything goes to heavy verification
2. **chipgate_only**: ChipGate deterministic gates filter cases
3. **external_dtl**: External DTL routes/filters, then ChipGate scans

## Key Metric

The most important metric for model-connected testing is:

> **estimated cost per verified accepted change** under the
> synthetic benchmark cost model.

This is the metric that can demonstrate 10x+ improvement when DTL
is placed before expensive verification.

## What We Can Claim (Model-Free Phase)

- ChipGate blocks unsafe RTL patterns deterministically.
- ChipGate preserves known-safe gated patterns.
- DTL-ChipBench estimates verification workload reduction.
- Replay results are stable and reproducible.

## What We Cannot Claim (Yet)

- Any AI model is faster, safer, or better at chip design.
- Real-world chip speedup or silicon safety.
- DTL beats any specific vendor or tool.

## Roadmap

1. ~~Model-free benchmark (v0.2.0)~~ Done
2. ~~Adapter framework (v0.3.0)~~ Done
3. Connect real model as proposal generator (future)
4. Freeze public test set + private holdout (future)
5. Compare model-only vs model+DTL (future)
6. Publish results after holdout validation (future)