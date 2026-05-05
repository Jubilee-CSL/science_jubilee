; visualization seed added by RecordingTransport
G90
M82
G92 X0 Y0 Z0 E0
G1 X0.10 Y0.00 E0.10 F600
; === tool change: T2 ===
; tpre2.g
G90                         ; Ensure the machine is in absolute mode before issuing movements.
G0 X105 Y280.0 Z50.0 F20000 ; Rapid to the approach position without any current tool.
G60 S0                      ; Save this position as the reference point from which to later apply new tool offsets.
; (macro not found: tpost2.g)
; T2
G10 P2 X1.2500 Y-2.5000 Z12.3400
