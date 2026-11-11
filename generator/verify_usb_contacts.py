#!/usr/bin/env python3
"""Verify the physical and electrical PCB-edge USB-A interface."""

from __future__ import annotations

import math
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"
REPORT = ROOT / "fabrication" / "reports" / "USB_contact_verification.txt"

EXPECTED = {
    "1": ("USB_VBUS", (4.5, 21.5), (7.0, 1.4)),
    "2": ("USB_DM",   (4.5, 24.0), (6.0, 1.2)),
    "3": ("USB_DP",   (4.5, 26.0), (6.0, 1.2)),
    "4": ("GND",      (4.5, 28.5), (7.0, 1.4)),
}
TONGUE = (0.0, 12.0, 19.0, 31.0)  # xmin, xmax, ymin, ymax


def mm(value: int) -> float:
    return value / 1e6


def rect(item):
    box = item.GetBoundingBox()
    return (mm(box.GetX()), mm(box.GetY()),
            mm(box.GetRight()), mm(box.GetBottom()))


def intersects(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or
                a[3] <= b[1] or b[3] <= a[1])


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    j1 = board.FindFootprintByReference("J1")
    if j1 is None:
        raise RuntimeError("J1 missing")
    pads = {pad.GetNumber(): pad for pad in j1.Pads()}
    failures = []
    rows = []

    # Verify the actual outline defines a left-facing 12 x 12 mm tongue.
    edge_pairs = set()
    for edge in board.GetDrawings():
        if edge.GetLayer() != pcbnew.Edge_Cuts:
            continue
        a, b = edge.GetStart(), edge.GetEnd()
        p = (round(mm(a.x), 3), round(mm(a.y), 3))
        q = (round(mm(b.x), 3), round(mm(b.y), 3))
        edge_pairs.add((p, q))
        edge_pairs.add((q, p))
    required_edges = [
        ((0.5, 19.0), (12.0, 19.0)),
        ((12.0, 31.0), (0.5, 31.0)),
        ((0.0, 30.5), (0.0, 19.5)),
    ]
    if not all(pair in edge_pairs for pair in required_edges):
        failures.append("board outline does not contain the expected USB tongue")

    pad_rects = {}
    for number in ("1", "2", "3", "4"):
        pad = pads.get(number)
        if pad is None:
            failures.append(f"J1.{number} is missing")
            continue
        exp_net, exp_pos, exp_size = EXPECTED[number]
        pos = (round(mm(pad.GetPosition().x), 3),
               round(mm(pad.GetPosition().y), 3))
        size = (round(mm(pad.GetSize().x), 3),
                round(mm(pad.GetSize().y), 3))
        angle = round(pad.GetOrientationDegrees() % 360.0, 1)
        box = rect(pad)
        pad_rects[number] = box
        inside = (box[0] >= TONGUE[0] and box[2] <= TONGUE[1] and
                  box[1] >= TONGUE[2] and box[3] <= TONGUE[3])
        parallel = size[0] > size[1] and angle in (0.0, 180.0)
        correct_layers = (pad.IsOnLayer(pcbnew.F_Cu) and
                          pad.IsOnLayer(pcbnew.F_Mask) and
                          not pad.IsOnLayer(pcbnew.B_Cu))
        track_connected = False
        for track in board.GetTracks():
            if track.GetNetname() != exp_net:
                continue
            for endpoint in (track.GetStart(), track.GetEnd()):
                if math.hypot(mm(endpoint.x) - pos[0],
                              mm(endpoint.y) - pos[1]) < 0.001:
                    track_connected = True
                    break
            if track_connected:
                break
        correct = all((pad.GetNetname() == exp_net, pos == exp_pos,
                       size == exp_size, inside, parallel,
                       correct_layers, track_connected))
        if not correct:
            failures.append(f"J1.{number} failed geometry/connectivity checks")
        rows.append((number, pad.GetNetname(), pos, size, angle,
                     inside, track_connected, correct))

    # Pin order when traversing from the lower tongue edge toward the upper
    # edge on the contact side must be VBUS, D-, D+, GND.
    order = [p.GetNumber() for p in sorted(pads.values(),
                                           key=lambda p: p.GetPosition().y)]
    if order != ["1", "2", "3", "4"]:
        failures.append(f"USB contact order is {order}")

    for a_num, a_box in pad_rects.items():
        for b_num, b_box in pad_rects.items():
            if a_num < b_num and intersects(a_box, b_box):
                failures.append(f"J1.{a_num} overlaps J1.{b_num}")

    # Ensure no unrelated pad overlaps any USB contact.
    for fp in board.GetFootprints():
        if fp.GetReference() == "J1":
            continue
        for pad in fp.Pads():
            for number, usb_box in pad_rects.items():
                if intersects(usb_box, rect(pad)):
                    failures.append(
                        f"J1.{number} overlaps {fp.GetReference()}.{pad.GetNumber()}"
                    )

    # No silkscreen item may enter the 12 x 12 mm mating tongue.
    tongue_box = (TONGUE[0], TONGUE[2], TONGUE[1], TONGUE[3])
    silk_hits = []
    for item in board.GetDrawings():
        if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and intersects(
                rect(item), tongue_box):
            silk_hits.append(item.GetClass())
    for fp in board.GetFootprints():
        for item in list(fp.GraphicalItems()) + [fp.Reference(), fp.Value()]:
            if (getattr(item, "IsVisible", lambda: True)() and
                    item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and
                    intersects(rect(item), tongue_box)):
                silk_hits.append(f"{fp.GetReference()}:{item.GetClass()}")
    if silk_hits:
        failures.append(f"silkscreen enters mating tongue: {silk_hits}")

    # Filled zones are forbidden on both sides of the complete tongue.
    fill_hits = 0
    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue
        layer = zone.GetLayer()
        polygons = zone.GetFilledPolysList(layer)
        for xi in range(1, 24):
            for yi in range(39, 62):
                point = pcbnew.VECTOR2I_MM(xi * 0.5, yi * 0.5)
                if polygons.Contains(point):
                    fill_hits += 1
    if fill_hits:
        failures.append(f"zone fill remains on USB tongue ({fill_hits} samples)")

    required_net_members = {
        "USB_VBUS": {("J1", "1"), ("F1", "1")},
        "USB_DM": {("J1", "2"), ("U1", "13"), ("U5", "3"), ("U5", "4")},
        "USB_DP": {("J1", "3"), ("U1", "14"), ("U5", "1"), ("U5", "6")},
        "GND": {("J1", "4"), ("U1", "1"), ("U5", "2")},
    }
    members = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            members.setdefault(pad.GetNetname(), set()).add(
                (fp.GetReference(), pad.GetNumber()))
    for net, required in required_net_members.items():
        if not required.issubset(members.get(net, set())):
            failures.append(
                f"{net} missing members {sorted(required - members.get(net, set()))}"
            )

    unconnected = board.GetConnectivity().GetUnconnectedCount(False)
    if unconnected:
        failures.append(f"board has {unconnected} unconnected items")

    status = "PASS" if not failures else "FAIL"
    lines = [
        "VaultKey USB-A PCB-edge contact verification",
        "============================================",
        f"Board: {BOARD.name}",
        "Actual insertion tip: X=0.000 mm; insertion/contact axis: +X",
        "Actual tongue: X=0.000..12.000, Y=19.000..31.000 mm",
        "Contact side: F.Cu / F.Mask",
        "",
        "Pad | Net      | Position (mm) | Size (mm) | Angle | Inside | Connected | Result",
        "----|----------|---------------|-----------|-------|--------|-----------|-------",
    ]
    for number, net, pos, size, angle, inside, connected, correct in rows:
        lines.append(
            f"{number:>3} | {net:<8} | ({pos[0]:.3f},{pos[1]:.3f}) | "
            f"{size[0]:.3f}x{size[1]:.3f} | {angle:5.1f} | "
            f"{'YES' if inside else 'NO':<6} | "
            f"{'YES' if connected else 'NO':<9} | {'PASS' if correct else 'FAIL'}"
        )
    lines += [
        "",
        "Contact order (lower edge toward upper edge): " + " -> ".join(order),
        "Expected net order: USB_VBUS -> USB_DM -> USB_DP -> GND",
        f"Silkscreen items on mating tongue: {len(silk_hits)}",
        f"Zone-fill samples on mating tongue: {fill_hits}",
        f"Unconnected items: {unconnected}",
        f"Overall result: {status}",
    ]
    if failures:
        lines += ["", "Failures:"] + [f"- {failure}" for failure in failures]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
