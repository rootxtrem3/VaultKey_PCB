#!/usr/bin/env python3
"""Apply the PCA9306 reference-bias circuit to the routed PCB.

TI's recommended translation-mode connection joins VREF2 and EN, pulls that
node to the high-side supply through 200 kOhm, and filters it with 100 pF.
This script is intentionally idempotent so it can be run after importing the
FreeRouting session without duplicating R8 or its local traces.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_pcb  # noqa: E402
import design  # noqa: E402

BOARD = ROOT / "VaultKey_USB.kicad_pcb"


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x, y)


def coord(item):
    a, b = item.GetStart(), item.GetEnd()
    p = (round(a.x / 1e6, 3), round(a.y / 1e6, 3))
    q = (round(b.x / 1e6, 3), round(b.y / 1e6, 3))
    return p, q


def same_segment(item, a, b) -> bool:
    p, q = coord(item)
    a = tuple(round(v, 3) for v in a)
    b = tuple(round(v, 3) for v in b)
    return (p, q) in ((a, b), (b, a))


def add_track(board, net, width, a, b, known):
    k = (tuple(round(v, 4) for v in a), tuple(round(v, 4) for v in b))
    if k in known or (k[1], k[0]) in known:
        return
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*a))
    track.SetEnd(point(*b))
    track.SetWidth(pcbnew.FromMM(width))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    board.Add(track)
    known.add(k)


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD))

    bias = board.FindNet("I2C_BIAS")
    if bias is None:
        bias = pcbnew.NETINFO_ITEM(board, "I2C_BIAS")
        board.Add(bias)

    nets = {name: board.FindNet(name) for name in design.NETS}
    nets["I2C_BIAS"] = bias

    # Correct U4 and reuse C5 as the datasheet-recommended 100 pF filter.
    u4 = board.FindFootprintByReference("U4")
    c5 = board.FindFootprintByReference("C5")
    if u4 is None or c5 is None:
        raise RuntimeError("U4 or C5 is missing")
    for pad in u4.Pads():
        target = design.part_by_ref("U4").pads.get(pad.GetNumber())
        if target:
            pad.SetNet(nets[target])
    c5.SetValue("100pF")
    for pad in c5.Pads():
        target = design.part_by_ref("C5").pads.get(pad.GetNumber())
        if target:
            pad.SetNet(nets[target])

    # Add the 200 kOhm bias resistor at its canonical placement.
    r8 = board.FindFootprintByReference("R8")
    created_r8 = r8 is None
    if r8 is None:
        r8 = build_pcb.place_part(board, design.part_by_ref("R8"), nets)
    else:
        r8.SetValue("200k")
        for pad in r8.Pads():
            target = design.part_by_ref("R8").pads.get(pad.GetNumber())
            if target:
                pad.SetNet(nets[target])

    # Snapshot segment geometry before removal: iterating a SWIG track list
    # after deleting an item is unsafe in some distro KiCad Python builds.
    tracks = list(board.GetTracks())
    known = set()
    for item in tracks:
        if item.Type() == pcbnew.PCB_TRACE_T:
            p, q = coord(item)
            known.add((p, q))

    # Remove the former direct rail connections to U4.7, U4.8 and C5.1,
    # plus endpoints produced by the older provisional patch.
    old = [
        ((80.150, 6.675), (79.050, 6.675)),
        ((80.150, 6.025), (80.150, 5.600)),
        ((80.150, 5.600), (80.750, 5.000)),
        ((82.000, 7.950), (78.065, 11.885)),
        ((83.243, 6.707), (82.000, 7.950)),
        ((84.500, 5.062), (83.243, 5.458)),
        ((84.500, 6.938), (82.000, 7.950)),
        # Dead branches left when U4.7/U4.8 and C5.1 stopped being rails.
        ((79.050, 6.675), (79.050, 4.400)),
        ((79.050, 4.400), (79.500, 3.950)),
        ((83.243, 5.458), (83.243, 6.707)),
        ((80.750, 6.177), (80.750, 5.000)),
        # The first bias route grazed U4.6; replace it with an orthogonal
        # dogleg through the channel between U4 and C5.
        ((82.000, 7.950), (80.150, 6.675)),
    ]
    removed = 0
    for item in tracks:
        if item.Type() != pcbnew.PCB_TRACE_T:
            continue
        if any(same_segment(item, a, b) for a, b in old):
            p, q = coord(item)
            board.Remove(item)
            known.discard((p, q))
            known.discard((q, p))
            removed += 1

    # Remove the now-unused +3V3 branch via at (80.75, 5.00).
    for item in tracks:
        if item.Type() != pcbnew.PCB_VIA_T:
            continue
        pos = item.GetPosition()
        if (round(pos.x / 1e6, 3), round(pos.y / 1e6, 3)) == (80.750, 5.000):
            board.Remove(item)
            removed += 1

    # Local bias network.  R8.2 is +5 V; R8.1 and C5.1 are I2C_BIAS.
    r8_pad = {p.GetNumber(): p.GetPosition() for p in r8.Pads()}
    r8_bias = (r8_pad["1"].x / 1e6, r8_pad["1"].y / 1e6)
    r8_5v = (r8_pad["2"].x / 1e6, r8_pad["2"].y / 1e6)
    add_track(board, nets["+5V"], 0.375,
              r8_5v, (83.243, 5.458), known)
    add_track(board, bias, 0.250,
              r8_bias, (82.000, 7.950), known)
    add_track(board, bias, 0.250,
              (82.000, 7.950), (81.100, 7.950), known)
    add_track(board, bias, 0.250,
              (81.100, 7.950), (81.100, 6.975), known)
    add_track(board, bias, 0.250,
              (81.100, 6.975), (80.800, 6.675), known)
    add_track(board, bias, 0.250,
              (80.800, 6.675), (80.150, 6.675), known)
    add_track(board, bias, 0.250,
              (80.150, 6.675), (80.150, 6.025), known)

    # Reconnect the two +5 V regions that formerly met at C5.1.  The route
    # goes around the PCA9306 support parts and above SW1.
    add_track(board, nets["+5V"], 0.500,
              r8_5v, (86.500, r8_5v[1]), known)
    add_track(board, nets["+5V"], 0.500,
              (86.500, r8_5v[1]), (87.200, 5.788), known)
    add_track(board, nets["+5V"], 0.500,
              (87.200, 5.788), (87.200, 8.500), known)
    add_track(board, nets["+5V"], 0.500,
              (87.200, 8.500), (78.065, 11.885), known)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"PCA9306 bias circuit applied; removed {removed} obsolete tracks")


if __name__ == "__main__":
    main()
