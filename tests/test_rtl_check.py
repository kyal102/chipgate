"""Tests for ChipGate Lite's RTL structural checks."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chipgate.rtl_check import (  # noqa: E402
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
    check_file,
    check_source,
)

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


def rules(report):
    return {f["rule"] for f in report["findings"]}


def test_clean_counter_passes():
    report = check_file(os.path.join(EXAMPLES, "good_counter.v"))
    assert report["verdict"] == VERDICT_PASS
    assert report["findings"] == []


def test_bad_alu_fails_with_expected_rules():
    report = check_file(os.path.join(EXAMPLES, "bad_alu.v"))
    assert report["verdict"] == VERDICT_FAIL
    assert {"UNDRIVEN_OUTPUT", "CASE_NO_DEFAULT", "IF_NO_ELSE",
            "BLOCKING_IN_SEQ", "NO_RESET"} <= rules(report)


def test_empty_module_is_an_error():
    src = "module stub(input clk, input req, output reg ack); endmodule"
    report = check_source(src)
    assert report["verdict"] == VERDICT_FAIL
    assert "EMPTY_MODULE" in rules(report)


def test_no_module_is_an_error():
    report = check_source("// just a comment\n")
    assert report["verdict"] == VERDICT_FAIL
    assert "NO_MODULE" in rules(report)


def test_undriven_output_detected():
    src = """
module m(input a, output y, output z);
  assign y = a;
endmodule
"""
    report = check_source(src)
    assert "UNDRIVEN_OUTPUT" in rules(report)
    assert any(f["rule"] == "UNDRIVEN_OUTPUT" and "'z'" in f["message"]
               for f in report["findings"])


def test_multi_driven_detected():
    src = """
module m(input clk, input a, output reg y);
  always @(posedge clk) y <= a;
  assign y = ~a;
endmodule
"""
    report = check_source(src)
    assert "MULTI_DRIVEN" in rules(report)
    assert report["verdict"] == VERDICT_FAIL


def test_blocking_in_sequential_flagged():
    src = """
module m(input clk, input rst, input a, output reg y);
  always @(posedge clk) begin
    if (rst) y = 0; else y = a;
  end
endmodule
"""
    report = check_source(src)
    assert "BLOCKING_IN_SEQ" in rules(report)
    assert report["verdict"] == VERDICT_REVIEW


def test_nonblocking_in_combinational_flagged():
    src = """
module m(input a, input b, output reg y);
  always @(*) begin
    y <= a & b;
  end
endmodule
"""
    report = check_source(src)
    assert "NONBLOCKING_IN_COMB" in rules(report)


def test_case_without_default_flagged():
    src = """
module m(input [1:0] s, input a, output reg y);
  always @(*) begin
    case (s)
      2'b00: y = a;
      2'b01: y = ~a;
      2'b10: y = 1'b0;
      2'b11: y = 1'b1;
    endcase
  end
endmodule
"""
    report = check_source(src)
    assert "CASE_NO_DEFAULT" in rules(report)


def test_case_with_default_not_flagged():
    src = """
module m(input [1:0] s, input a, output reg y);
  always @(*) begin
    case (s)
      2'b00:   y = a;
      default: y = 1'b0;
    endcase
  end
endmodule
"""
    report = check_source(src)
    assert "CASE_NO_DEFAULT" not in rules(report)
    assert report["verdict"] == VERDICT_PASS


def test_full_if_else_chain_not_flagged():
    src = """
module m(input a, input b, output reg y);
  always @(*) begin
    if (a) y = 1'b1;
    else if (b) y = 1'b0;
    else y = a ^ b;
  end
endmodule
"""
    report = check_source(src)
    assert "IF_NO_ELSE" not in rules(report)


def test_no_reset_is_info_only():
    src = """
module m(input clk, input a, output reg y);
  always @(posedge clk) y <= a;
endmodule
"""
    report = check_source(src)
    assert "NO_RESET" in rules(report)
    assert report["verdict"] == VERDICT_PASS  # info does not gate


def test_comparisons_are_not_assignments():
    src = """
module m(input [3:0] a, input [3:0] b, output reg y);
  always @(*) begin
    if (a <= b) y = 1'b1;
    else y = 1'b0;
  end
endmodule
"""
    report = check_source(src)
    assert "NONBLOCKING_IN_COMB" not in rules(report)
    assert report["verdict"] == VERDICT_PASS


def test_comments_and_strings_ignored():
    src = """
// module fake(output ghost);
/* output phantom; */
module m(input a, output y);
  assign y = a;
endmodule
"""
    report = check_source(src)
    assert report["modules"] == ["m"]
    assert report["verdict"] == VERDICT_PASS


def test_instances_suppress_undriven_output_check():
    src = """
module top(input clk, input a, output y);
  leaf u0 (.clk(clk), .a(a), .y(y));
endmodule
"""
    report = check_source(src)
    assert "UNDRIVEN_OUTPUT" not in rules(report)


def test_report_is_deterministic():
    src = open(os.path.join(EXAMPLES, "bad_alu.v"), encoding="utf-8").read()
    assert check_source(src) == check_source(src)
