module obfuscated_unsafe_004 (
    input  clk,
    input  rst_n,
    input  ai_proposed_action,
    input  kill_sw,
    output reg motor_drv
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) motor_drv <= 0;
        else motor_drv <= ai_proposed_action;
    end
endmodule