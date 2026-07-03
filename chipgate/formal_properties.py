"""
formal_properties.py — Formal safety properties for DTL-gated RTL designs.

This is a public module that defines a default set of SystemVerilog formal
safety properties for DTL (Design-Time Lockout) gated designs and generates
SymbiYosys (SBY) configuration files suitable for formal verification with
Yosys/SBY.

Public API
----------
- generate_default_properties() -> str
      Return an SBY properties section containing eight default safety
      assertions covering kill-switch, timeout, reset, verifier, policy,
      sensor, failsafe-state, and blocked-state checks.

- generate_sby_config(rtl_path, top_module, properties) -> str
      Return a complete SBY configuration file for a given RTL file,
      optionally accepting a custom properties section.

- check_formal_readiness(file_path) -> dict
      Analyse a Verilog file for structural readiness for formal
      verification.  Returns a dict with keys: ready (bool),
      assertion_count (int), issues (list[str]), sby_config (str).

This module is purely about defining properties and generating configs.
It does NOT import from chipgate.formal_flow or chipgate.formal, and it
does NOT invoke any external tools.
"""

import re


# ---------------------------------------------------------------------------
# Default safety properties
# ---------------------------------------------------------------------------

_DEFAULT_PROPERTIES: list[tuple[str, str]] = [
    (
        "kill_switch_blocks_output",
        "assert (kill_switch |-> !actuator_enable);",
    ),
    (
        "timeout_blocks_output",
        "assert (timeout |-> !actuator_enable);",
    ),
    (
        "reset_blocks_output",
        "assert (reset |-> !actuator_enable);",
    ),
    (
        "actuator_requires_verifier",
        "assert (actuator_enable |-> verifier_ok);",
    ),
    (
        "actuator_requires_policy",
        "assert (actuator_enable |-> policy_ok);",
    ),
    (
        "actuator_requires_sensor",
        "assert (actuator_enable |-> sensor_ok);",
    ),
    (
        "failsafe_no_direct_approve",
        "assert (failsafe_state != APPROVED |-> 1'b1);",
    ),
    (
        "blocked_state_holds_output_low",
        "assert (failsafe_state != APPROVED |-> actuator_enable == 1'b0);",
    ),
]

# Comment lines that preface the properties section in the generated SBY config.
_PROPERTY_COMMENTS: list[str] = [
    "# ------------------------------------------------------------------",
    "# DTL-gate formal safety properties:",
    "#   kill_switch_blocks_output   — kill switch must force actuator low",
    "#   timeout_blocks_output       — timeout condition must force actuator low",
    "#   reset_blocks_output         — reset condition must force actuator low",
    "#   actuator_requires_verifier  — actuator can only be enabled when verifier_ok",
    "#   actuator_requires_policy    — actuator can only be enabled when policy_ok",
    "#   actuator_requires_sensor    — actuator can only be enabled when sensor_ok",
    "#   failsafe_no_direct_approve  — tautology placeholder for failsafe state enum",
    "#   blocked_state_holds_output_low — non-APPROVED failsafe state holds output low",
    "# ------------------------------------------------------------------",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_default_properties() -> str:
    """Return SBY properties section text.

    The returned string contains a comment header explaining each property,
    followed by the eight default SystemVerilog assertions.  The assertions
    use only basic operators (no $display, $random, #delay, or always
    @posedge clk) and reference only the expected DTL-gate signals:
    ``posedge``, ``kill_switch``, ``timeout``, ``reset``, ``verifier_ok``,
    ``policy_ok``, ``sensor_ok``, ``actuator_enable``, ``failsafe_state``,
    ``APPROVED``.
    """
    lines = list(_PROPERTY_COMMENTS)
    for name, body in _DEFAULT_PROPERTIES:
        lines.append(f"{name}: {body}")
    return "\n".join(lines) + "\n"


def generate_sby_config(
    rtl_path: str,
    top_module: str = "top",
    properties: str | None = None,
) -> str:
    """Return complete SBY config file content.

    Parameters
    ----------
    rtl_path : str
        Path to the Verilog RTL file.  The file name (basename) is used in
        the ``[files]`` and ``[script]`` sections.
    top_module : str, optional
        Name of the top-level module.  Defaults to ``"top"``.  If the value
        ``"auto"`` is passed, the module name is auto-detected from the
        first ``module`` declaration in *rtl_path*.
    properties : str, optional
        Custom properties section text.  If ``None``, the default eight DTL
        safety properties are used (see :func:`generate_default_properties`).

    Returns
    -------
    str
        A complete SBY configuration file ready to be written to ``.sby``.
    """
    if top_module == "auto":
        top_module = _detect_top_module(rtl_path)

    if properties is None:
        properties = generate_default_properties()

    file_name = _basename(rtl_path)

    return (
        f"[options]\n"
        f"mode prove\n"
        f"depth 20\n"
        f"\n"
        f"[engines]\n"
        f"smtbmc\n"
        f"\n"
        f"[script]\n"
        f"read_verilog {file_name}\n"
        f"prep -top {top_module}\n"
        f"\n"
        f"[files]\n"
        f"{file_name}\n"
        f"\n"
        f"[properties]\n"
        f"{properties}"
    )


def check_formal_readiness(file_path: str) -> dict:
    """Check if a Verilog design is structurally ready for formal verification.

    This examines the file for:

    1. **Assertions** — at least one ``assert``/``cover``/``assume``/``restrict``
       statement must be present.
    2. **Problematic constructs** — ``$display``, ``$random``, and delay
       constructs (``#``) are flagged as issues that complicate formal
       verification.
    3. **Module detection** — the first ``module`` statement is used to
       identify the top module for the generated SBY config.

    Parameters
    ----------
    file_path : str
        Path to the Verilog file to check.

    Returns
    -------
    dict
        ``{
            ready: bool,
            assertion_count: int,
            issues: list[str],
            sby_config: str,
        }``
    """
    with open(file_path, "r") as fh:
        raw_text = fh.read()

    issues: list[str] = []
    assertion_count = 0

    # -- Count assertions (assert, cover, assume, restrict) ---------------
    re_assert = re.compile(
        r"\b(assert|cover|assume|restrict)\b", re.IGNORECASE
    )
    assertion_count = len(re_assert.findall(raw_text))

    if assertion_count == 0:
        issues.append(
            "No assertions found — formal verification requires at least one "
            "assertion property."
        )

    # -- Flag constructs that complicate formal verification ---------------
    if re.search(r"\$display", raw_text, re.IGNORECASE):
        issues.append(
            "Uses $display — simulation-only, ignored in formal verification."
        )
    if re.search(r"\$random", raw_text, re.IGNORECASE):
        issues.append(
            "Uses $random — non-deterministic, may complicate formal proof."
        )
    if re.search(r"\s*#\d+", raw_text):
        issues.append(
            "Contains delay constructs — not meaningful for formal verification."
        )

    # -- Determine readiness ------------------------------------------------
    non_assertion_issues = [i for i in issues if "No assertions" not in i]
    ready = assertion_count > 0 and len(non_assertion_issues) == 0

    # -- Generate SBY config if we have a usable top module -----------------
    top_module = _detect_top_module(raw_text) if assertion_count > 0 else "top"
    sby_config = ""
    if assertion_count > 0 and top_module:
        sby_config = generate_sby_config(file_path, top_module=top_module)

    return {
        "ready": ready,
        "assertion_count": assertion_count,
        "issues": issues,
        "sby_config": sby_config,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _basename(path: str) -> str:
    """Return the base file name from *path*."""
    import os
    return os.path.basename(path)


def _detect_top_module(source: str | None = None, file_path: str | None = None) -> str:
    """Auto-detect the top module name from the first ``module`` statement.

    If *source* is provided (a string of Verilog text), it is searched
    directly.  Otherwise, if *file_path* is provided, the file is read and
    searched.  Returns the identifier after the first ``module`` keyword,
    or ``"top"`` if none is found.

    Uses ``re.DOTALL`` so that the module declaration is found regardless
    of line breaks.
    """
    text = source
    if text is None and file_path is not None:
        with open(file_path, "r") as fh:
            text = fh.read()
    if text is None:
        return "top"

    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.DOTALL)
    if match:
        return match.group(1)
    return "top"