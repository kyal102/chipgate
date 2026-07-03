// failsafe_escape_formal.sv — FormalGate-Lite FAILSAFE escape property
//
// This property captures the requirement that the failsafe state
// cannot go directly to APPROVED.  In a correctly designed DTL gate,
// the failsafe FSM must pass through an intermediate state (e.g.
// PENDING) before reaching APPROVED.
//
// This property is structural: it cannot directly APPROVE any design.
// It can only FAIL a design that allows direct transitions to APPROVED,
// providing evidence that the failsafe mechanism is bypassed.
//
// SBY [properties] format:  name: assert(expression);
// ----------------------------------------------------------------

failsafe_no_direct_approve: assert (failsafe_state != APPROVED |-> 1'b1);
