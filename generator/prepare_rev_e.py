#!/usr/bin/env python3
"""Apply the Rev-E electrical changes to the routed Rev-D PCB in place.

Existing footprint coordinates and the board outline are asserted and kept.
USB edge contact nets are corrected to match the specified insertion order;
the short contact fanout is rebuilt separately by mirror_usb_contacts.py.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "generator"))
import design  # noqa: E402

BOARD_PATH = ROOT / "VaultKey_USB.kicad_pcb"
TP_LIB = "/usr/share/kicad/footprints/TestPoint.pretty"
TP_NAME = "TestPoint_2Pads_Pitch2.54mm_Drill0.8mm"


def mm(value: int) -> float:
    return value / 1_000_000


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD_PATH))

    # Freeze all existing footprint placements as a guard against accidental
    # movement while adding the recovery pads.
    for part in design.PARTS:
        if part.ref == "TP1" or part.ref.startswith("H"):
            continue
        fp = board.FindFootprintByReference(part.ref)
        if fp is None:
            raise RuntimeError(f"missing existing footprint {part.ref}")
        position = fp.GetPosition()
        actual = (mm(position.x), mm(position.y), fp.GetOrientationDegrees())
        expected_rot = part.rot + (180 if part.side == "B" else 0)
        rotation_delta = (actual[2] - expected_rot + 180) % 360 - 180
        expected = (part.x, part.y, expected_rot)
        if (abs(actual[0] - expected[0]) > 0.001 or
                abs(actual[1] - expected[1]) > 0.001 or
                abs(rotation_delta) > 0.001):
            raise RuntimeError(f"existing placement changed: {part.ref}: {actual} != {expected}")

    if board.FindFootprintByReference("TP1") is not None:
        raise RuntimeError("TP1 already exists; refusing to add it twice")

    led_gpio = board.FindNet("LED_GPIO")
    if led_gpio is None:
        led_gpio = pcbnew.NETINFO_ITEM(board, "LED_GPIO")
        board.Add(led_gpio)

    def assign(ref: str, number: str, net: str) -> None:
        fp = board.FindFootprintByReference(ref)
        pad = fp.FindPadByNumber(number) if fp else None
        net_info = board.FindNet(net)
        if pad is None or net_info is None:
            raise RuntimeError(f"cannot assign {ref}.{number} to {net}")
        pad.SetNet(net_info)

    # USB-A contact row, from the lower tongue edge upward: VBUS, D-, D+, GND.
    assign("J1", "1", "USB_VBUS")
    assign("J1", "4", "GND")
    # Active-high LED path: GPIO1 -> R5 (1 kOhm) -> D1 -> GND.
    assign("R5", "1", "LED_GPIO")
    assign("U1", "39", "LED_GPIO")

    # The Rev-D LED feed was routed directly from +3V3 to R5 pad 1. Remove
    # only that feed segment; the adjacent +3V3 rail and all other routing stay.
    stale_led_feed = []
    for track in list(board.GetTracks()):
        if (track.Type() != pcbnew.PCB_VIA_T and
                track.GetNetname() == "+3V3" and
                track.GetLayer() == pcbnew.F_Cu):
            start, end = track.GetStart(), track.GetEnd()
            points = ((start.x / 1e6, start.y / 1e6),
                      (end.x / 1e6, end.y / 1e6))
            if any(abs(x - 46.5875) < 0.01 and abs(y - 3.5) < 0.01
                   for x, y in points):
                stale_led_feed.append(track)
    if len(stale_led_feed) != 1:
        raise RuntimeError(f"expected one old LED supply track, found {len(stale_led_feed)}")
    board.Remove(stale_led_feed[0])

    fp = pcbnew.FootprintLoad(TP_LIB, TP_NAME)
    if fp is None:
        raise RuntimeError(f"could not load TestPoint:{TP_NAME}")
    fp.SetPosition(pcbnew.VECTOR2I_MM(design.part_by_ref("TP1").x,
                                      design.part_by_ref("TP1").y))
    fp.SetOrientationDegrees(0)
    fp.SetReference("TP1")
    fp.SetValue("BOOT_RECOVERY")
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)
    for number, net in (("1", "BOOT"), ("2", "GND")):
        pad = fp.FindPadByNumber(number)
        if pad is None:
            raise RuntimeError(f"recovery footprint is missing pad {number}")
        pad.SetNet(board.FindNet(net))

    board.GetTitleBlock().SetRevision("E")
    board.BuildListOfNets()
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print("Rev-E nets and TP1 added; existing footprint placements preserved")


if __name__ == "__main__":
    main()
