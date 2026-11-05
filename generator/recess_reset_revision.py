#!/usr/bin/env python3
"""Replace the finger-operated RESET/BOOT buttons with a recessed EN switch.

Revision D removes the two 6 x 6 mm user-accessible controls (SW5 RESET and
SW6 BOOT).  GPIO0 stays pulled high by the existing R7, so the ESP32-S3 boots
from flash on every USB power-up.  SW5 becomes a 4.5 x 4.5 mm SMD tactile
switch connected only between EN and GND, intended to be pressed through a
pinhole in the enclosure with a needle or SIM-ejector tool.

The distro pcbnew SWIG bindings can crash after a footprint removal, so the
revision is split into isolated processes:

    python3 generator/recess_reset_revision.py remove
    python3 generator/recess_reset_revision.py add
"""

from __future__ import annotations

from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"

SWITCH_LIB = "/usr/share/kicad/footprints/Button_Switch_SMD.pretty"
SWITCH_FP = "SW_Push_1P1T_NO_Vertical_Wuerth_434133025816"
SWITCH_REF = "SW5"
SWITCH_AT = (104.0, 13.5)
SWITCH_ROT = 0.0

# Absolute pad centres for the Wuerth 434133025816 at (104.0, 13.5), 0 deg.
# Pad 1 is duplicated on the top row; pad 2 is duplicated on the bottom row.
EN_PADS = ((101.925, 12.425), (106.075, 12.425))
GND_PADS = ((101.925, 14.575), (106.075, 14.575))

# (net, layer, start, end, width)
TRACKS = (
    # Existing EN trunk ends at (101.0, 13.5); join it to the left pad 1.
    ("EN", pcbnew.F_Cu, (101.0, 13.5), (101.925, 12.425), 0.25),
    # Link both pad 1 terminals together.
    ("EN", pcbnew.F_Cu, (101.925, 12.425), (106.075, 12.425), 0.25),
    # Link both pad 2 terminals; the GND pours finish the connection.
    ("GND", pcbnew.F_Cu, (101.925, 14.575), (106.075, 14.575), 0.25),
)


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x, y)


def remove_legacy_buttons() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    removed = []
    for ref in ("SW5", "SW6"):
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            continue
        removed.append(ref)
        board.Remove(fp)
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"removed footprints: {', '.join(removed) or '(none present)'}")


def add_recessed_switch() -> None:
    board = pcbnew.LoadBoard(str(BOARD))

    if board.FindFootprintByReference(SWITCH_REF) is not None:
        raise RuntimeError(f"{SWITCH_REF} already exists; run the remove phase first")

    fp = pcbnew.FootprintLoad(SWITCH_LIB, SWITCH_FP)
    if fp is None:
        raise RuntimeError(f"could not load {SWITCH_FP}")

    fp.SetReference(SWITCH_REF)
    fp.SetValue("RESET")
    fp.SetPosition(pt(*SWITCH_AT))
    fp.SetOrientationDegrees(SWITCH_ROT)
    fp.SetLibDescription("Recessed EN/reset switch, needle access only")

    nets = board.GetNetsByName()
    for pad in fp.Pads():
        number = pad.GetNumber()
        name = "EN" if number == "1" else "GND"
        pad.SetNet(nets[name])
        if name == "GND":
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    board.Add(fp)

    existing = list(board.GetTracks())

    def present(net, layer, a, b):
        for t in existing:
            if t.Type() == pcbnew.PCB_VIA_T:
                continue
            if t.GetNetname() != net or t.GetLayer() != layer:
                continue
            s, e = t.GetStart(), t.GetEnd()
            pts = {(round(s.x / 1e6, 3), round(s.y / 1e6, 3)),
                   (round(e.x / 1e6, 3), round(e.y / 1e6, 3))}
            if pts == {a, b}:
                return True
        return False

    for net, layer, a, b, width in TRACKS:
        if present(net, layer, a, b):
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pt(*a))
        track.SetEnd(pt(*b))
        track.SetWidth(pcbnew.FromMM(width))
        track.SetLayer(layer)
        track.SetNet(nets[net])
        board.Add(track)
        existing.append(track)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print("added recessed EN switch, routed EN/GND, refilled zones")


def main() -> None:
    import sys

    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase == "remove":
        remove_legacy_buttons()
    elif phase == "add":
        add_recessed_switch()
    else:
        raise SystemExit("usage: recess_reset_revision.py remove|add")


if __name__ == "__main__":
    main()
