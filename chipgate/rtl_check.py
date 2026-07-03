"""ChipGate Lite: a deterministic structural sanity checker for Verilog RTL.

Given a Verilog source file, ChipGate Lite parses each module and runs a
fixed set of structural checks that catch common RTL mistakes *before*
synthesis or simulation:

- EMPTY_MODULE          module declares ports but contains no logic
- UNDRIVEN_OUTPUT       an output port is never assigned
- MULTI_DRIVEN          a signal is driven from more than one always block
                        (or from both an always block and a continuous assign)
- BLOCKING_IN_SEQ       blocking '=' used inside an edge-triggered always
- NONBLOCKING_IN_COMB   nonblocking '<=' used inside a combinational always
- CASE_NO_DEFAULT       case statement without a default arm in
                        combinational logic (latch-inference risk)
- IF_NO_ELSE            more 'if's than 'else's in combinational logic
                        (latch-inference risk, heuristic)
- NO_RESET              edge-triggered always with no apparent reset (info)

Everything is pure Python standard library; the analysis is line/token
based, not a full Verilog elaboration. See LIMITATIONS.md: this is a
lint-level structural gate, not a synthesizer, simulator, LEC tool, or a
substitute for a real EDA flow.

Verdicts:
    CHIPGATE_PASS          no findings above info level
    CHIPGATE_NEEDS_REVIEW  warnings present (latch risks, style hazards)
    CHIPGATE_FAIL          errors present (undriven, multi-driven, empty,
                           or the file does not contain a module)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

VERDICT_PASS = "CHIPGATE_PASS"
VERDICT_REVIEW = "CHIPGATE_NEEDS_REVIEW"
VERDICT_FAIL = "CHIPGATE_FAIL"

_VERILOG_KEYWORDS = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg",
    "logic", "integer", "real", "parameter", "localparam", "assign",
    "always", "initial", "begin", "end", "if", "else", "case", "casex",
    "casez", "endcase", "default", "for", "while", "repeat", "forever",
    "posedge", "negedge", "or", "and", "not", "generate", "endgenerate",
    "genvar", "function", "endfunction", "task", "endtask", "signed",
    "unsigned", "supply0", "supply1", "tri", "wand", "wor",
}

_RESET_NAME = re.compile(r"(rst|reset)", re.IGNORECASE)


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments, preserving newlines for line numbers."""
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            end = n if j == -1 else j + 2
            out.append("\n" * text.count("\n", i, end))
            i = end
        elif text[i] in "\"'":
            quote = text[i]
            j = i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


class AlwaysBlock:
    def __init__(self, sensitivity: str, body: str, line: int) -> None:
        self.sensitivity = sensitivity
        self.body = body
        self.line = line
        self.is_sequential = bool(re.search(r"\b(posedge|negedge)\b", sensitivity))

    def assignments(self) -> List[Tuple[str, str]]:
        """Return (signal, operator) pairs assigned in this block.

        Comparisons are excluded by first blanking parenthesized groups
        (if/case conditions), then matching assignment statements.
        """
        body = self.body
        # Blank the contents of parens so '<=' / '==' comparisons inside
        # conditions are not mistaken for assignments.
        prev = None
        while prev != body:
            prev = body
            body = re.sub(r"\(([^()]*)\)", lambda m: "(" + " " * len(m.group(1)) + ")", body)
        pairs: List[Tuple[str, str]] = []
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(<=|=)(?![=>])", body):
            name, op = m.group(1), m.group(2)
            if name in _VERILOG_KEYWORDS:
                continue
            pairs.append((name, op))
        return pairs


class Module:
    def __init__(self, name: str, header: str, body: str, line: int) -> None:
        self.name = name
        self.header = header
        self.body = body
        self.line = line
        self.body_line = line + header.count("\n")
        self.outputs = self._collect_ports("output")
        self.always_blocks = self._collect_always()
        self.assign_lhs = self._collect_assign_lhs()
        self.has_instances = self._detect_instances()

    def _collect_ports(self, direction: str) -> List[str]:
        names: List[str] = []
        for scope in (self.header, self.body):
            for m in re.finditer(
                rf"\b{direction}\b\s*(?:reg|wire|logic|signed|unsigned)?\s*"
                rf"(?:signed|unsigned)?\s*(?:\[[^\]]*\]\s*)?([A-Za-z_][\w\s,]*)",
                scope,
            ):
                for part in m.group(1).split(","):
                    token = part.strip().split()[-1] if part.strip() else ""
                    if token and token not in _VERILOG_KEYWORDS and re.fullmatch(r"[A-Za-z_]\w*", token):
                        names.append(token)
        seen: List[str] = []
        for n in names:
            if n not in seen:
                seen.append(n)
        return seen

    def _collect_always(self) -> List[AlwaysBlock]:
        blocks: List[AlwaysBlock] = []
        for m in re.finditer(r"\balways\b\s*(@\s*(?:\(|\*))?", self.body):
            start = m.end()
            sensitivity = ""
            if m.group(1):
                if m.group(1).rstrip().endswith("*"):
                    sensitivity = "*"
                else:
                    depth, j = 1, start
                    while j < len(self.body) and depth:
                        if self.body[j] == "(":
                            depth += 1
                        elif self.body[j] == ")":
                            depth -= 1
                        j += 1
                    sensitivity = self.body[m.end():j - 1]
                    start = j
            body = self._block_body(start)
            blocks.append(AlwaysBlock(sensitivity, body, _line_of(self.body, m.start()) + self.body_line - 1))
        return blocks

    def _block_body(self, start: int) -> str:
        rest = self.body[start:]
        m = re.match(r"\s*begin\b", rest)
        if not m:
            end = rest.find(";")
            return rest[: end + 1 if end != -1 else len(rest)]
        depth, i = 1, m.end()
        while i < len(rest) and depth:
            km = re.compile(r"\b(begin|end)\b").search(rest, i)
            if not km:
                break
            depth += 1 if km.group(1) == "begin" else -1
            i = km.end()
        return rest[m.end():i]

    def _collect_assign_lhs(self) -> List[Tuple[str, int]]:
        out: List[Tuple[str, int]] = []
        for m in re.finditer(r"\bassign\b\s+([A-Za-z_]\w*)", self.body):
            out.append((m.group(1), _line_of(self.body, m.start()) + self.body_line - 1))
        return out

    def _detect_instances(self) -> bool:
        for m in re.finditer(r"^[ \t]*([A-Za-z_]\w*)\s*(?:#\s*\([^;]*?\)\s*)?\s+([A-Za-z_]\w*)\s*\(", self.body, re.MULTILINE):
            if m.group(1) not in _VERILOG_KEYWORDS and m.group(2) not in _VERILOG_KEYWORDS:
                return True
        return False


def _find_modules(text: str) -> List[Module]:
    modules: List[Module] = []
    for m in re.finditer(r"\bmodule\s+([A-Za-z_]\w*)", text):
        end = text.find("endmodule", m.end())
        if end == -1:
            end = len(text)
        chunk = text[m.start():end]
        semi = chunk.find(";")
        header = chunk[: semi + 1] if semi != -1 else chunk
        body = chunk[semi + 1:] if semi != -1 else ""
        modules.append(Module(m.group(1), header, body, _line_of(text, m.start())))
    return modules


def _finding(rule: str, severity: str, line: int, message: str, suggestion: str, module: str) -> Dict[str, Any]:
    return {
        "rule": rule,
        "severity": severity,
        "module": module,
        "line": line,
        "message": message,
        "suggestion": suggestion,
    }


def check_module(mod: Module) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    has_logic = bool(mod.always_blocks or mod.assign_lhs or mod.has_instances)

    if not has_logic:
        findings.append(_finding(
            "EMPTY_MODULE", SEVERITY_ERROR, mod.line,
            f"module '{mod.name}' declares ports but contains no logic "
            "(no always block, no assign, no instances)",
            "implement the module body, or remove the stub", mod.name))
        return findings

    driven: Dict[str, int] = {}
    for name, line in mod.assign_lhs:
        driven[name] = driven.get(name, 0) + 1

    for blk in mod.always_blocks:
        block_signals = set()
        for name, op in blk.assignments():
            if blk.is_sequential and op == "=":
                findings.append(_finding(
                    "BLOCKING_IN_SEQ", SEVERITY_WARNING, blk.line,
                    f"blocking assignment '{name} = ...' inside edge-triggered always "
                    f"in module '{mod.name}'",
                    "use nonblocking '<=' for sequential logic", mod.name))
            if not blk.is_sequential and op == "<=":
                findings.append(_finding(
                    "NONBLOCKING_IN_COMB", SEVERITY_WARNING, blk.line,
                    f"nonblocking assignment '{name} <= ...' inside combinational always "
                    f"in module '{mod.name}'",
                    "use blocking '=' for combinational logic", mod.name))
            block_signals.add(name)
        for name in block_signals:
            driven[name] = driven.get(name, 0) + 1

        if not blk.is_sequential:
            for cm in re.finditer(r"\bcase[xz]?\b", blk.body):
                endc = blk.body.find("endcase", cm.end())
                span = blk.body[cm.end(): endc if endc != -1 else len(blk.body)]
                if not re.search(r"\bdefault\b", span):
                    findings.append(_finding(
                        "CASE_NO_DEFAULT", SEVERITY_WARNING, blk.line,
                        f"case without default arm in combinational always in module "
                        f"'{mod.name}' (latch-inference risk)",
                        "add a default arm assigning every output of the case", mod.name))
            n_if = len(re.findall(r"\bif\b", blk.body))
            n_else = len(re.findall(r"\belse\b", blk.body))
            if n_if > n_else and blk.assignments():
                findings.append(_finding(
                    "IF_NO_ELSE", SEVERITY_WARNING, blk.line,
                    f"'if' without matching 'else' in combinational always in module "
                    f"'{mod.name}' (latch-inference risk, heuristic)",
                    "cover all paths: add an else arm or a default assignment "
                    "before the if", mod.name))
        else:
            reset_in_sens = bool(_RESET_NAME.search(blk.sensitivity))
            reset_in_body = bool(_RESET_NAME.search(blk.body))
            if not reset_in_sens and not reset_in_body:
                findings.append(_finding(
                    "NO_RESET", SEVERITY_INFO, blk.line,
                    f"edge-triggered always in module '{mod.name}' has no apparent reset",
                    "confirm registers reach a known state (reset, load, or "
                    "initial value)", mod.name))

    for name, count in sorted(driven.items()):
        if count > 1:
            findings.append(_finding(
                "MULTI_DRIVEN", SEVERITY_ERROR, mod.line,
                f"signal '{name}' in module '{mod.name}' is driven from {count} places "
                "(multiple always blocks and/or continuous assigns)",
                "drive each signal from exactly one process", mod.name))

    if not mod.has_instances:
        for out in mod.outputs:
            if out not in driven:
                findings.append(_finding(
                    "UNDRIVEN_OUTPUT", SEVERITY_ERROR, mod.line,
                    f"output '{out}' of module '{mod.name}' is never assigned",
                    "drive the output with an assign or an always block, "
                    "or remove the port", mod.name))

    return findings


def check_source(text: str, filename: str = "<input>") -> Dict[str, Any]:
    """Check Verilog source text. Returns a report dict with a verdict."""
    clean = _strip_comments(text)
    modules = _find_modules(clean)
    findings: List[Dict[str, Any]] = []
    if not modules:
        findings.append(_finding(
            "NO_MODULE", SEVERITY_ERROR, 1,
            "no Verilog module found in input", "provide a .v file containing "
            "at least one module ... endmodule", "-"))
    for mod in modules:
        findings.extend(check_module(mod))

    worst = SEVERITY_INFO
    for f in findings:
        if f["severity"] == SEVERITY_ERROR:
            worst = SEVERITY_ERROR
            break
        if f["severity"] == SEVERITY_WARNING:
            worst = SEVERITY_WARNING
    if worst == SEVERITY_ERROR:
        verdict = VERDICT_FAIL
    elif worst == SEVERITY_WARNING or any(f["severity"] == SEVERITY_INFO for f in findings):
        verdict = VERDICT_REVIEW if worst == SEVERITY_WARNING else VERDICT_PASS
    else:
        verdict = VERDICT_PASS

    return {
        "tool": "chipgate-lite",
        "schema_version": "chipgate.report.v1",
        "file": filename,
        "modules": [m.name for m in modules],
        "findings": findings,
        "counts": {
            "error": sum(1 for f in findings if f["severity"] == SEVERITY_ERROR),
            "warning": sum(1 for f in findings if f["severity"] == SEVERITY_WARNING),
            "info": sum(1 for f in findings if f["severity"] == SEVERITY_INFO),
        },
        "verdict": verdict,
        "limitations": (
            "Lint-level structural analysis of Verilog text. Not a synthesizer, "
            "simulator, equivalence checker, or timing tool; does not prove "
            "functional correctness or fabrication readiness."
        ),
    }


def check_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return check_source(fh.read(), filename=path)


def format_report(report: Dict[str, Any]) -> str:
    lines = [f"{report['file']}  (modules: {', '.join(report['modules']) or 'none'})"]
    for f in report["findings"]:
        lines.append(
            f"  line {f['line']:>4}  [{f['severity']:<7}] {f['rule']}: {f['message']}")
        lines.append(f"             sugg: {f['suggestion']}")
    c = report["counts"]
    lines.append(
        f"  -> {report['verdict']}  "
        f"({c['error']} error, {c['warning']} warning, {c['info']} info)")
    return "\n".join(lines)


def exit_code(report: Dict[str, Any]) -> int:
    if report["verdict"] == VERDICT_FAIL:
        return 1
    if report["verdict"] == VERDICT_REVIEW:
        return 2
    return 0
