#!/usr/bin/env python3
"""Mirror the PCB-edge USB-A contact row and reroute its four nets.

The physical contact row already has the correct USB-A order and geometry.
The hand-routed board had VBUS and GND assigned to the opposite outer pads.
This revision swaps those nets and rebuilds only their short fan-out while
preserving the differential pair and downstream routing.

The distro pcbnew SWIG bindings are fragile when the track container is read
after a removal or addition, so the revision runs in two reloaded phases and
only ever inspects a snapshot of the container.
"""

from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"

# Absolute pad centres after J1's -90 degree footprint transform.
TARGETS = {
    "1": (4.5, 21.5),  # USB_VBUS
    "2": (4.5, 24.0),  # USB_DM
    "3": (4.5, 26.0),  # USB_DP
    "4": (4.5, 28.5),  # GND
}

REMOVALS = (
    # prepare_rev_e.py assigns the corrected net to each edge pad before this
    # phase; pcbnew updates the attached legacy traces with the pad's new net.
    ("USB_VBUS", pcbnew.F_Cu, (4.5, 21.5), (12.5, 21.5)),
    ("USB_VBUS", pcbnew.F_Cu, (7.9, 21.5), (12.5, 21.5)),
    ("USB_VBUS", pcbnew.F_Cu, (7.9, 21.5), (8.707, 21.5)),
    ("USB_VBUS", pcbnew.B_Cu, (8.707, 21.5), (9.375, 23.125)),
    ("GND", pcbnew.F_Cu, (4.5, 28.5), (9.5, 28.5)),
    ("USB_VBUS", pcbnew.F_Cu, (4.5, 28.5), (9.5, 28.5)),
)
VIA_REMOVALS = (
    ("USB_VBUS", (9.5, 28.5)),
    ("GND", (12.5, 21.5)),
    ("USB_VBUS", (12.5, 21.5)),
)

# (net, layer, start, end, width)
TRACKS = (
    ("USB_VBUS", pcbnew.F_Cu, (4.5, 21.5), (8.707, 21.5), 0.5),
    ("USB_VBUS", pcbnew.B_Cu, (8.707, 21.5), (9.3746, 23.1254), 0.5),
    ("GND", pcbnew.F_Cu, (4.5, 28.5), (13.0, 28.5), 0.5),
)
# (net, position, diameter, drill)
VIAS = (
    ("USB_VBUS", (8.707, 21.5), 0.8, 0.4),
    ("GND", (12.5, 21.5), 0.8, 0.4),
    ("GND", (13.0, 28.5), 0.8, 0.4),
)

TOL = 0.03


def pt(x, y):
    return pcbnew.VECTOR2I_MM(x, y)


def near(a, b):
    return abs(a.x / 1e6 - b[0]) < TOL and abs(a.y / 1e6 - b[1]) < TOL


def same_track(track, net, layer, a, b):
    if track.Type() == pcbnew.PCB_VIA_T:
        return False
    if track.GetNetname() != net or track.GetLayer() != layer:
        return False
    s, e = track.GetStart(), track.GetEnd()
    return ((near(s, a) and near(e, b)) or
            (near(s, b) and near(e, a)))


def same_via(track, net, position):
    return (track.Type() == pcbnew.PCB_VIA_T and
            track.GetNetname() == net and
            near(track.GetPosition(), position))


def mirror_pads_and_remove_old_fanout() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    j1 = board.FindFootprintByReference("J1")
    if j1 is None:
        raise RuntimeError("J1 is missing")

    for number, (x, y) in TARGETS.items():
        pad = j1.FindPadByNumber(number)
        if pad is None:
            raise RuntimeError(f"J1.{number} is missing")
        pos = pad.GetPosition()
        if abs(pos.x / 1e6 - x) > TOL or abs(pos.y / 1e6 - y) > TOL:
            raise RuntimeError(f"J1.{number} geometry differs from the verified contact layout")

    snapshot = list(board.GetTracks())
    doomed = []
    for track in snapshot:
        for net, layer, a, b in REMOVALS:
            if same_track(track, net, layer, a, b):
                doomed.append(track)
                break
        else:
            for net, position in VIA_REMOVALS:
                if same_via(track, net, position):
                    doomed.append(track)
                    break
    for track in doomed:
        board.Remove(track)
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"mirrored pads; removed {len(doomed)} old fan-out items")


def add_new_fanout() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    snapshot = list(board.GetTracks())

    for net, layer, a, b, width in TRACKS:
        if any(same_track(t, net, layer, a, b) for t in snapshot):
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pt(*a))
        track.SetEnd(pt(*b))
        track.SetWidth(pcbnew.FromMM(width))
        track.SetLayer(layer)
        track.SetNet(board.FindNet(net))
        board.Add(track)
        snapshot.append(track)

    for net, position, diameter, drill in VIAS:
        if any(same_via(t, net, position) for t in snapshot):
            continue
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pt(*position))
        via.SetWidth(pcbnew.FromMM(diameter))
        via.SetDrill(pcbnew.FromMM(drill))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(board.FindNet(net))
        via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        board.Add(via)
        snapshot.append(via)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print("added mirrored fan-out and refilled zones")


def main() -> None:
    import sys

    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase == "remove":
        mirror_pads_and_remove_old_fanout()
    elif phase == "add":
        add_new_fanout()
    else:
        raise SystemExit(
            "usage: mirror_usb_contacts.py remove|add "
            "(run each phase in its own process)"
        )


if __name__ == "__main__":
    main()
