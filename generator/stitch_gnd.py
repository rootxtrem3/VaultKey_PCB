#!/usr/bin/env python3
"""Add GND stitching vias for any disconnected copper island.

FreeRouting treats a ground pour as a plane and does not add stitching vias.
After importing a session the front and back pours can end up as several
electrically separate regions (they are all GND, but the connectivity checker
still wants a copper path between them).  This script finds each filled island
and drops a tented 0.6/0.3 mm via into a clear spot, tying it to the continuous
pour on the opposite layer.
"""

from __future__ import annotations

import math
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"


def mm(v: float) -> int:
    return pcbnew.FromMM(v)


def point_clear(board: pcbnew.BOARD, pt: pcbnew.VECTOR2I,
                net: pcbnew.NETINFO_ITEM) -> bool:
    x, y = pt.x / 1e6, pt.y / 1e6
    # Board-edge margin.
    for edge in board.GetDrawings():
        if edge.GetLayer() != pcbnew.Edge_Cuts:
            continue
        sx, sy = edge.GetStart().x / 1e6, edge.GetStart().y / 1e6
        ex, ey = edge.GetEnd().x / 1e6, edge.GetEnd().y / 1e6
        # distance from point to segment
        dx, dy = ex - sx, ey - sy
        if dx == dy == 0:
            dist = math.hypot(x - sx, y - sy)
        else:
            t = max(0.0, min(1.0, ((x - sx) * dx + (y - sy) * dy) / (dx * dx + dy * dy)))
            dist = math.hypot(x - (sx + t * dx), y - (sy + t * dy))
        if dist < 1.0:
            return False

    # Keepout rule areas.
    for zone in board.Zones():
        if not zone.GetIsRuleArea():
            continue
        if zone.Outline().Contains(pt):
            return False

    # Pads and drilled holes.
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == net.GetNetCode():
                continue
            d = math.hypot(x - pad.GetPosition().x / 1e6,
                           y - pad.GetPosition().y / 1e6)
            if d < 1.0:
                return False
            if pad.GetDrillSize().x > 0 and d < 1.4:
                return False

    # Tracks and vias belonging to other nets.
    for track in board.GetTracks():
        if track.GetNetCode() == net.GetNetCode():
            continue
        d = math.hypot(x - track.GetStart().x / 1e6,
                       y - track.GetStart().y / 1e6)
        d2 = math.hypot(x - track.GetEnd().x / 1e6,
                        y - track.GetEnd().y / 1e6)
        if min(d, d2) < 1.0:
            return False
    return True


def add_via(board: pcbnew.BOARD, pt: pcbnew.VECTOR2I,
            net: pcbnew.NETINFO_ITEM) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pt)
    via.SetWidth(mm(0.60))
    via.SetDrill(mm(0.30))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(via)


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    gnd = board.FindNet("GND")

    added = 0
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetNetname() != "GND":
            continue
        layer = zone.GetLayer()
        polys = zone.GetFilledPolysList(layer)
        for i in range(polys.OutlineCount()):
            outline = polys.COutline(i)
            pts = [outline.CPoint(j) for j in range(outline.PointCount())]
            if not pts:
                continue
            xs = [p.x / 1e6 for p in pts]
            ys = [p.y / 1e6 for p in pts]
            bbox_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if bbox_area > 800:  # main pour, not an island
                continue
            placed = False
            for yy in range(int(min(ys)) + 1, int(max(ys)), 1):
                for xx in range(int(min(xs)) + 1, int(max(xs)), 1):
                    pt = pcbnew.VECTOR2I_MM(xx + 0.5, yy + 0.5)
                    if not outline.PointInside(pt):
                        continue
                    if not point_clear(board, pt, gnd):
                        continue
                    add_via(board, pt, gnd)
                    added += 1
                    placed = True
                    break
                if placed:
                    break
            if not placed:
                print(f"WARNING: no free stitching point for island {i} "
                      f"on {board.GetLayerName(layer)} bbox "
                      f"({min(xs):.1f},{min(ys):.1f})-({max(xs):.1f},{max(ys):.1f})")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"added {added} GND stitching vias")


if __name__ == "__main__":
    main()
