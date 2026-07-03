# Adapter Framework

## Overview

ChipGate v0.3.0 introduces an adapter framework that provides a clean
black-box boundary between the benchmark runner and proposal sources.

The public repository only knows:

    input case context → adapter returns candidate RTL + metadata

Private DTL/JARVI3 internals stay outside the public repo.

## Adapter Contract

Every adapter receives a `ProposalInput` and returns a `ProposalResult`:

**Input (ProposalInput):**

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | str | Unique benchmark case identifier |
| `rtl_before` | str | Baseline RTL before mutation |
| `mutation_set` | List[tuple] | (name, description) of mutations applied |
| `risk_level` | str | Expected risk level |
| `expected_gate_requirements` | List[str] | Expected gate signals |

**Output (ProposalResult):**

| Field | Type | Description |
|-------|------|-------------|
| `proposal_id` | str | Unique proposal identifier |
| `proposed_rtl` | str | Candidate RTL to evaluate |
| `proposal_source` | str | Source label (e.g. "synthetic", "external_dtl") |
| `adapter_name` | str | Adapter name |
| `adapter_version` | str | Adapter version |
| `confidence` | float? | Optional confidence score (0.0–1.0) |
| `route_label` | str? | Optional routing label (e.g. "safety_gate_missing") |
| `reason` | str? | Optional reason for the decision |
| `metadata` | dict? | Optional additional metadata |

## Built-in Adapters

### SyntheticAdapter (default)

Returns the built-in mutation-generated RTL proposals.
No AI model is involved. Source label: `"synthetic"`.

```python
from chipgate.adapters.synthetic_adapter import SyntheticAdapter
adapter = SyntheticAdapter()
proposal = adapter.get_proposal(proposal_input)
```

### JSONLAdapter

Reads proposals from an external JSONL file.
Each line is a JSON object with at least: `case_id`, `proposed_rtl`, `proposal_source`.

This is the recommended way to feed external DTL/JARVI3 results into the
benchmark without exposing private code.

```python
from chipgate.adapters.jsonl_adapter import JSONLAdapter
adapter = JSONLAdapter("path/to/proposals.jsonl")
proposal = adapter.get_proposal(proposal_input)
```

CLI usage:

```bash
python -m chipgate bench --mode external_dtl --adapter proposals.jsonl --json
```

### Example External DTL Adapter

See `chipgate/adapters/external_dtl_adapter.example.py` for a template.
This is NOT functional — it shows the interface you should implement.

## Writing a Custom Adapter

1. Subclass `BaseAdapter` from `chipgate.adapters.base`.
2. Implement `name`, `version`, `source_label`, and `get_proposal()`.
3. Export results via JSONL (recommended) or pass the adapter via `--adapter`.

**Do NOT commit private DTL internals to the public repo.**

## Public-Safe Wording

This adapter framework is a benchmark boundary interface. It does not
expose private DTL/JARVI3 internals. Model-connected testing is future
work. The public repository provides the benchmark harness, adapters,
and scoring.