#!/usr/bin/env python3
"""Standardize the PCB-edge USB-A contact geometry."""

from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"

# Absolute board coordinates after J1's -90 degree footprint transform.
# The exposed tip is X=0; contacts extend toward the body in +X.
EXPECTED = {
    "1": ("USB_VBUS", (4.5, 21.5), (7.0, 1.4)),
    "2": ("USB_DM",   (4.5, 24.0), (6.0, 1.2)),
    "3": ("USB_DP",   (4.5, 26.0), (6.0, 1.2)),
    "4": ("GND",      (4.5, 28.5), (7.0, 1.4)),
}


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    j1 = board.FindFootprintByReference("J1")
    if j1 is None:
        raise RuntimeError("J1 is missing")

    pads = {pad.GetNumber(): pad for pad in j1.Pads()}
    if set(pads) != set(EXPECTED):
        raise RuntimeError(f"unexpected J1 pads: {sorted(pads)}")

    for number, (net, center, size) in EXPECTED.items():
        pad = pads[number]
        if pad.GetNetname() != net:
            raise RuntimeError(
                f"J1.{number}: net is {pad.GetNetname()}, expected {net}"
            )
        actual_center = (round(pad.GetPosition().x / 1e6, 4),
                         round(pad.GetPosition().y / 1e6, 4))
        if actual_center != center:
            raise RuntimeError(
                f"J1.{number}: center is {actual_center}, expected {center}"
            )
        # Preserve the verified center and net. Power/GND reach 0.5 mm closer
        # to the tip than D-/D+ for make-first/break-last behavior.
        pad.SetSize(pcbnew.VECTOR2I_MM(*size))
        pad.SetOrientationDegrees(0.0)

    keepout = None
    for zone in board.Zones():
        if zone.GetIsRuleArea() and zone.GetZoneName() in (
                "USB_TIP_KEEPOUT", "USB_TONGUE_POUR_KEEPOUT"):
            keepout = zone
            break
    if keepout is None:
        raise RuntimeError("USB tongue pour keepout is missing")
    keepout.SetZoneName("USB_TONGUE_POUR_KEEPOUT")
    outline = keepout.Outline()
    outline.RemoveAllContours()
    outline.NewOutline()
    for x, y in ((0.0, 19.0), (12.0, 19.0),
                 (12.0, 31.0), (0.0, 31.0)):
        outline.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print("USB-A PCB-edge contact geometry standardized")


if __name__ == "__main__":
    main()
