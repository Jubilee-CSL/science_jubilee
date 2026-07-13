; Engage tool lock with maximum torque
G91                   ; relative mode
G1 U10 F5000 H0        ; back off slightly
M569 P1.2 S0 D0        ; ensure SpreadCycle for max torque
;M906 U1000 I100         ; temporarily high current
M201 U100              ; slow acceleration
G1 U80 F1500 H1      ; torque-limit move
;M906 U1000          ; revert current
M201 U250              ; restore normal acceleration
G90                   ; back to absolute mode
