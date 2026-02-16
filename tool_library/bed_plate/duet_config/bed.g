M290 R0 S0                   ; Reset baby stepping
M561                         ; Disable any Mesh Bed Compensation
M557 X65:240 Y40:270 S30     ; Define mesh grid for probing (set to bed area)

G1 Z50                       ; pop bed down
G1 X195 Y40                  ; move near back leadscrew
G30 P0 X195 Y40 Z-99999      ; probe near back leadscrew
G1 Z50 ; pop bed down
G1 X240 Y270
G30 P1 X240 Y270 Z-99999     ; probe near front left leadscrew
G1 Z50
G1 X65 Y270
G30 P2 X65 Y270 Z-99999 S3   ; probe near front right leadscrew and calibrate 3 motors
G29                          ; Probe and enable Mesh Bed Compensation (creates /sys/heightmap.csv)
G1 Z100                      ; pop bed down when finished
