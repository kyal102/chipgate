module unsafe_direct_005 (
    input  clk,
    input  ai_cmd,
    input  nn_output,
    input  ai_signal,
    input  ai_decision,
    input  ai_proposal,
    output reg laser_fire
);
    always @(posedge clk) begin
        laser_fire <= ai_proposal;
    end
endmodule