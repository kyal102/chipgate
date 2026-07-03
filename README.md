<p align="center"><img src="assets/chipgate_logo.png" alt="ChipGate" width="140"></p>

# ChipGate Lite

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![license](https://img.shields.io/badge/license-MIT-green) ![deps](https://img.shields.io/badge/dependencies-stdlib--only-blue)

**A deterministic structural sanity checker for Verilog RTL.** Point it at a
`.v` file and it tells you — same answer every run, no model, no network, no
dependencies — whether the design has structural problems that commonly slip
out of AI-generated (or hurried human) RTL: undriven outputs, multi-driven
signals, latch-inference risks, and blocking/nonblocking misuse.

```bash
python -m chipgate design.v
```

## 60-second demo

```bash
git clone https://github.com/kyal102/chipgate
cd chipgate
python -m chipgate examples/bad_alu.v
```

Real output:

```text
examples/bad_alu.v  (modules: bad_alu)
  line   13  [warning] CASE_NO_DEFAULT: case without default arm in combinational always in module 'bad_alu' (latch-inference risk)
             sugg: add a default arm assigning every output of the case
  line   13  [warning] IF_NO_ELSE: 'if' without matching 'else' in combinational always in module 'bad_alu' (latch-inference risk, heuristic)
             sugg: cover all paths: add an else arm or a default assignment before the if
  line   24  [warning] BLOCKING_IN_SEQ: blocking assignment 'acc = ...' inside edge-triggered always in module 'bad_alu'
             sugg: use nonblocking '<=' for sequential logic
  line   24  [info   ] NO_RESET: edge-triggered always in module 'bad_alu' has no apparent reset
             sugg: confirm registers reach a known state (reset, load, or initial value)
  line    5  [error  ] UNDRIVEN_OUTPUT: output 'status' of module 'bad_alu' is never assigned
             sugg: drive the output with an assign or an always block, or remove the port
  -> CHIPGATE_FAIL  (1 error, 3 warning, 1 info)
```

The bundled [`examples/good_counter.v`](examples/good_counter.v) — a plain
synchronous counter with an async reset — produces `CHIPGATE_PASS` with zero
findings.

## What it checks

| Rule | Severity | What it catches |
|------|----------|-----------------|
| `NO_MODULE` | error | input contains no `module … endmodule` |
| `EMPTY_MODULE` | error | module declares ports but contains no logic at all |
| `UNDRIVEN_OUTPUT` | error | an output port that is never assigned |
| `MULTI_DRIVEN` | error | a signal driven from more than one always block / assign |
| `BLOCKING_IN_SEQ` | warning | blocking `=` inside an edge-triggered always |
| `NONBLOCKING_IN_COMB` | warning | nonblocking `<=` inside a combinational always |
| `CASE_NO_DEFAULT` | warning | combinational `case` with no `default` arm (latch risk) |
| `IF_NO_ELSE` | warning | combinational `if` with no `else` (latch risk, heuristic) |
| `NO_RESET` | info | edge-triggered always with no apparent reset |

Verdicts: **`CHIPGATE_PASS`** (no findings above info), **`CHIPGATE_NEEDS_REVIEW`**
(warnings), **`CHIPGATE_FAIL`** (errors). Exit codes `0` / `2` / `1` respectively,
so it drops straight into CI.

## Usage

```bash
python -m chipgate design.v other.v       # human-readable report per file
python -m chipgate --json design.v        # machine-readable JSON report
python -m chipgate --demo                 # run on the bundled examples
python -m pytest tests -q                 # run the test suite (19 tests)
```

Or install it:

```bash
python -m pip install -e .
chipgate design.v
```

No dependencies — pure Python standard library.

## How it works

`chipgate/rtl_check.py` (~350 lines, readable in one sitting) strips comments
and strings, splits the source into modules, extracts ports, `always` blocks
(with sensitivity lists), continuous assigns, and instantiations, then runs
the fixed rule set above. Comparisons inside conditions are excluded from
assignment detection by blanking parenthesized groups first, so `if (a <= b)`
is never mistaken for a nonblocking assignment.

## What it is — and isn't

This is a **lint-level structural gate**, deliberately small and fully
deterministic. It is **not** a synthesizer, simulator, formal equivalence
checker, or timing tool, and a `CHIPGATE_PASS` does **not** prove functional
correctness, timing closure, fabrication readiness, or safety of any kind.
It answers one narrow question well: *does this RTL have obvious structural
defects that mean it should not yet be trusted or exported?*

See [LIMITATIONS.md](LIMITATIONS.md) for the full statement.

## DesignGuard schema demo (secondary)

The repo also carries the JSON request/response schema used by the private
JARVI3 Chip DesignGuard service, which wraps gates like this one with
evidence packs, replay, and design passports:

```bash
python -m chipgate --schema-demo
```

That prints the documented request/response format (see
[`demo_request.json`](demo_request.json) / [`demo_response.json`](demo_response.json)).
The schema demo contains no checking logic; the checker above is the working
software in this repo.

## Ecosystem

Part of the public gate family: [UnitGate](https://github.com/kyal102/unitgate)
(dimensional analysis) · [ElementGate](https://github.com/kyal102/elementgate)
(chemistry) · [ClaimGate](https://github.com/kyal102/claimgate) ·
[ClaimLint](https://github.com/kyal102/claimlint) ·
[EvidencePack](https://github.com/kyal102/evidencepack) ·
[ReplayGate](https://github.com/kyal102/replaygate) ·
[ClaimStack demo](https://github.com/kyal102/claimstack-demo).
Public lite tools; the full private engine remains private.

**AI proposes. Gates verify.**

MIT © Kyal McAuliffe / EcoKure
