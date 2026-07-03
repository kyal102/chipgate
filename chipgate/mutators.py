"""
ChipGate MutationBench — Mutation generators.

Each mutator takes safe RTL text and produces an unsafe variant.
Mutations are designed to test whether ChipGate can detect the
specific unsafe pattern.

Does not guarantee silicon correctness, fabrication readiness,
timing signoff, physical safety, real power or real area.
"""

import hashlib
import re
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Mutation:
    """A single RTL mutation result."""
    mutation_id: str = ""
    category: str = ""
    description: str = ""
    original_hash: str = ""
    mutated_hash: str = ""
    diff_hash: str = ""
    original_text: str = ""
    mutated_text: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary (excludes full RTL text for compact output)."""
        return {
            "mutation_id": self.mutation_id,
            "category": self.category,
            "description": self.description,
            "original_hash": self.original_hash,
            "mutated_hash": self.mutated_hash,
            "diff_hash": self.diff_hash,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _make_id(category: str, index: int, suffix: str = "") -> str:
    tag = category.upper().replace(" ", "_")[:16]
    return f"MUT_{tag}_{index:04d}{suffix}"


# ── Mutation generators ─────────────────────────────────────────────────

def _remove_verifier_gate(rtl: str) -> str:
    """Remove verifier_ok from actuator enable condition."""
    patterns = [
        (r"ai_output\s*&&\s*verifier_ok\s*&&", "ai_output &&"),
        (r"verifier_ok\s*&&\s*ai_output\s*&&", "ai_output &&"),
        (r"&&\s*verifier_ok\s*&&", "&&"),
        (r"&&\s*verifier_ok\s*;", ";"),
        (r"(\(\s*\S+\s*\))\s*&&\s*verifier_ok", r"\1"),
    ]
    for pat, repl in patterns:
        rtl = re.sub(pat, repl, rtl)
    return rtl


def _remove_policy_gate(rtl: str) -> str:
    """Remove policy_ok from actuator enable condition."""
    patterns = [
        (r"policy_ok\s*&&\s*", ""),
        (r"&&\s*policy_ok", ""),
    ]
    for pat, repl in patterns:
        rtl = re.sub(pat, repl, rtl)
    return rtl


def _remove_sensor_gate(rtl: str) -> str:
    """Remove sensor_ok from actuator enable condition."""
    patterns = [
        (r"sensor_ok\s*&&\s*", ""),
        (r"&&\s*sensor_ok", ""),
    ]
    for pat, repl in patterns:
        rtl = re.sub(pat, repl, rtl)
    return rtl


def _invert_kill_switch(rtl: str) -> str:
    """Invert kill_switch logic: !kill_switch -> kill_switch."""
    rtl = re.sub(r"!\s*kill_switch", "kill_switch", rtl)
    rtl = re.sub(r"kill_switch\s*=\s*1'b0", "kill_switch = 1'b1", rtl)
    return rtl


def _remove_timeout_block(rtl: str) -> str:
    """Remove !timeout from blocking condition."""
    patterns = [
        (r"\|\s*!\s*timeout\s*", ""),
        (r"!\s*timeout\s*\|\s*", ""),
        (r"&&\s*!\s*timeout\s*;", ";"),
        (r"&&\s*!\s*timeout\s*&&", "&&"),
    ]
    for pat, repl in patterns:
        rtl = re.sub(pat, repl, rtl)
    return rtl


def _remove_reset_block(rtl: str) -> str:
    """Remove !reset from blocking condition."""
    patterns = [
        (r"\|\s*!\s*reset\s*", ""),
        (r"!\s*reset\s*\|\s*", ""),
        (r"&&\s*!\s*reset\s*;", ";"),
        (r"&&\s*!\s*reset\s*&&", "&&"),
        (r"&&\s*!\s*reset\b", ""),
        (r"\b!\s*reset\s*&&", ""),
    ]
    for pat, repl in patterns:
        rtl = re.sub(pat, repl, rtl)
    return rtl


def _direct_actuator_bypass(rtl: str) -> str:
    """Replace gated actuator with direct ai_output assignment."""
    rtl = re.sub(
        r"actuator_enable\s*<=\s*[^\n;]+;",
        "    assign actuator_enable = ai_output;",
        rtl,
    )
    rtl = re.sub(
        r"assign\s+actuator_enable\s*=\s*[^\n;]+;",
        "    assign actuator_enable = ai_output;",
        rtl,
    )
    return rtl


def _or_bypass_injection(rtl: str) -> str:
    """Change safe AND chain into unsafe OR chain in gating."""
    patterns = [
        (r"ai_output\s*&&\s*verifier_ok", "ai_output || verifier_ok"),
        (r"verifier_ok\s*&&\s*ai_output", "verifier_ok || ai_output"),
        (r"policy_ok\s*&&\s*sensor_ok", "policy_ok || sensor_ok"),
        (r"sensor_ok\s*&&\s*policy_ok", "sensor_ok || policy_ok"),
    ]
    for pat, repl in patterns:
        rtl = re.sub(pat, repl, rtl)
    return rtl


def _stale_verifier_acceptance(rtl: str) -> str:
    """Add a stale verifier that is always high (bypass)."""
    # Insert a wire declaration for stale_verifier_ok after input declarations
    if "wire stale_verifier_ok" not in rtl:
        # Find last input declaration and insert after it
        match = re.search(
            r"(input\s+\S+\s*;)\n", rtl
        )
        if match:
            insert_pos = match.end()
            rtl = (
                rtl[:insert_pos]
                + "    wire stale_verifier_ok = 1'b1; // STALE VERIFIER MUTATION\n"
                + rtl[insert_pos:]
            )
    # Replace verifier_ok with stale_verifier_ok in the gating
    rtl = re.sub(r"\bverifier_ok\b", "stale_verifier_ok", rtl)
    return rtl


def _failsafe_escape(rtl: str) -> str:
    """Allow FSM to jump directly from BLOCKED to APPROVED."""
    # Find the BLOCKED state and add a direct transition to APPROVED
    rtl = re.sub(
        r"(BLOCKED:\s*begin.*?)"
        r"(\s*actuator_enable\s*<=\s*1'b0;)",
        r"\1if (ai_output) beginsafe_state <= APPROVED; end\2",
        rtl,
        flags=re.DOTALL,
    )
    return rtl


def _blocked_escape(rtl: str) -> str:
    """Allow BLOCKED to transition directly to APPROVED."""
    rtl = re.sub(
        r"(BLOCKED:\s*begin.*?)"
        r"(\s*if\s*\(\s*reset\s*\))",
        r"\1if (ai_output || reset) failsafe_state <= APPROVED; end\2",
        rtl,
        flags=re.DOTALL,
    )
    return rtl


def _glitchy_reset_mutation(rtl: str) -> str:
    """Allow actuator output during reset transition."""
    rtl = re.sub(
        r"if\s*\(!rst_n\)\s*begin",
        "if (!rst_n) begin // GLITCHY RESET MUTATION\n        actuator_enable <= ai_output;",
        rtl,
    )
    return rtl


def _shadow_signal_bypass(rtl: str) -> str:
    """Create a shadow signal that routes actuator around the gate."""
    if "wire hidden_enable" not in rtl:
        match = re.search(r"(input\s+\S+\s*;)\n", rtl)
        if match:
            insert_pos = match.end()
            rtl = (
                rtl[:insert_pos]
                + "    wire hidden_enable; // SHADOW SIGNAL MUTATION\n"
                + rtl[insert_pos:]
            )
    # Replace the final actuator assignment with one using hidden_enable
    rtl = re.sub(
        r"actuator_enable\s*<=\s*[^\n;]+;",
        "    assign actuator_enable = hidden_enable; // SHADOW",
        rtl,
    )
    # Drive hidden_enable from ai_output
    if "assign hidden_enable" not in rtl and "hidden_enable" in rtl:
        rtl = re.sub(
            r"(endmodule)",
            "    assign hidden_enable = ai_output; // SHADOW DRIVE\n\\1",
            rtl,
        )
    return rtl


def _obfuscated_unsafe_expression(rtl: str) -> str:
    """Hide unsafe logic in nested ternary / obfuscated form."""
    rtl = re.sub(
        r"ai_output\s*&&\s*verifier_ok\s*&&\s*policy_ok\s*&&\s*sensor_ok",
        "((ai_output ? ({(verifier_ok && (policy_ok && sensor_ok)) : 1'b0) : 1'b0)",
        rtl,
    )
    return rtl


def _multiline_bypass(rtl: str) -> str:
    """Split unsafe assignment across multiple lines."""
    rtl = re.sub(
        r"actuator_enable\s*<=\s*ai_output\s*&&\s*verifier_ok\s*&&\s*policy_ok\s*&&\s*sensor_ok\s*;",
        (
            "actuator_enable <= ai_output\n"
            "        && verifier_ok\n"
            "        && policy_ok\n"
            "        && sensor_ok; // MULTILINE BYPASS"
        ),
        rtl,
    )
    return rtl


def _duplicate_assignment(rtl: str) -> str:
    """Create conflicting assignments for actuator_enable."""
    if "assign actuator_enable = ai_output" not in rtl:
        pattern = re.compile(
            r"(APPROVED:\s*begin.*?)"
            r"(actuator_enable\s*<=\s*[^\n;]+;)",
            re.DOTALL,
        )
        match = pattern.search(rtl)
        if match:
            rtl = rtl[:match.start()] + match.group(0) + "\n    assign actuator_enable = ai_output; // DUPLICATE CONFLICT" + rtl[match.end():]
    return rtl


def _unsafe_default_state(rtl: str) -> str:
    """Set default FSM state to APPROVED so output starts high."""
    rtl = re.sub(
        r"failsafe_state\s*<=\s*IDLE\s*;",
        "failsafe_state <= APPROVED; // UNSAFE DEFAULT",
        rtl,
    )
    return rtl


def _missing_safety_output(rtl: str) -> str:
    """Remove blocked/failsafe output signal."""
    rtl = re.sub(
        r"output\s+(reg\s+)?\[1:0\]\s+failsafe_state\s*;",
        "output [1:0] failsafe_state; // MISSING SAFETY OUTPUT",
        rtl,
    )
    return rtl


def _unsafe_pin_exposure(rtl: str) -> str:
    """Remove gating and expose actuator_enable directly."""
    # Replace the gated output with a direct passthrough
    rtl = re.sub(
        r"output\s+reg\s+actuator_enable\s*;",
        "output actuator_enable; // UNSAFE PIN EXPOSURE",
        rtl,
    )
    # Remove the gating logic
    rtl = re.sub(
        r"actuator_enable\s*<=\s*[^\n;]+;",
        "    assign actuator_enable = ai_output; // EXPOSED",
        rtl,
    )
    return rtl


def _private_leak_mutation(rtl: str) -> str:
    """Inject a forbidden private name reference."""
    comment = "    // Reference: jarvi3 internal DTL adapter (PRIVATE LEAK TEST)\n"
    # Insert after the first line
    if "module " in rtl:
        rtl = rtl.replace("module ", "module " + comment, 1)
    else:
        rtl = comment + rtl
    return rtl


# ── Catalog ──────────────────────────────────────────────────────────────

MUTATION_CATALOG: List[Tuple[str, str, Callable[[str], str]]] = [
    ("remove_verifier_gate", "Remove verifier_ok from gating", _remove_verifier_gate),
    ("remove_policy_gate", "Remove policy_ok from gating", _remove_policy_gate),
    ("remove_sensor_gate", "Remove sensor_ok from gating", _remove_sensor_gate),
    ("invert_kill_switch", "Invert kill_switch polarity", _invert_kill_switch),
    ("remove_timeout_block", "Remove timeout blocking", _remove_timeout_block),
    ("remove_reset_block", "Remove reset blocking", _remove_reset_block),
    ("direct_actuator_bypass", "Direct ai_output to actuator", _direct_actuator_bypass),
    ("or_bypass", "Replace AND with OR in gating chain", _or_bypass_injection),
    ("stale_verifier", "Bypass with stale always-high verifier", _stale_verifier_acceptance),
    ("failsafe_escape", "FSM jumps BLOCKED to APPROVED", _failsafe_escape),
    ("blocked_escape", "BLOCKED transitions to APPROVED", _blocked_escape),
    ("glitchy_reset", "Actuator active during reset", _glitchy_reset_mutation),
    ("shadow_signal", "Shadow signal bypasses gate", _shadow_signal_bypass),
    ("obfuscated_expression", "Nested ternary hides unsafe logic", _obfuscated_unsafe_expression),
    ("multiline_bypass", "Split unsafe assign across lines", _multiline_bypass),
    ("duplicate_assignment", "Conflicting actuator assignments", _duplicate_assignment),
    ("unsafe_default_state", "Default FSM state is APPROVED", _unsafe_default_state),
    ("missing_safety_output", "Remove blocked output signal", _missing_safety_output),
    ("unsafe_pin_exposure", "Expose actuator without gate", _unsafe_pin_exposure),
    ("private_leak", "Inject forbidden private name", _private_leak_mutation),
]


def get_mutation_names() -> List[str]:
    """Return list of all mutation category names."""
    return [name for name, _, _ in MUTATION_CATALOG]


def apply_mutation(rtl: str, category: str) -> str:
    """Apply a named mutation to RTL text.

    Args:
        rtl: Original RTL source text.
        category: Mutation category name (must exist in catalog).

    Returns:
        Mutated RTL text, or original if category not found.
    """
    for name, _, func in MUTATION_CATALOG:
        if name == category:
            return func(rtl)
    return rtl


def generate_mutations(
    rtl: str,
    count: int = 1000,
    categories: Optional[List[str]] = None,
    seed: int = 42,
) -> List[Mutation]:
    """Generate multiple mutations of an RTL design.

    Args:
        rtl: Original RTL source text.
        count: Number of mutations to generate.
        categories: Optional list of category names. Default: all.
        seed: Random seed for reproducibility.

    Returns:
        List of Mutation objects.
    """
    import random
    rng = random.Random(seed)

    if categories is None:
        categories = get_mutation_names()

    orig_hash = _sha256(rtl)
    results: List[Mutation] = []
    per_cat = max(1, count // len(categories))
    extra = count - per_cat * len(categories)

    for cat_name, _, func in MUTATION_CATALOG:
        if cat_name not in categories:
            continue
        n = per_cat + (1 if categories.index(cat_name) < extra else 0)
        for i in range(n):
            try:
                mutated = func(rtl)
                if mutated == rtl:
                    continue
                mut_hash = _sha256(mutated)
                diff_text = f"{orig_hash}\n{mut_hash}"
                results.append(Mutation(
                    mutation_id=_make_id(cat_name, i),
                    category=cat_name,
                    description=f"{cat_name} mutation variant {i}",
                    original_hash=orig_hash,
                    mutated_hash=mut_hash,
                    diff_hash=_sha256(diff_text),
                    original_text=rtl,
                    mutated_text=mutated,
                ))
            except Exception:
                continue

    return results[:count]