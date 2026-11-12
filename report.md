# VaultKey USB circuit report

Release state: 2026-11-12  
Project: `/home/rootx/Projects/VaultKey_USB`  
Toolchain: KiCad 10.0.8  
Physical prototype tested: **NO**

## Repository scope

This repository contains the electrical design, routed PCB, deterministic
generator sources, circuit-specific 3D envelopes, documentation plots, and
fabrication/assembly outputs.

The separate `enclosure/` directory and all FreeCAD enclosure models are
excluded from Git. The board STEP under `fabrication/3d/` and component STEP
envelopes under `lib/VaultKey.3dshapes/` remain included because they belong to
PCB assembly and fabrication, not the plastic enclosure.

## Circuit summary

```text
MCU:              ESP32-S3-WROOM-1U
USB:              PCB-edge USB-A device plug
Display:          Adafruit SSD1306 128x64 I2C module footprint
RTC:              DS1307+ with 32.768 kHz crystal and CR2032 backup
I2C translation:  PCA9306, 3.3 V OLED/MCU side to 5 V RTC side
Controls:         UP, DOWN, SELECT, BACK, recessed EN reset
PCB:              2 layers, 1.6 mm FR4, 112.500 x 50.000 mm
```

## Verified signal mapping

| Function | ESP32-S3 signal | U1 pad |
|---|---:|---:|
| SELECT | GPIO4 | 4 |
| DOWN | GPIO5 | 5 |
| BACK | GPIO6 | 6 |
| UP | GPIO7 | 7 |
| OLED SDA / low-side I2C SDA | GPIO8 | 12 |
| OLED SCL / low-side I2C SCL | GPIO9 | 17 |
| OLED reset | GPIO13 | 21 |
| USB D− | GPIO19 | 13 |
| USB D+ | GPIO20 | 14 |
| BOOT strap | GPIO0 | 27 |
| EN/reset | EN | 3 |

USB connectivity from the exported netlist:

```text
J1.2 D− -> USB_DM -> U5.3/U5.4 -> U1.13 -> GPIO19
J1.3 D+ -> USB_DP -> U5.1/U5.6 -> U1.14 -> GPIO20
```

## Validation report

```text
ARCHIVED RELEASE OUTPUTS
  Fabrication SHA-256 manifest: PASS (34/34 files)
  Archived PCB DRC: 0 violations, 0 unconnected pads
  Archived schematic ERC: 0 errors, 0 warnings
  Archived netlist comparison: 102 PCB pads, 102 schematic pins, 0 mismatches
  USB edge-contact verification: PASS
  BOOT/reset revision verification: PASS

CURRENT SOURCE, READ-ONLY CHECKS
  PCB DRC after in-memory zone refill: 0 violations, 0 unconnected items
  PCB source modified by check: NO
  Schematic ERC errors: 0
  Schematic ERC warnings: 37
  Current PCB trace count: 275
  Current PCB via count: 37
  USB D+ routed length: 69.713 mm
  USB D− routed length: 76.338 mm
  USB pair-length difference: 6.625 mm
```

The fresh ERC warnings are primarily footprint-link warnings in the generated
schematic. It also reports one USB ground-net warning and one
`OLED_SCL`/`OLED_SDA` multiple-net-name warning. These must be reviewed in
KiCad before fabrication. The archived 0/0 ERC report and current source do not
currently produce identical direct-CLI results.

The README previously stated a 0.057 mm USB pair mismatch and 104 connected
pins. Direct measurement of the current PCB and the archived equivalence report
show 6.625 mm and 102 respectively; the README has been corrected.

## Mechanical and manufacturing status

- Board outline: 112.500 × 50.000 mm.
- Main body: 100.500 × 50.000 mm after the 12 mm USB tongue.
- Four 2.7 mm NPTH mounting holes are at the documented locked coordinates.
- OLED corner drills are intentionally absent.
- Keystone 1058/1058TR CR2032 holder is on the bottom side.
- All 37 vias are specified as tented on both sides.
- Minimum routed width/clearance reported: 0.2000/0.2017 mm.
- Hard gold is preferred for the exposed USB fingers; ENIG is acceptable only
  for low-cycle prototypes.
- Gerber/drill and full manufacturing ZIP archives are present and match the
  recorded SHA-256 manifest.

## Reset and recovery

- R6 and C7 provide automatic EN release on USB power-up.
- SW5 is the recessed EN-to-GND reset switch at `(104.0, 13.5)`.
- R7 pulls GPIO0 high and SW6/BOOT is absent.
- A normal reset does not erase flash or RTC backup state.
- The native USB Serial/JTAG controller supports normal automatic download.
- GPIO0 is not externally accessible, so ROM recovery is not guaranteed if
  application firmware disables or takes ownership of the shared USB PHY.
  Hidden GPIO0, EN, and GND programming pads are recommended for the next PCB
  revision.

## Unresolved issues

1. No assembled board has been tested electrically or mechanically.
2. Reconcile the 37 fresh ERC warnings with the archived 0-warning report,
   especially the OLED SDA/SCL multiple-net-name warning.
3. Re-export fabrication artifacts after resolving source/report differences,
   then regenerate and verify the checksum manifest.
4. Validate USB signal integrity and connector retention in the intended host
   receptacles. The 6.625 mm full-speed pair difference must be reviewed rather
   than represented as 0.057 mm.
5. Add an accessible GPIO0 recovery method before production.
6. Confirm the fitted ESP32-S3-WROOM-1U flash-size variant.
7. Confirm OLED controller/address on the procured module.
8. Validate AMS1117 temperature, 0.5 A polyfuse margin, peak radio current,
   CR2032 polarity/retention, DS1307 drift, and enclosure temperature.

## Release conclusion

The project is a complete routed circuit package with internally checksummed
fabrication outputs and a clean refilled-zone PCB DRC. It is **not yet approved
for production fabrication** because the current schematic ERC warnings,
source/report discrepancies, physical USB recovery limitation, and lack of
prototype testing remain open.
