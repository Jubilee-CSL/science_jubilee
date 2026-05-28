; visualization seed added by RecordingTransport
G90
M82
G92 X0 Y0 Z0 E0
G1 X0.10 Y0.00 E0.10 F600
; M98 P"homeall.g"
; M98 P"homeu.g" ; X and Z require U to be homed first in case a tool is currently active
G90                     ; Set absolute mode
G92 U0                  ; Define current position as 0 to enable move without homing
G1 U2 H2 F5000          ; Move the axis 2deg to back it off of the unlocked switch
G1 U120 H1 F5000        ; Move the axis to 120deg, or until it hits an endstop
M400                    ; Wait for the command buffer to drain before checking model
if {abs((move.axes[3].userPosition - 120))} > 1
M84 U
M291 R"Intervention Required" P"Please remove the tool, return it to its post, and restore the twist lock to its unlocked (horizontal) position. Press OK to continue..." S3
T-1 P0                  ; Set current tool to none
G91                     ; Set relative mode
G1 U-360 F9000 H1       ; Big negative move to search for home endstop
G1 U6 F600              ; Back off the endstop
G1 U-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
; M98 P"homey.g"
G91                     ; Set relative mode
G1 H2 Z5 F5000          ; Lower the bed
G1 Y-400 F6000 H1       ; Big negative move to search for endstop
G1 Y4 F600              ; Back off the endstop
G1 Y-10 F600 H1         ; Find endstop again slowly
G1 H2 Z-5 F5000         ; Raise the bed
G90                     ; Set absolute mode
; M98 P"homex.g"
G90                     ; Set absolute mode
if !move.axes[3].homed
M291 R"Cannot Home X" P"U axis must be homed before X to prevent damage to tool. Press OK to home U or Cancel to abort" S3
; M98 P"homeu.g"
G90                     ; Set absolute mode
G92 U0                  ; Define current position as 0 to enable move without homing
G1 U2 H2 F5000          ; Move the axis 2deg to back it off of the unlocked switch
G1 U120 H1 F5000        ; Move the axis to 120deg, or until it hits an endstop
M400                    ; Wait for the command buffer to drain before checking model
if {abs((move.axes[3].userPosition - 120))} > 1
M84 U
M291 R"Intervention Required" P"Please remove the tool, return it to its post, and restore the twist lock to its unlocked (horizontal) position. Press OK to continue..." S3
T-1 P0                  ; Set current tool to none
G91                     ; Set relative mode
G1 U-360 F9000 H1       ; Big negative move to search for home endstop
G1 U6 F600              ; Back off the endstop
G1 U-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
if !move.axes[1].homed
M291 R"Cannot Home X" P"Y axis must be homed before x to prevent damage to tool. Press OK to home Y or Cancel to abort" S3
; M98 P"homey.g"
G91                     ; Set relative mode
G1 H2 Z5 F5000          ; Lower the bed
G1 Y-400 F6000 H1       ; Big negative move to search for endstop
G1 Y4 F600              ; Back off the endstop
G1 Y-10 F600 H1         ; Find endstop again slowly
G1 H2 Z-5 F5000         ; Raise the bed
G90                     ; Set absolute mode
if move.axes[1].userPosition >= 305
G0 Y305 F20000       ; Rapid to safe y position
if state.currentTool != -1
M84 U
M291 R"Cannot Home X" P"Tool must be deselected before homing. U has been unlocked, please manually dock tool and press OK to continue or Cancel to abort" S3
; M98 P"homeu.g"
G90                     ; Set absolute mode
G92 U0                  ; Define current position as 0 to enable move without homing
G1 U2 H2 F5000          ; Move the axis 2deg to back it off of the unlocked switch
G1 U120 H1 F5000        ; Move the axis to 120deg, or until it hits an endstop
M400                    ; Wait for the command buffer to drain before checking model
if {abs((move.axes[3].userPosition - 120))} > 1
M84 U
M291 R"Intervention Required" P"Please remove the tool, return it to its post, and restore the twist lock to its unlocked (horizontal) position. Press OK to continue..." S3
T-1 P0                  ; Set current tool to none
G91                     ; Set relative mode
G1 U-360 F9000 H1       ; Big negative move to search for home endstop
G1 U6 F600              ; Back off the endstop
G1 U-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
G91                     ; Relative mode
G1 H2 Z5 F5000          ; Lower the bed
G1 X-330 6000 H1        ; Big negative move to search for endstop
G1 X4 F600              ; Back off the endstop
G1 X-10 F600 H1         ; Find endstop again slowly
G1 H2 Z-5 F5000         ; Raise the bed
G90                     ; Set absolute mode
; M98 P"homez.g"
if !move.axes[3].homed
M291 R"Cannot Home Z" P"U axis must be homed before Z to prevent damage to tool. Press OK to home U or Cancel to abort" S3
; M98 P"homeu.g"
G90                     ; Set absolute mode
G92 U0                  ; Define current position as 0 to enable move without homing
G1 U2 H2 F5000          ; Move the axis 2deg to back it off of the unlocked switch
G1 U120 H1 F5000        ; Move the axis to 120deg, or until it hits an endstop
M400                    ; Wait for the command buffer to drain before checking model
if {abs((move.axes[3].userPosition - 120))} > 1
M84 U
M291 R"Intervention Required" P"Please remove the tool, return it to its post, and restore the twist lock to its unlocked (horizontal) position. Press OK to continue..." S3
T-1 P0                  ; Set current tool to none
G91                     ; Set relative mode
G1 U-360 F9000 H1       ; Big negative move to search for home endstop
G1 U6 F600              ; Back off the endstop
G1 U-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
if !move.axes[0].homed || !move.axes[1].homed
M291 R"Cannot Home Z" P"X&Y Axes must be homed before Z for probing. Press OK to home X&Y or Cancel to abort" S3
; M98 P"homey.g"
G91                     ; Set relative mode
G1 H2 Z5 F5000          ; Lower the bed
G1 Y-400 F6000 H1       ; Big negative move to search for endstop
G1 Y4 F600              ; Back off the endstop
G1 Y-10 F600 H1         ; Find endstop again slowly
G1 H2 Z-5 F5000         ; Raise the bed
G90                     ; Set absolute mode
; M98 P"homex.g"
G90                     ; Set absolute mode
if !move.axes[3].homed
M291 R"Cannot Home X" P"U axis must be homed before X to prevent damage to tool. Press OK to home U or Cancel to abort" S3
; M98 P"homeu.g"
G90                     ; Set absolute mode
G92 U0                  ; Define current position as 0 to enable move without homing
G1 U2 H2 F5000          ; Move the axis 2deg to back it off of the unlocked switch
G1 U120 H1 F5000        ; Move the axis to 120deg, or until it hits an endstop
M400                    ; Wait for the command buffer to drain before checking model
if {abs((move.axes[3].userPosition - 120))} > 1
M84 U
M291 R"Intervention Required" P"Please remove the tool, return it to its post, and restore the twist lock to its unlocked (horizontal) position. Press OK to continue..." S3
T-1 P0                  ; Set current tool to none
G91                     ; Set relative mode
G1 U-360 F9000 H1       ; Big negative move to search for home endstop
G1 U6 F600              ; Back off the endstop
G1 U-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
if !move.axes[1].homed
M291 R"Cannot Home X" P"Y axis must be homed before x to prevent damage to tool. Press OK to home Y or Cancel to abort" S3
; M98 P"homey.g"
G91                     ; Set relative mode
G1 H2 Z5 F5000          ; Lower the bed
G1 Y-400 F6000 H1       ; Big negative move to search for endstop
G1 Y4 F600              ; Back off the endstop
G1 Y-10 F600 H1         ; Find endstop again slowly
G1 H2 Z-5 F5000         ; Raise the bed
G90                     ; Set absolute mode
if move.axes[1].userPosition >= 305
G0 Y305 F20000       ; Rapid to safe y position
if state.currentTool != -1
M84 U
M291 R"Cannot Home X" P"Tool must be deselected before homing. U has been unlocked, please manually dock tool and press OK to continue or Cancel to abort" S3
; M98 P"homeu.g"
G90                     ; Set absolute mode
G92 U0                  ; Define current position as 0 to enable move without homing
G1 U2 H2 F5000          ; Move the axis 2deg to back it off of the unlocked switch
G1 U120 H1 F5000        ; Move the axis to 120deg, or until it hits an endstop
M400                    ; Wait for the command buffer to drain before checking model
if {abs((move.axes[3].userPosition - 120))} > 1
M84 U
M291 R"Intervention Required" P"Please remove the tool, return it to its post, and restore the twist lock to its unlocked (horizontal) position. Press OK to continue..." S3
T-1 P0                  ; Set current tool to none
G91                     ; Set relative mode
G1 U-360 F9000 H1       ; Big negative move to search for home endstop
G1 U6 F600              ; Back off the endstop
G1 U-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
G91                     ; Relative mode
G1 H2 Z5 F5000          ; Lower the bed
G1 X-330 6000 H1        ; Big negative move to search for endstop
G1 X4 F600              ; Back off the endstop
G1 X-10 F600 H1         ; Find endstop again slowly
G1 H2 Z-5 F5000         ; Raise the bed
G90                     ; Set absolute mode
if state.currentTool != -1
M84 U
M291 R"Cannot Home Z" P"Tool must be deselected before homing. U has been unlocked, please manually dock tool and press OK to continue or Cancel to abort" S3
; M98 P"homeu.g"
G90                     ; Set absolute mode
G92 U0                  ; Define current position as 0 to enable move without homing
G1 U2 H2 F5000          ; Move the axis 2deg to back it off of the unlocked switch
G1 U120 H1 F5000        ; Move the axis to 120deg, or until it hits an endstop
M400                    ; Wait for the command buffer to drain before checking model
if {abs((move.axes[3].userPosition - 120))} > 1
M84 U
M291 R"Intervention Required" P"Please remove the tool, return it to its post, and restore the twist lock to its unlocked (horizontal) position. Press OK to continue..." S3
T-1 P0                  ; Set current tool to none
G91                     ; Set relative mode
G1 U-360 F9000 H1       ; Big negative move to search for home endstop
G1 U6 F600              ; Back off the endstop
G1 U-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
M290 R0 S0              ; Reset baby stepping
M561                    ; Disable any Mesh Bed Compensation
G91                     ; Relative mode
G1 H2 Z5 F5000          ; Lower the bed
G90                     ; back to absolute positioning
G90 G1 X150 Y130 F10000 ; Move to the center of the bed -20mm to not probe on
M558 F500               ; Set the probing speed
G30                     ; Probe
M558 F50                ; Set a slower probing speed
G30                     ; Prob
G32                     ; Run 3-point bed calibration defined in bed.g
G29                  ; Enable Mesh Bed Compensation
; M98 P"homeb.g"
G91                     ; Set relative mode
G1 B-360 F9000 H1       ; Big negative move to search for home endstop
G1 B6 F600              ; Back off the endstop
G1 B-15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
; M98 P"homec.g"
G91                     ; Set relative mode
G1 C360 F9000 H1       ; Big negative move to search for home endstop
G1 C-6 F600              ; Back off the endstop
G1 C15 F600 H1         ; Find endstop again slowly
G90                     ; Set absolute mode
M409 K"move.axes[].homed"
