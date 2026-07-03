module safe_dtl_gate (
    input wire clk,
    input wire rst_n,
    input wire verifier_ok,
    input wire policy_ok,
    input wire evidence_ok,
    input wire timeout_ok,
    input wire kill_switch,
    output reg approved
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || kill_switch) begin
            approved <= 1'b0;
        end else if (verifier_ok && policy_ok && evidence_ok && timeout_ok) begin
            approved <= 1'b1;
        end else begin
            approved <= 1'b0;
        end
    end
endmodule
