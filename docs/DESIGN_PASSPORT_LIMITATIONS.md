# Design Passport Limitations

## Core Limitation

DTL Verified Design Passport does not prove that a design is correct, safe, certified, fabrication-ready, commercially validated or ready for real-world use. It records the configured checks, evidence, limitations and replay status for a specific artifact.

## What the Passport Does NOT Prove

- Design correctness
- Fabrication readiness
- Timing closure
- Physical safety
- Commercial viability
- Medical safety
- Defence safety
- Robotics safety
- Real-world actuator safety
- Independent validation
- Production readiness
- Deployment suitability

## What the Passport Records

- What was checked (configured gates)
- What passed
- What failed
- What evidence exists
- What replay command can reproduce the decision
- Whether export/build/simulation should be allowed, blocked or sent to review

## Important Notes

- Badge states are labels only and do not constitute safety guarantees
- Gate simulation is deterministic based on content heuristics, not real toolchains
- No private JARVI3/DTL imports are used
- No `shell=True` subprocess calls
- The passport is a structured verification record, not a certification
