#!/usr/bin/env python3
"""Verify the revision-D BOOT removal and recessed EN reset switch."""

from __future__ import annotations

import re
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / "VaultKey_USB.kicad_pcb"
REPORTS = ROOT / "fabrication" / "reports"
OUT = REPORTS / "reset_revision_verification.txt"

EXPECTED_FP = "SW_Push_1P1T_NO_Vertical_Wuerth_434133025816"
EXPECTED_AT = (104.0, 13.5)


def net_pads(board, net):
    out = set()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                out.add((fp.GetReference(), pad.GetNumber()))
    return out


def report_errors(path: Path) -> tuple[int, int]:
    text = path.read_text()
    if path.name.startswith("DRC"):
        m = re.search(r"Found (\d+) DRC violations", text)
        u = re.search(r"Found (\d+) unconnected pads", text)
        return int(m.group(1) if m else -1), int(u.group(1) if u else -1)
    m = re.search(r"ERC messages: (\d+)\s+Errors (\d+)\s+Warnings (\d+)", text)
    return (int(m.group(2)) if m else -1, int(m.group(3)) if m else -1)


def main() -> int:
    board = pcbnew.LoadBoard(str(PCB))
    lines = [
        "VaultKey USB revision-D BOOT/RESET verification",
        "==============================================",
    ]
    ok = True

    sw5 = board.FindFootprintByReference("SW5")
    sw6 = board.FindFootprintByReference("SW6")
    checks = []
    checks.append(("SW6 BOOT footprint absent", sw6 is None))
    checks.append(("SW5 present as Wuerth recessed switch",
                   sw5 is not None and sw5.GetFPIDAsString() == EXPECTED_FP))
    if sw5 is not None:
        at = (sw5.GetPosition().x / 1e6, sw5.GetPosition().y / 1e6)
        checks.append((f"SW5 at {EXPECTED_AT} mm front side",
                       at == EXPECTED_AT and sw5.GetLayer() == pcbnew.F_Cu))
    en = net_pads(board, "EN")
    boot = net_pads(board, "BOOT")
    gnd = net_pads(board, "GND")
    checks.append(("EN = module pin 3, R6, C7, SW5 (no GND short)",
                   en == {("C7", "1"), ("R6", "2"), ("SW5", "1"), ("U1", "3")}
                   and ("U1", "3") not in gnd))
    checks.append(("BOOT/GPIO0 = module pin 27 + R7 pull-up only (no switch)",
                   boot == {("R7", "2"), ("U1", "27")}
                   and ("U1", "27") not in gnd))
    checks.append(("R6 pad 1 is +3V3 (EN pull-up present)",
                   ("R6", "1") in net_pads(board, "+3V3")))
    checks.append(("C7 pad 2 is GND (EN RC present)",
                   ("C7", "2") in gnd))
    checks.append(("R7 pad 1 is +3V3 (GPIO0 pull-up present)",
                   ("R7", "1") in net_pads(board, "+3V3")))
    checks.append(("USB D- on U1 pin 13",
                   ("U1", "13") in net_pads(board, "USB_DM")))
    checks.append(("USB D+ on U1 pin 14",
                   ("U1", "14") in net_pads(board, "USB_DP")))
    checks.append(("PCB unconnected items = 0",
                   board.GetConnectivity().GetUnconnectedCount(False) == 0))

    drc_errors, drc_unconnected = report_errors(REPORTS / "DRC_report.txt")
    erc_errors, erc_warnings = report_errors(REPORTS / "ERC_report.txt")
    checks.append(("DRC violations = 0", drc_errors == 0))
    checks.append(("DRC unconnected pads = 0", drc_unconnected == 0))
    checks.append(("ERC errors = 0", erc_errors == 0))
    checks.append(("ERC warnings = 0", erc_warnings == 0))

    for label, passed in checks:
        ok = ok and passed
        lines.append(f"{'PASS' if passed else 'FAIL':4s}  {label}")

    lines += [
        "",
        f"EN net pads: {', '.join(f'{r}.{p}' for r, p in sorted(en))}",
        f"BOOT/GPIO0 net pads: {', '.join(f'{r}.{p}' for r, p in sorted(boot))}",
        "Recessed switch: Button_Switch_SMD:"
        "SW_Push_1P1T_NO_Vertical_Wuerth_434133025816",
        "Switch position: (104.000, 13.500) mm, front side",
        "Enclosure access: 1.0-1.2 mm pinhole centred above the switch",
        "Reset pin: ESP32-S3 EN (U1 pin 3), not a GPIO",
        "Normal boot: R7 holds GPIO0 high; R6/C7 release EN after USB power-up",
        "USB programming: native USB-Serial/JTAG automatic download mode",
        "",
        f"Overall result: {'PASS' if ok else 'FAIL'}",
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
