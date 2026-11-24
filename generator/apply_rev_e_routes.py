#!/usr/bin/env python3
"""Apply the Rev-E recovery and LED routes without moving existing parts."""

from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
BOARD_PATH = ROOT / "VaultKey_USB.kicad_pcb"

# FreeRouting's valid GPIO1 route, normalized to the board's 0.20 mm minimum.
LED_F = [
    ((46.5875, 3.5), (46.5875, 3.8507)),
    ((46.5875, 3.8507), (49.2459, 6.5091)),
    ((48.7634, 42.9467), (50.4567, 44.64)),
    ((50.4567, 44.64), (53.25, 44.64)),
    ((48.7634, 42.9467), (52.0517, 39.4292)),
    ((52.0517, 39.4292), (52.0517, 28.8466)),
    ((52.0517, 28.8466), (58.2304, 22.6679)),
    ((58.2304, 22.6679), (58.2304, 21.5556)),
]
LED_B = [
    ((49.2459, 6.5091), (58.2304, 15.4936)),
    ((58.2304, 15.4936), (58.2304, 21.5556)),
]
LED_VIAS = ((49.2459, 6.5091), (58.2304, 21.5556))
GROUND_STITCH_VIAS = ((51.5, 42.0),)


def near(point, xy, tolerance=0.01):
    return (abs(point.x / 1e6 - xy[0]) < tolerance and
            abs(point.y / 1e6 - xy[1]) < tolerance)


def add_track(board, net, layer, start, end, width):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(*start))
    track.SetEnd(pcbnew.VECTOR2I_MM(*end))
    track.SetWidth(pcbnew.FromMM(width))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net))
    board.Add(track)


def main():
    board = pcbnew.LoadBoard(str(BOARD_PATH))

    existing_tracks = list(board.GetTracks())
    existing_ground_vias = [
        item.GetPosition() for item in existing_tracks
        if item.Type() == pcbnew.PCB_VIA_T and item.GetNetname() == "GND"
    ]

    # Replace only the added GPIO1 route to make reruns deterministic.
    for item in existing_tracks:
        if item.GetNetname() == "LED_GPIO":
            board.Remove(item)

    boot_start = (101.0, 33.5)
    boot_end = (104.0, 36.0)
    boot_connected = any(
        item.Type() != pcbnew.PCB_VIA_T and item.GetNetname() == "BOOT" and
        item.GetLayer() == pcbnew.F_Cu and
        ((near(item.GetStart(), boot_start) and near(item.GetEnd(), boot_end)) or
         (near(item.GetStart(), boot_end) and near(item.GetEnd(), boot_start)))
        for item in existing_tracks
    )
    if not boot_connected:
        add_track(board, "BOOT", pcbnew.F_Cu, boot_start, boot_end, 0.25)

    for start, end in LED_F:
        add_track(board, "LED_GPIO", pcbnew.F_Cu, start, end, 0.20)
    for start, end in LED_B:
        add_track(board, "LED_GPIO", pcbnew.B_Cu, start, end, 0.20)
    for position in LED_VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I_MM(*position))
        via.SetWidth(pcbnew.FromMM(0.6))
        via.SetDrill(pcbnew.FromMM(0.3))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(board.FindNet("LED_GPIO"))
        via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        board.Add(via)

    # Reconnect the small F.Cu ground island beside C6 to the continuous B.Cu
    # ground plane after the GPIO1 fanout separates the local copper region.
    for position in GROUND_STITCH_VIAS:
        if any(near(existing, position) for existing in existing_ground_vias):
            continue
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I_MM(*position))
        via.SetWidth(pcbnew.FromMM(0.6))
        via.SetDrill(pcbnew.FromMM(0.3))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(board.FindNet("GND"))
        via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        board.Add(via)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print("Rev-E BOOT recovery and LED routing applied")


if __name__ == "__main__":
    main()
