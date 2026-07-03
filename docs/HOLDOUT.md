# Holdout Cases

## Purpose

Public benchmark cases are included for reproducibility. Private holdout
cases may be used for independent validation.

## Directory Structure

```
benchmarks/
├── chipbench_v0/           # Public cases (committed)
│   └── cases/
└── chipbench_holdout/       # Private holdout (NOT committed)
    └── *.v
```

## How It Works

When the benchmark runner detects a `chipbench_holdout/` directory
alongside the benchmark path, it loads any `.v` files from it as
additional cases with category `"holdout"`.

If the holdout directory is missing, the benchmark skips cleanly with
zero holdout cases. No error is raised.

## Holdout Case Format

Each holdout case is a single `.v` file. The file stem becomes the case ID
(prefixed with `HOLDOUT-`).

Holdout cases have no expected gate result — they are measured, not asserted.

## Publication Guidelines

Holdout results should only be published with clear scope and methodology:

- State clearly which cases are public vs holdout
- Report holdout results separately from public results
- Do not cherry-pick holdout results
- Include the holdout case count

## Why Holdout Matters

Public benchmark cases are visible to anyone. An adversary (or an
overfitted system) could potentially shape responses to match the
public set. Private holdout cases provide honest, independent validation.

This is the same principle used in ML: train on public, validate on
holdout, publish both.