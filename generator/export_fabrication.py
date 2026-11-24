#!/usr/bin/env python3
"""Validate and export the complete VaultKey USB manufacturing package."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import design  # noqa: E402

PCB = ROOT / "VaultKey_USB.kicad_pcb"
SCH = ROOT / "VaultKey_USB.kicad_sch"
FAB = ROOT / "fabrication"
GERBERS = FAB / "gerbers"
DRILL = FAB / "drill"
ASSEMBLY = FAB / "assembly"
REPORTS = FAB / "reports"
MODELS = FAB / "3d"
DOCS = ROOT / "docs"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def mkdirs() -> None:
    for path in (GERBERS, DRILL, ASSEMBLY, REPORTS, MODELS, DOCS):
        path.mkdir(parents=True, exist_ok=True)


def validate_and_report() -> None:
    run("python3", "generator/build_custom_footprints.py")
    run("python3", "generator/apply_mechanical_revision.py")
    run("python3", "generator/fix_usb_contacts.py")
    run("python3", "generator/apply_labels.py")
    run("FreeCADCmd", "-c",
        "exec(open('generator/build_3d_models.py').read())")
    run("python3", "generator/apply_3d_models.py")
    run("python3", "generator/build_project.py")
    run("python3", "generator/build_sch.py")
    run("kicad-cli", "pcb", "drc", "--severity-all", "--refill-zones",
        "--exit-code-violations", "-o", str(REPORTS / "DRC_report.txt"), str(PCB))
    run("python3", "generator/verify_usb_contacts.py")
    run("kicad-cli", "sch", "erc", "--severity-all", "--exit-code-violations",
        "-o", str(REPORTS / "ERC_report.txt"), str(SCH))
    netlist = REPORTS / "VaultKey_USB.net"
    run("kicad-cli", "sch", "export", "netlist", "-o", str(netlist), str(SCH))
    result = subprocess.run(
        ["python3", "generator/check_netlist.py", str(netlist)],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    (REPORTS / "netlist_equivalence.txt").write_text(result.stdout)
    print(result.stdout.strip())

    board = pcbnew.LoadBoard(str(PCB))
    edge_points = []
    for item in board.GetDrawings():
        if item.GetLayer() == pcbnew.Edge_Cuts:
            edge_points.extend([item.GetStart(), item.GetEnd()])
    xs = [p.x / 1e6 for p in edge_points]
    ys = [p.y / 1e6 for p in edge_points]
    actual = (max(xs) - min(xs), max(ys) - min(ys))
    if any(abs(a - b) > 1e-6 for a, b in zip(actual, (design.BOARD_W, design.BOARD_H))):
        raise RuntimeError(f"board dimensions are {actual}, expected 112.5 x 50.0 mm")
    if board.GetConnectivity().GetUnconnectedCount(False) != 0:
        raise RuntimeError("PCB has unconnected items")

    locked = ("J1", "DS1", "U1", "U2", "SW1", "SW2", "SW3", "SW4")
    lines = [
        "VaultKey USB mechanical/electrical validation",
        "============================================",
        f"Edge coordinate bounds: {min(xs):.3f}, {min(ys):.3f} to "
        f"{max(xs):.3f}, {max(ys):.3f} mm",
        f"Exact outline dimensions: {actual[0]:.3f} x {actual[1]:.3f} mm",
        f"Board thickness: {board.GetDesignSettings().GetBoardThickness() / 1e6:.3f} mm",
        f"Copper layers: {board.GetCopperLayerCount()}",
        f"Footprints: {len(board.GetFootprints())}",
        f"Tracks: {sum(t.Type() == pcbnew.PCB_TRACE_T for t in board.GetTracks())}",
        f"Vias: {sum(t.Type() == pcbnew.PCB_VIA_T for t in board.GetTracks())}",
        "Unconnected items: 0",
        "",
        "Locked placements:",
    ]
    for ref in locked:
        fp = board.FindFootprintByReference(ref)
        p = fp.GetPosition()
        part = design.part_by_ref(ref)
        got = (p.x / 1e6, p.y / 1e6, fp.GetOrientationDegrees())
        expected = (part.x, part.y, part.rot)
        if max(abs(a - b) for a, b in zip(got, expected)) > 1e-5:
            raise RuntimeError(f"locked placement changed: {ref}: {got} != {expected}")
        lines.append(f"  {ref:4s} X={got[0]:8.3f} Y={got[1]:8.3f} rot={got[2]:7.1f} deg")
    lines += ["", "Mounting holes:"]
    for ref in ("H1", "H2", "H3", "H4"):
        fp = board.FindFootprintByReference(ref)
        p = fp.GetPosition()
        lines.append(f"  {ref}: ({p.x / 1e6:.3f}, {p.y / 1e6:.3f}) mm, 2.7 mm NPTH")

    ds1 = board.FindFootprintByReference("DS1")
    blank_oled_pads = [p for p in ds1.Pads() if not p.GetNumber()]
    if blank_oled_pads:
        raise RuntimeError("OLED corner drills are still present")
    bt1 = board.FindFootprintByReference("BT1")
    if str(bt1.GetFPID().GetLibItemName()) != "BatteryHolder_Keystone_1058_1x2032":
        raise RuntimeError("BT1 is not the Keystone 1058 slot-style holder")
    lines += [
        "",
        "OLED module corner drills: 0 (intentionally removed)",
        "RTC battery holder: Keystone 1058/1058TR, bottom side",
    ]

    for item in board.GetTracks():
        if item.Type() == pcbnew.PCB_VIA_T:
            if (item.GetFrontTentingMode() != pcbnew.TENTING_MODE_TENTED or
                    item.GetBackTentingMode() != pcbnew.TENTING_MODE_TENTED):
                raise RuntimeError("found an untented via")
    lines += ["", "All vias are tented on front and back."]
    lengths = {}
    for item in board.GetTracks():
        if item.Type() == pcbnew.PCB_TRACE_T:
            lengths[item.GetNetname()] = lengths.get(item.GetNetname(), 0.0) + item.GetLength() / 1e6
    lines += [
        "",
        f"USB D+ routed length: {lengths['USB_DP']:.3f} mm",
        f"USB D- routed length: {lengths['USB_DM']:.3f} mm",
        f"USB pair length mismatch: {abs(lengths['USB_DP'] - lengths['USB_DM']):.3f} mm",
    ]
    (REPORTS / "mechanical_validation.txt").write_text("\n".join(lines) + "\n")


def export_manufacturing() -> None:
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
    run("kicad-cli", "pcb", "export", "gerbers", "--check-zones",
        "--subtract-soldermask", "--precision", "6", "-l", layers,
        "-o", str(GERBERS), str(PCB))
    run("kicad-cli", "pcb", "export", "drill", "--format", "excellon",
        "--drill-origin", "absolute", "--excellon-units", "mm",
        "--excellon-separate-th", "--generate-map", "--map-format", "pdf",
        "--generate-report", "--report-path", str(REPORTS / "drill_report.txt"),
        "-o", str(DRILL), str(PCB))
    run("kicad-cli", "pcb", "export", "ipcd356", "-o",
        str(REPORTS / "VaultKey_USB.d356"), str(PCB))
    run("kicad-cli", "pcb", "export", "stats", "--format", "report",
        "--units", "mm", "--subtract-holes-from-board", "-o",
        str(REPORTS / "board_statistics.txt"), str(PCB))
    run("kicad-cli", "pcb", "export", "stats", "--format", "json",
        "--units", "mm", "--subtract-holes-from-board", "-o",
        str(REPORTS / "board_statistics.json"), str(PCB))

    run("kicad-cli", "sch", "export", "bom", "--exclude-dnp",
        "--fields", "Reference,Value,Footprint,Description,QUANTITY,DNP",
        "--labels", "References,Value,Footprint,Description,Quantity,DNP",
        "--group-by", "Value,Footprint", "--sort-field", "Reference", "-o",
        str(ASSEMBLY / "VaultKey_USB_BOM.csv"), str(SCH))
    run("kicad-cli", "pcb", "export", "pos", "--side", "both", "--format", "csv",
        "--units", "mm", "--exclude-dnp", "-o",
        str(ASSEMBLY / "VaultKey_USB_all_positions.csv"), str(PCB))
    for side, label in (("front", "top"), ("back", "bottom")):
        run("kicad-cli", "pcb", "export", "pos", "--side", side,
            "--format", "csv", "--units", "mm", "--smd-only", "--exclude-dnp",
            "-o", str(ASSEMBLY / f"VaultKey_USB_{label}_SMD_positions.csv"), str(PCB))

    run("kicad-cli", "pcb", "export", "step", "--force", "--subst-models",
        "--no-dnp", "-o", str(MODELS / "VaultKey_USB.step"), str(PCB))


def export_docs() -> None:
    run("kicad-cli", "sch", "export", "pdf", "-o",
        str(DOCS / "VaultKey_USB_Schematic.pdf"), str(SCH))
    run("kicad-cli", "pcb", "export", "svg", "--mode-single",
        "--page-size-mode", "2", "--exclude-drawing-sheet", "--check-zones",
        "-l", "F.Cu,F.Silkscreen,F.Mask,Edge.Cuts", "-o",
        str(DOCS / "VaultKey_USB_PCB_Front.svg"), str(PCB))
    run("kicad-cli", "pcb", "export", "svg", "--mode-single", "--mirror",
        "--page-size-mode", "2", "--exclude-drawing-sheet", "--check-zones",
        "-l", "B.Cu,B.Silkscreen,B.Mask,Edge.Cuts", "-o",
        str(DOCS / "VaultKey_USB_PCB_Back.svg"), str(PCB))
    run("kicad-cli", "pcb", "export", "pdf", "--mode-single", "--black-and-white",
        "--check-zones", "--scale", "1", "-l",
        "F.Cu,F.Silkscreen,F.Mask,Edge.Cuts", "-o",
        str(DOCS / "VaultKey_USB_PCB_Front_1to1.pdf"), str(PCB))
    run("kicad-cli", "pcb", "export", "pdf", "--mode-single", "--black-and-white",
        "--mirror", "--check-zones", "--scale", "1", "-l",
        "B.Cu,B.Silkscreen,B.Mask,Edge.Cuts", "-o",
        str(DOCS / "VaultKey_USB_PCB_Back_1to1.pdf"), str(PCB))

    render_common = ("kicad-cli", "pcb", "render", "--width", "2200",
                     "--height", "1100", "--quality", "high",
                     "--background", "transparent", "--use-board-stackup-colors")
    run(*render_common, "--side", "top", "-o",
        str(DOCS / "VaultKey_USB_3D_Top.png"), str(PCB))
    run(*render_common, "--side", "bottom", "-o",
        str(DOCS / "VaultKey_USB_3D_Bottom.png"), str(PCB))
    run(*render_common, "--side", "top", "--perspective", "--floor",
        "--rotate", "-35,0,-45", "--zoom", "0.85", "-o",
        str(DOCS / "VaultKey_USB_3D_Isometric.png"), str(PCB))


def write_notes_and_archive() -> None:
    notes = """VaultKey USB fabrication notes
==============================

Board outline: 112.500 mm x 50.000 mm overall.
Main body: X=12.000..112.500 mm, 100.500 mm x 50.000 mm.
USB-A tongue: X=0.000..12.000 mm, Y=19.000..31.000 mm with 0.5 mm tip chamfers.
Stackup: 2-layer, 1.6 mm finished FR4, 1 oz copper unless the fabricator requires otherwise.
Finish: standard ENIG is specified for this low-cycle prototype; hard gold is
not required. Verify the fabricator's edge-plating process and insertion life.
Release status: PCB source passes DRC; perform physical USB insertion and
hardware validation before production use.
Solder mask: both sides; all vias are tented on both sides.
Minimum track/space: 0.20 / 0.20 mm.
Copper-to-edge: 0.50 mm minimum.
Minimum drill: 0.30 mm; standard signal vias 0.60/0.30 mm and power vias 0.80/0.40 mm.
Mounting holes: 2.7 mm NPTH at (16,3.5), (15,47), (108.5,3.5), (108,46) mm.

USB-A PCB-edge contacts
-----------------------
Contact side: front copper/front mask. Tongue: X=0..12 mm, Y=19..31 mm.
Pad 4 GND:      center (4.5,21.5), 7.0 x 1.4 mm.
Pad 3 USB_DP:   center (4.5,24.0), 6.0 x 1.2 mm.
Pad 2 USB_DM:   center (4.5,26.0), 6.0 x 1.2 mm.
Pad 1 USB_VBUS: center (4.5,28.5), 7.0 x 1.4 mm.
Top-to-bottom order, insertion tip facing left: GND, D+, D-, VBUS.
No silkscreen or zone fill is permitted on the 12 x 12 mm mating tongue.
The specified stackup remains 1.6 mm; confirm retention in the target port.

Important assembly notes
------------------------
* BT1 is a bottom-side Keystone 1058 low-profile CR2032 holder. Pad 1 is
  VBAT (+); pad 2 is GND (-). Insert the cell through the holder opening.
* U5 (USBLC6-2SC6) is mounted on the bottom side.
* DS1 is mounted on headers above the board. Configure the Adafruit OLED for I2C.
  OLED pin 3 (DC/SA0) and pin 5 (CS) are strapped low; pin 6 (3V3 output) is NC.
  The carrier PCB intentionally has no OLED corner mounting drills; the module
  is retained by the 8-pin header.
* U4 uses the TI-recommended PCA9306 translation circuit: pins 7 and 8 share
  I2C_BIAS, filtered by C5=100 pF and pulled to +5 V by R8=200 kOhm.
* GPIO1 drives D1 through R5=1 kOhm; the LED is MCU controlled and active high.
* TP1.1 is BOOT/GPIO0 and TP1.2 is GND. Bridge them while pulsing SW5/EN to
  enter ROM recovery mode; remove the bridge after ROM USB enumeration.
* Confirm the exact Keystone 1058/1058TR ordering and polarity marking against
  the procured part before loading cells.
* Program the ESP32-S3 over the native USB D+/D- connection. The USB-Serial/
  JTAG interface supports automatic download mode; GPIO0 is held high by R7=10k.
* SW5 is a recessed 4.2 x 3.2 mm, 2.5 mm tall SMD tactile switch at
  (104.0, 13.5) on the front side, wired only from EN to GND. It is not
  finger-accessible: provide
  a 1.0-1.2 mm pinhole in the enclosure lid directly above it and use a needle
  or SIM-ejector tool to reset the module.
* The project-local U1 STEP model is an assembly-envelope approximation, not
  vendor-controlled CAD; do not use it to machine mating parts.
"""
    (FAB / "MANUFACTURING_NOTES.txt").write_text(notes)

    archive = FAB / "VaultKey_USB_Gerbers_and_Drill.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in (GERBERS, DRILL):
            for path in sorted(folder.glob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(FAB))
        zf.write(FAB / "MANUFACTURING_NOTES.txt", "MANUFACTURING_NOTES.txt")

    full_package = FAB / "VaultKey_USB_Manufacturing_Package.zip"
    with zipfile.ZipFile(full_package, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in (GERBERS, DRILL, ASSEMBLY, REPORTS, MODELS):
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(FAB))
        zf.write(FAB / "MANUFACTURING_NOTES.txt", "MANUFACTURING_NOTES.txt")
        zf.write(FAB / "ROUTING_SESSION_NOTE.txt", "ROUTING_SESSION_NOTE.txt")
        zf.write(ROOT / "README.md", "README.md")

    checksum_paths = []
    for folder in (GERBERS, DRILL, ASSEMBLY, REPORTS, MODELS):
        checksum_paths.extend(p for p in folder.rglob("*") if p.is_file())
    checksum_paths += [archive, full_package, FAB / "MANUFACTURING_NOTES.txt",
                       FAB / "ROUTING_SESSION_NOTE.txt"]
    rows = []
    for path in sorted(set(checksum_paths)):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {path.relative_to(ROOT)}")
    (FAB / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n")


def main() -> None:
    mkdirs()
    validate_and_report()
    export_manufacturing()
    export_docs()
    write_notes_and_archive()
    print("Fabrication package complete:", FAB)


if __name__ == "__main__":
    main()
