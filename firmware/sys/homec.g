; Home W Axis

G91                     ; Set relative mode
G1 C360 F9000 H1       ; Big negative move to search for home endstop
G1 C-6 F600              ; Back off the endstop
G1 C15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
