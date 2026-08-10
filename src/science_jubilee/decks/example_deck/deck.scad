// ═══════════════════════════════════════════════════════════════════
// Deck plate — repère Jubilee (X vertical, Y horizontal)
// ═══════════════════════════════════════════════════════════════════
$fn = 64;

difference() {
    cube([305, 305, 3.0]);
    translate([5.000, 5.000, -0.5])
        cylinder(r=1.5, h=4.0, $fn=64);
    translate([5.000, 300.000, -0.5])
        cylinder(r=1.5, h=4.0, $fn=64);
    translate([300.000, 5.000, -0.5])
        cylinder(r=1.5, h=4.0, $fn=64);
    translate([300.000, 300.000, -0.5])
        cylinder(r=1.5, h=4.0, $fn=64);
}
