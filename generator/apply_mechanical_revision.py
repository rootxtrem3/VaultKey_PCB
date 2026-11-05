#!/usr/bin/env python3
"""Install the slot-style RTC holder and hole-free OLED footprint."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_pcb  # noqa: E402
import design  # noqa: E402


BOARD = ROOT / "VaultKey_USB.kicad_pcb"


def segment(item):
    a, b = item.GetStart(), item.GetEnd()
    return ((round(a.x / 1e6, 3), round(a.y / 1e6, 3)),
            (round(b.x / 1e6, 3), round(b.y / 1e6, 3)))


def same_segment(item, p, q):
    a, b = segment(item)
    return (a, b) in ((p, q), (q, p))


def place_loaded(board, fp, ref, nets):
    part = design.part_by_ref(ref)
    fp.SetPosition(pcbnew.VECTOR2I_MM(part.x, part.y))
    fp.SetOrientationDegrees(part.rot)
    board.Add(fp)
    if part.side == "B":
        fp.Flip(fp.GetPosition(), part.flip_lr)
    fp.SetReference(part.ref)
    fp.SetValue(part.value)
    fp.SetFPIDAsString(f"{part.lib}:{part.fp}")
    for pad in fp.Pads():
        net_name = part.pads.get(pad.GetNumber())
        if net_name:
            pad.SetNet(nets[net_name])
            if net_name == "GND":
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    build_pcb.clean_footprint(fp, part)
    return fp


def replace_footprint(board, ref, nets, new_fp):
    old = board.FindFootprintByReference(ref)
    if old is not None:
        board.Remove(old)
    return place_loaded(board, new_fp, ref, nets)


def apply_ds1() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    ds1 = board.FindFootprintByReference("DS1")
    if ds1 is None:
        raise RuntimeError("DS1 is missing")
    removed = 0
    for pad in list(ds1.Pads()):
        if not pad.GetNumber():
            ds1.Remove(pad)
            removed += 1
    changed = bool(removed)
    target_id = "VaultKey:Adafruit_SSD1306_NoMountingHoles"
    if ds1.GetFPIDAsString() != target_id:
        ds1.SetFPIDAsString(target_id)
        changed = True
    if changed:
        print("replaced DS1 with the no-corner-hole footprint")
        pcbnew.SaveBoard(str(BOARD), board)


def add_bt1() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    nets = {name: board.FindNet(name) for name in design.NETS}
    bt1 = board.FindFootprintByReference("BT1")
    bt1_name = str(bt1.GetFPID().GetLibItemName()) if bt1 else ""
    if bt1_name != "BatteryHolder_Keystone_1058_1x2032":
        if bt1 is not None:
            bt1.SetReference("BT1_OLD")
        new_bt1 = build_pcb.load_footprint(design.part_by_ref("BT1"))
        place_loaded(board, new_bt1, "BT1", nets)
        print("replaced BT1 with the Keystone 1058 low-profile holder")
        pcbnew.SaveBoard(str(BOARD), board)
    elif (bt1.GetPosition() != pcbnew.VECTOR2I_MM(96.0, 18.0) or
          abs((bt1.GetOrientationDegrees() % 360.0) - 270.0) > 0.01 or
          bt1.GetFPIDAsString() != "Battery:BatteryHolder_Keystone_1058_1x2032"):
        bt1.SetPosition(pcbnew.VECTOR2I_MM(96.0, 18.0))
        # B-side Y mirroring negates the 90-degree source orientation.
        bt1.SetOrientationDegrees(270.0)
        bt1.SetFPIDAsString("Battery:BatteryHolder_Keystone_1058_1x2032")
        pcbnew.SaveBoard(str(BOARD), board)


def remove_old_bt1() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    old = board.FindFootprintByReference("BT1_OLD")
    if old is not None:
        board.Remove(old)
        pcbnew.SaveBoard(str(BOARD), board)


def apply_route() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    nets = {name: board.FindNet(name) for name in design.NETS}
    tracks = list(board.GetTracks())

    for item in tracks:
        if item.GetNetname() == "VBAT":
            board.Remove(item)

    route = [
        (pcbnew.F_Cu, (64.585, 8.625), (68.000, 8.625)),
        (pcbnew.F_Cu, (68.000, 8.625), (68.000, 0.900)),
        (pcbnew.F_Cu, (68.000, 0.900), (94.500, 0.900)),
        (pcbnew.F_Cu, (94.500, 0.900), (96.000, 1.200)),
        (pcbnew.B_Cu, (96.000, 1.200), (96.000, 3.320)),
    ]
    for layer, start, end in route:
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I_MM(*start))
        track.SetEnd(pcbnew.VECTOR2I_MM(*end))
        track.SetWidth(pcbnew.FromMM(0.25))
        track.SetLayer(layer)
        track.SetNet(nets["VBAT"])
        board.Add(track)

    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I_MM(96.0, 1.2))
    via.SetWidth(pcbnew.FromMM(0.60))
    via.SetDrill(pcbnew.FromMM(0.30))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(nets["VBAT"])
    via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(via)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)


def main() -> None:
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        {"ds1": apply_ds1, "bt1add": add_bt1,
         "bt1remove": remove_old_bt1, "route": apply_route}[mode]()
        return
    # Keep each footprint replacement in a fresh process to avoid a plugin
    # lifetime defect in the distro pcbnew SWIG bindings.
    for mode in ("ds1", "bt1add", "bt1remove", "route"):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), mode], check=False)
        if result.returncode not in (0, -11, 139):
            raise subprocess.CalledProcessError(result.returncode, result.args)
    print("mechanical revision applied")


if __name__ == "__main__":
    main()
