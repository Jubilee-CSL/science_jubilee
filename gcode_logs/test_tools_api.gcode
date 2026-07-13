; visualization seed added by RecordingTransport
G90
M82
G92 X0 Y0 Z0 E0
G1 X0.10 Y0.00 E0.10 F600
; === park tool: T-1 ===
; tfree1.g
G91                          ; Relative Mode.
G1 Z2                        ; Pop Z up slightly so we don't crash while traveling over the usable bed region.
G90                          ; Absolute Mode.
G53 G0 X210 Y270 F12000    ; Rapid to the back of the post. Stay away from the tool rack so we don't collide with tools.
G53 G1 Y338 F6000            ; Controlled move to the park position with tool-1. (park_x, park_y)
; M98 P"/macros/tool_unlock.g" ; Unlock the tool
G91                 ; Set relative movements
G1 U-4 F9000 H2     ; Back off the limit switch with a small move
G1 U-360 F9000 H1   ; Perform up to one rotation looking for the home limit switch
G90                 ; Restore absolute movements
G53 G1 Y305 F6000            ; Retract the pin.
; T-1
; === tool change: T2 ===
; tpre2.g
G90                         ; Ensure the machine is in absolute mode before issuing movements.
G0 X105 Y280.0 Z50.0 F20000 ; Rapid to the approach position without any current tool.
G60 S0                      ; Save this position as the reference point from which to later apply new tool offsets.
; (macro not found: tpost2.g)
; T2
