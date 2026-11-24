#!/usr/bin/env python3
"""Build the VaultKey USB PCB from the data in design.py.

Run from the project root:

    python3 generator/build_pcb.py

The script is deterministic: it always recreates VaultKey_USB.kicad_pcb from
scratch, so the checked-in board and the generator cannot drift apart.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import design  # noqa: E402
import labels  # noqa: E402

BOARD_PATH = ROOT / "VaultKey_USB.kicad_pcb"
DSN_PATH = ROOT / "fabrication" / "VaultKey_USB.dsn"


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def add_outline(board: pcbnew.BOARD) -> None:
    pts = design.OUTLINE
    for i, start in enumerate(pts):
        end = pts[(i + 1) % len(pts)]
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I_MM(*start))
        seg.SetEnd(pcbnew.VECTOR2I_MM(*end))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(mm(0.1))
        board.Add(seg)


def make_nets(board: pcbnew.BOARD) -> dict[str, pcbnew.NETINFO_ITEM]:
    nets: dict[str, pcbnew.NETINFO_ITEM] = {}
    for name in design.NETS:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        nets[name] = net
    return nets


def set_design_rules(board: pcbnew.BOARD) -> None:
    ds = board.GetDesignSettings()

    # Supplied DRC targets.
    ds.m_MinClearance = mm(0.20)
    ds.m_TrackMinWidth = mm(0.20)
    ds.m_CopperEdgeClearance = mm(0.50)
    ds.m_HoleClearance = mm(0.25)
    ds.m_HoleToHoleMin = mm(0.25)
    ds.m_ViasMinSize = mm(0.60)
    ds.m_MinThroughDrill = mm(0.30)
    ds.m_ViasMinAnnularWidth = mm(0.15)
    ds.m_MicroViasMinSize = mm(0.30)
    ds.m_MicroViasMinDrill = mm(0.10)

    # Tented vias on both sides.
    ds.m_TentViasFront = True
    ds.m_TentViasBack = True
    ds.m_PlugViasFront = False
    ds.m_PlugViasBack = False

    # Default net class.
    classes = board.GetAllNetClasses()
    default = classes["Default"]
    default.SetClearance(mm(0.20))
    default.SetTrackWidth(mm(0.25))
    default.SetViaDiameter(mm(0.60))
    default.SetViaDrill(mm(0.30))
    default.SetDiffPairWidth(mm(0.25))
    default.SetDiffPairGap(mm(0.20))
    default.SetDiffPairViaGap(mm(0.25))

    # A slightly wider class for the supply rails.  The autorouter is allowed
    # to use 0.25 mm everywhere, but hand edits should honour these widths.
    power = pcbnew.NETCLASS("Power")
    power.SetClearance(mm(0.25))
    power.SetTrackWidth(mm(0.50))
    power.SetViaDiameter(mm(0.80))
    power.SetViaDrill(mm(0.40))
    board.GetDesignSettings().m_NetSettings.SetNetclass("Power", power)
    for name in design.POWER_NETS:
        board.GetDesignSettings().m_NetSettings.SetNetclassPatternAssignment(
            name, "Power"
        )
    board.SynchronizeNetsAndNetClasses(True)


def load_footprint(part: design.Part) -> pcbnew.FOOTPRINT:
    lib_path = design.FOOTPRINT_LIBS[part.lib]
    fp = pcbnew.FootprintLoad(str(ROOT / lib_path) if not lib_path.startswith("/")
                              else lib_path, part.fp)
    if fp is None:
        raise RuntimeError(f"cannot load footprint {part.lib}:{part.fp}")
    return fp


def clean_footprint(fp: pcbnew.FOOTPRINT, part: design.Part) -> None:
    """Apply small, documented footprint clean-ups.

    * Hide reference/value text on the fabricated silkscreen.  Assembly
      references come from the position file, so the board stays readable.
    * Drop the hard-coded ``REF**`` user text present in the switch footprint
      (it is not a ${REFERENCE} placeholder and duplicates the reference).
    * Remove the very large 1.3-inch OLED courtyard: the display is mounted on
      headers above the board and the bottom-left board screw sits in that gap.
      Keeping the courtyard would produce a false 2-D collision with H2.
    * Bump the ESP32 thermal-via pad drills from 0.2 mm to 0.3 mm so they obey
      the board's 0.3 mm minimum through-drill rule.
    """
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)

    for item in list(fp.GraphicalItems()):
        if item.GetClass() == "PCB_TEXT" and item.GetLayer() in (
            pcbnew.F_SilkS, pcbnew.B_SilkS
        ):
            text = item.GetText()
            if "REF" in text or "${" in text:
                fp.Remove(item)
        if part.ref == "DS1" and item.GetLayer() in (
            pcbnew.F_CrtYd, pcbnew.B_CrtYd
        ):
            fp.Remove(item)

    if part.ref == "U1":
        for pad in fp.Pads():
            drill = pad.GetDrillSize()
            if drill.x > 0 and drill.x < mm(0.3):
                pad.SetDrillSize(pcbnew.VECTOR2I_MM(0.3, 0.3))

    local_models = {
        "U1": "${KIPRJMOD}/lib/VaultKey.3dshapes/ESP32-S3-WROOM-1U.step",
    }
    if part.ref in local_models:
        fp.Models().clear()
        model = pcbnew.FP_3DMODEL()
        model.m_Filename = local_models[part.ref]
        fp.Add3DModel(model)


def place_part(board: pcbnew.BOARD, part: design.Part,
               nets: dict[str, pcbnew.NETINFO_ITEM]) -> pcbnew.FOOTPRINT:
    fp = load_footprint(part)
    fp.SetPosition(pcbnew.VECTOR2I_MM(part.x, part.y))
    fp.SetOrientationDegrees(part.rot)
    board.Add(fp)

    if part.side == "B":
        # Flip around the footprint anchor.  aFlipLeftRight=True mirrors in Y
        # (used for the battery holder so pin 2 stays on the right); False
        # mirrors in X (used for the SOT-23 USB ESD array).
        fp.Flip(fp.GetPosition(), part.flip_lr)

    fp.SetReference(part.ref)
    fp.SetValue(part.value)
    if part.dnp:
        fp.SetDNP(True)

    for pad in fp.Pads():
        net_name = part.pads.get(pad.GetNumber())
        if net_name:
            if net_name not in nets:
                raise RuntimeError(f"{part.ref}: unknown net {net_name!r}")
            pad.SetNet(nets[net_name])
            if net_name == "GND":
                # Solid plane connection for every ground pad.  The large
                # 1.3-inch OLED module makes thermal-spoke geometry tight and
                # a solid connection is the most robust choice for reflow.
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    clean_footprint(fp, part)
    return fp


def add_edge_keepouts(board: pcbnew.BOARD) -> None:
    """Keep tracks, vias and pours 0.75 mm inside the board edge.

    ``copper_edge_clearance`` is a DRC rule, not a router constraint.  Without
    an explicit rule area FreeRouting is happy to run a 0.5 mm power track
    with its centre line 0.66 mm from the edge, leaving only 0.42 mm of
    copper-to-edge clearance.  The 0.75 mm ring guarantees at least 0.5 mm of
    clearance even for the widest power track.
    """
    d = 0.75
    strips = [
        # top
        (12.0, 0.0, 112.5, d),
        # bottom
        (12.0, 50.0 - d, 112.5, 50.0),
        # right
        (112.5 - d, 0.0, 112.5, 50.0),
        # left, above the USB tongue
        (12.0, 0.0, 12.0 + d, 19.0),
        # left, below the USB tongue
        (12.0, 31.0, 12.0 + d, 50.0),
        # tongue, top and bottom
        (0.0, 19.0, 12.0, 19.0 + d),
        (0.0, 31.0 - d, 12.0, 31.0),
        # tongue tip
        (0.0, 19.0, d, 31.0),
    ]
    for i, (x0, y0, x1, y1) in enumerate(strips):
        zone = pcbnew.ZONE(board)
        zone.SetIsRuleArea(True)
        zone.SetLayerSet(pcbnew.LSET.AllCuMask())
        zone.SetDoNotAllowTracks(True)
        zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowZoneFills(True)
        zone.SetDoNotAllowPads(False)
        zone.SetDoNotAllowFootprints(False)
        zone.SetZoneName(f"EDGE_KEEPOUT_{i}")
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            outline.Append(mm(x), mm(y))
        board.Add(zone)


def add_gnd_zones(board: pcbnew.BOARD,
                  gnd: pcbnew.NETINFO_ITEM) -> None:
    # The front pour covers the main body only.  The USB tongue has four long
    # edge fingers and a tip keepout; pouring GND between them creates isolated
    # copper islands that the connectivity checker correctly reports as
    # unconnected.  The back pour still covers the whole outline, so the tongue
    # keeps a solid ground reference on the opposite side.
    main_body = [
        (12.0, 0.0), (112.5, 0.0), (112.5, 50.0), (12.0, 50.0),
    ]
    outlines = {
        pcbnew.F_Cu: main_body,
        pcbnew.B_Cu: design.OUTLINE,
    }
    for layer, poly_pts in outlines.items():
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(gnd)
        zone.SetZoneName("GND_" + board.GetLayerName(layer).replace(".", "_"))
        zone.SetLocalClearance(mm(0.25))
        zone.SetMinThickness(mm(0.25))
        zone.SetThermalReliefGap(mm(0.30))
        zone.SetThermalReliefSpokeWidth(mm(0.50))
        zone.SetHatchGap(mm(0.5))
        zone.SetHatchThickness(mm(0.25))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.SetMinIslandArea(0)
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in poly_pts:
            outline.Append(mm(x), mm(y))
        board.Add(zone)


def add_usb_gnd_stitch(board: pcbnew.BOARD,
                       gnd: pcbnew.NETINFO_ITEM) -> None:
    """Tie the USB shell/ground finger into the main ground pour.

    J1 pad 1 is the USB-A ground contact on the tongue. The front pour starts
    at the main-body edge (x = 12 mm), so a short 0.5 mm track and a via carry
    that finger to both ground planes.
    """
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(4.5, 21.5))
    track.SetEnd(pcbnew.VECTOR2I_MM(13.0, 22.0))
    track.SetWidth(mm(0.50))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(gnd)
    board.Add(track)

    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I_MM(13.0, 22.0))
    via.SetWidth(mm(0.80))
    via.SetDrill(mm(0.40))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(gnd)
    via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(via)


def add_keepouts(board: pcbnew.BOARD) -> None:
    """Keep copper pours off the complete USB-A mating tongue.

    Routed, solder-mask-covered signals remain allowed. Zone fill is excluded
    from X=0..12 mm so J1 is the only exposed mating copper.
    """
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetLayerSet(pcbnew.LSET.AllCuMask())
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowTracks(False)
    zone.SetDoNotAllowVias(False)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    zone.SetZoneName("USB_TONGUE_POUR_KEEPOUT")
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in [
        (0.0, 19.0), (12.0, 19.0), (12.0, 31.0), (0.0, 31.0),
    ]:
        outline.Append(mm(x), mm(y))
    board.Add(zone)


def add_board_text(board: pcbnew.BOARD) -> None:
    tb = board.GetTitleBlock()
    tb.SetTitle("VaultKey USB Security Key")
    tb.SetRevision("E")
    tb.SetCompany("VaultKey")
    tb.SetComment(0, "USB-A edge connector, ESP32-S3, OLED, DS1307 RTC")
    tb.SetComment(1, "2-layer, 1.6 mm FR4, 1 oz copper")
    tb.SetComment(2, "Generated by generator/build_pcb.py")

    for text, x, y, size in [
        ("VAULTKEY", 90.0, 46.5, 1.6),
        ("USB 2.0", 4.0, 17.0, 0.8),
        ("Rev E", 90.0, 48.2, 1.0),
    ]:
        item = pcbnew.PCB_TEXT(board)
        item.SetText(text)
        item.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        item.SetLayer(pcbnew.F_SilkS)
        item.SetTextSize(pcbnew.VECTOR2I_MM(size, size))
        item.SetTextThickness(mm(0.15))
        board.Add(item)


def main() -> None:
    if BOARD_PATH.exists():
        BOARD_PATH.unlink()

    board = pcbnew.CreateEmptyBoard()
    board.SetFileName(str(BOARD_PATH))

    add_outline(board)
    nets = make_nets(board)
    set_design_rules(board)

    for part in design.PARTS:
        place_part(board, part, nets)

    add_usb_gnd_stitch(board, nets["GND"])
    add_gnd_zones(board, nets["GND"])
    add_keepouts(board)
    add_edge_keepouts(board)
    add_board_text(board)
    labels.apply(board)

    board.BuildListOfNets()
    board.SynchronizeNetsAndNetClasses(True)

    pcbnew.SaveBoard(str(BOARD_PATH), board)
    print(f"wrote {BOARD_PATH} ({board.GetFootprints().__len__()} footprints, "
          f"{len(board.GetTracks())} tracks)")

    # Fill zones once so that the saved board displays sensibly before the
    # autorouter runs.  The board is filled again after SES import.
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD_PATH), board)

    DSN_PATH.parent.mkdir(parents=True, exist_ok=True)
    ok = pcbnew.ExportSpecctraDSN(board, str(DSN_PATH))
    print(f"DSN export: {ok} -> {DSN_PATH}")


if __name__ == "__main__":
    main()
