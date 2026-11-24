# VaultKey USB Rev E engineering review

Review date: 2026-11-24
Physical prototype tested: **No**
Fabrication status: **PCB DRC clean; manufacturing outputs regenerated**

## Changes reviewed

- Added TP1 two-pad recovery access: TP1.1 is BOOT/GPIO0 and TP1.2 is GND.
  Bridge the pads while pulsing SW5/EN, then remove the bridge after ROM USB
  enumeration.
- Routed GPIO1 (U1.39) through R5 (1 kΩ) to the existing green LED D1. The LED
  is active high. Firmware source now drives status patterns without blocking
  the main loop.
- Existing component placements and the 112.5 × 50 mm board outline remain
  unchanged. Only the new recovery pads and copper/net changes were added.
- No hard-gold edge plating is specified. The notes call for standard ENIG for
  this low-cycle prototype and ask the fabricator to confirm insertion life.

## Verification results

| Check | Result |
|---|---|
| USB-A contact pad geometry and order | PASS: GND, D+, D−, VBUS top to bottom; all pads inside the tongue |
| USB silkscreen and copper pour keepout | PASS |
| Schematic/PCB connected-pin comparison | PASS: 105 pins, 0 mismatches |
| Schematic ERC | PASS: 0 violations |
| Recovery BOOT and EN pad-net checks | PASS |
| LED_GPIO route and minimum width | PASS |
| PCB DRC after zone refill | 0 violations, 0 unconnected pads |
| Firmware source build | PASS: 8 MB and 4 MB Rev-E variants |
| Rev-E firmware/factory images | Built and checksummed in `VaultKey_Firmware/firmware/` |

The independent USB contact checker confirms the four physical pad assignments
and geometry. A GND stitching via reconnects the isolated F.Cu copper island,
and KiCad now reports zero unconnected pads. The USB VBUS fanout passes DRC
after refilling the copper zones. The Gerber, drill, and manufacturing
archives have been regenerated from the current board.

## Release decision

The PCB source passes DRC and both Rev-E firmware flash variants build. Validate
recovery, USB enumeration, LED behavior, and mechanical fit on the assembled
board before production use.
