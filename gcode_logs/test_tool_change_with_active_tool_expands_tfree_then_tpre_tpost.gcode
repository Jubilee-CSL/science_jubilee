; visualization seed added by RecordingTransport
G90
M82
G92 X0 Y0 Z0 E0
G1 X0.10 Y0.00 E0.10 F600
; === tool change: T1 ===
; tfree0.g
G91                          ; Relative Mode.
G1 Z2                        ; Pop Z up slightly so we don't crash while traveling over the usable bed region.
G90                          ; Absolute Mode.
G53 G0 X290.5 Y270 F12000    ; Rapid to the back of the post. Stay away from the tool rack so we don't collide with tools.
G53 G1 Y338.5 F6000            ; Controlled move to the park position with tool-1. (park_x, park_y)
; M98 P"/macros/tool_unlock.g" ; Unlock the tool
G91                 ; Set relative movements
G1 U-4 F9000 H2     ; Back off the limit switch with a small move
G1 U-360 F9000 H1   ; Perform up to one rotation looking for the home limit switch
G90                 ; Restore absolute movements
G53 G1 Y305 F6000            ; Retract the pin.
; tpre1.g
G90                   ; Ensure the machine is in absolute mode before issuing movements.
G0 X270 Y270 F20000 ; Rapid to the approach position without any current tool.
G60 S0                ; Save this position as the reference point from which to later apply new tool offsets.
; tpost1.g
G90                        ; Ensure the machine is in absolute mode before issuing movements.
G53 G1 X210 F6000           ; Move to the pickup position with tool-1.
G53 G1 Y338 F6000
; M98 P"/macros/tool_lock.g" ; Lock the tool
G91                   ; relative mode
G1 U10 F5000 H0        ; back off slightly
M569 P1.2 S0 D0        ; ensure SpreadCycle for max torque
M201 U100              ; slow acceleration
G1 U80 F1500 H1      ; torque-limit move
M201 U250              ; restore normal acceleration
G90                   ; back to absolute mode
G1 R2 Z0                   ; Restore prior Z position before tool change was initiated.
G1 R0 Y0                   ; Retract tool by restoring Y position next now accounting for new tool offset.
G1 R0 X0                   ; Restore X position now accounting for new tool offset.
M106 R2                    ; restore print cooling fan speed
; T1
