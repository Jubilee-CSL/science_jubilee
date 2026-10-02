; tpre3.g
; Runs after the previous tool is freed and before Tool 3 is picked up.
; Tool offsets are NOT yet applied at this stage.

G90                         ; Ensure absolute positioning mode is active
G53 G0 X19.00 Y280.00 Z100.00 F20000 ; Move to a safe approach position using machine coordinates (no tool mounted)
