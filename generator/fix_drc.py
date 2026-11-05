#!/usr/bin/env python3
"""Post-route cleanup: widen sub-0.2 mm tracks and stitch remaining GND islands."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"

MIN_W = 0.20


def mm(v: float) -> int:
    return pcbnew.FromMM(v)


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def widen_tracks(board):
    changed = 0
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_TRACE_T:
            continue
        w = t.GetWidth() / 1e6
        if w < MIN_W - 1e-9:
            t.SetWidth(mm(MIN_W))
            changed += 1
    print(f"widened {changed} tracks to {MIN_W} mm")
    return changed


def clearance_ok(board, pt, net, need):
    """True when pt is at least `need` mm from all copper of other nets."""
    x, y = pt.x / 1e6, pt.y / 1e6
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == net.GetNetCode():
                continue
            px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
            r = math.hypot(pad.GetSize().x, pad.GetSize().y) / 2 / 1e6
            if math.hypot(x - px, y - py) - r < need:
                return False
    for t in board.GetTracks():
        if t.GetNetCode() == net.GetNetCode():
            continue
        a = t.GetStart()
        b = t.GetEnd()
        r = t.GetWidth() / 2 / 1e6 if t.Type() == pcbnew.PCB_TRACE_T else 0.4
        d = seg_dist(x, y, a.x / 1e6, a.y / 1e6, b.x / 1e6, b.y / 1e6)
        if d - r < need:
            return False
    for edge in board.GetDrawings():
        if edge.GetLayer() != pcbnew.Edge_Cuts:
            continue
        a, b = edge.GetStart(), edge.GetEnd()
        d = seg_dist(x, y, a.x / 1e6, a.y / 1e6, b.x / 1e6, b.y / 1e6)
        if d < need + 0.3:
            return False
    return True


def add_via(board, pt, net):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pt)
    via.SetWidth(mm(0.60))
    via.SetDrill(mm(0.30))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(via)


def islands(board, layer):
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetLayer() != layer:
            continue
        polys = zone.GetFilledPolysList(layer)
        for i in range(polys.OutlineCount()):
            o = polys.COutline(i)
            pts = [o.CPoint(j) for j in range(o.PointCount())]
            if not pts:
                continue
            xs = [p.x / 1e6 for p in pts]
            ys = [p.y / 1e6 for p in pts]
            yield zone, o, min(xs), min(ys), max(xs), max(ys)


def stitch(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    gnd = board.FindNet("GND")
    added = 0
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        for zone, outline, x0, y0, x1, y1 in list(islands(board, layer)):
            # Only small islands can be disconnected; the main pour is large.
            if (x1 - x0) * (y1 - y0) > 200:
                continue
            # Already stitched by an earlier pass?
            already = False
            for t in board.GetTracks():
                if t.Type() == pcbnew.PCB_VIA_T and outline.PointInside(t.GetPosition()):
                    already = True
                    break
            if already:
                continue
            best = None
            step = 0.1
            yy = y0 + step / 2
            while yy < y1:
                xx = x0 + step / 2
                while xx < x1:
                    pt = pcbnew.VECTOR2I_MM(round(xx, 2), round(yy, 2))
                    if outline.PointInside(pt) and clearance_ok(board, pt, gnd, 0.55):
                        # prefer points away from the outline edge
                        d = min(seg_dist(xx, yy, outline.CPoint(j).x / 1e6,
                                         outline.CPoint(j).y / 1e6,
                                         outline.CPoint((j + 1) % outline.PointCount()).x / 1e6,
                                         outline.CPoint((j + 1) % outline.PointCount()).y / 1e6)
                                for j in range(outline.PointCount()))
                        if best is None or d > best[0]:
                            best = (d, pt)
                    xx += step
                yy += step
            if best is None:
                print(f"WARNING: no stitching point in island "
                      f"({x0:.2f},{y0:.2f})-({x1:.2f},{y1:.2f}) on "
                      f"{board.GetLayerName(layer)}")
                continue
            add_via(board, best[1], gnd)
            added += 1
            print(f"stitched island ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) on "
                  f"{board.GetLayerName(layer)} at "
                  f"({best[1].x / 1e6:.2f},{best[1].y / 1e6:.2f})")
    print(f"added {added} stitching vias")
    return added


def fix_stray_vias(board):
    """Move GND stitching vias that collide with a pad hole."""
    gnd = board.FindNet("GND")
    holes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetDrillSize().x > 0:
                holes.append((pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6,
                              pad.GetDrillSize().x / 1e6))
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            continue
        x, y = t.GetPosition().x / 1e6, t.GetPosition().y / 1e6
        for hx, hy, hd in holes:
            gap = math.hypot(x - hx, y - hy) - hd / 2 - 0.15
            if 0 < gap < 0.25:
                print(f"via at ({x:.2f},{y:.2f}) too close to hole at "
                      f"({hx:.2f},{hy:.2f}) gap {gap:.3f}; nudging")
                # push directly away from the hole
                ang = math.atan2(y - hy, x - hx)
                for d in (0.15, 0.25, 0.35, 0.5):
                    nx = x + d * math.cos(ang)
                    ny = y + d * math.sin(ang)
                    pt = pcbnew.VECTOR2I_MM(round(nx, 3), round(ny, 3))
                    ng = math.hypot(nx - hx, ny - hy) - hd / 2 - 0.15
                    if ng >= 0.25 and clearance_ok(board, pt, gnd, 0.45):
                        t.SetPosition(pt)
                        print(f"  -> ({nx:.2f},{ny:.2f}) gap {ng:.3f}")
                        break
                else:
                    print("  !! could not nudge")


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    fix_stray_vias(board)
    widen_tracks(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    stitch(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print("unconnected:", board.GetConnectivity().GetUnconnectedCount(False))


if __name__ == "__main__":
    main()
