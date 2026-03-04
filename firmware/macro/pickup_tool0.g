; pickup_tool0.g
; Picks up Tool 0 from its parking post.
;
; RepRapFirmware handles the full sequence automatically on T0:
;   1. tfree{n}.g  — parks the currently active tool (if any)
;   2. tpre0.g     — approaches the Tool 0 parking post
;   3. tpost0.g    — locks Tool 0 onto the carriage and restores position
;
; Run this macro from DWC or via: M98 P"/macros/pickup_tool0.g"

T0
