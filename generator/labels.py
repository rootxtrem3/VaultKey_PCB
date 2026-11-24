"""Silkscreen reference and functional-label placement."""

from __future__ import annotations

import pcbnew


# Global PCB coordinates in mm.  References are deliberately beside, rather
# than beneath, their components so they remain useful during assembly.
REFERENCE_LABELS = {
    "J1": (10.2, 18.0, 0),
    "F1": (14.5, 7.4, 0),
    "C9": (18.0, 7.4, 0),
    "U5": (21.0, 25.0, 0),
    "U3": (27.0, 12.0, 0),
    "C1": (21.3, 6.0, 0),
    "C2": (33.0, 3.8, 0),
    "C3": (79.0, 44.6, 0),
    "C6": (50.0, 48.0, 0),
    "C8": (36.0, 8.4, 0),
    "R5": (47.5, 5.5, 0),
    "D1": (51.5, 5.5, 0),
    "U1": (61.0, 48.5, 0),
    "DS1": (50.3, 38.0, 90),
    "U2": (70.0, 13.8, 0),
    "X1": (58.7, 7.0, 0),
    "BT1": (81.5, 18.0, 90),
    "U4": (77.5, 10.3, 0),
    "C5": (82.0, 4.2, 0),
    "C4": (77.2, 3.0, 0),
    "R1": (65.0, 15.1, 0),
    "R2": (67.5, 15.1, 0),
    "R3": (70.0, 15.1, 0),
    "R4": (72.5, 15.1, 0),
    "R8": (86.5, 5.8, 0),
    "SW1": (86.5, 16.4, 0),
    "SW2": (87.0, 38.0, 0),
    "SW3": (95.0, 26.5, 0),
    "SW4": (77.5, 26.5, 0),
    "SW5": (104.0, 16.6, 0),
    "R6": (97.0, 5.8, 0),
    "C7": (103.0, 5.8, 0),
    "R7": (96.5, 39.5, 0),
    "TP1": (105.3, 33.8, 0),
    "H1": (19.2, 3.5, 0),
    "H2": (13.0, 43.5, 0),
    "H3": (104.7, 3.5, 0),
    "H4": (103.5, 46.0, 0),
}


# (text, x, y, angle, side, size)
FUNCTION_LABELS = [
    ("UP", 86.5, 17.7, 0, "F", 0.9),
    ("DOWN", 87.0, 39.3, 0, "F", 0.9),
    ("SELECT", 95.0, 27.8, 0, "F", 0.9),
    ("BACK", 77.5, 27.8, 0, "F", 0.9),
    ("RESET", 104.0, 17.7, 0, "F", 0.8),
    ("BOOT", 104.0, 38.0, 0, "F", 0.8),
    ("GND", 106.54, 38.0, 0, "F", 0.8),
    ("OLED", 50.3, 42.5, 90, "F", 0.9),
    ("RTC", 73.0, 13.8, 0, "F", 0.9),
    ("ESP32-S3", 67.0, 48.5, 0, "F", 0.9),
    ("I2C SHIFT", 78.0, 11.6, 0, "F", 0.8),
    ("3V3 REG", 27.0, 13.3, 0, "F", 0.8),
    ("RTC BATTERY", 96.0, 36.2, 0, "B", 1.0),
    ("USB ESD", 17.0, 28.5, 0, "B", 0.9),
]


def apply(board: pcbnew.BOARD) -> None:
    for ref, (x, y, angle) in REFERENCE_LABELS.items():
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            raise RuntimeError(f"missing footprint for silk label: {ref}")
        text = fp.Reference()
        back = fp.GetLayer() == pcbnew.B_Cu
        text.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
        text.SetMirrored(back)
        text.SetVisible(True)
        text.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        text.SetTextAngleDegrees(angle)
        text.SetTextSize(pcbnew.VECTOR2I_MM(0.8, 0.8))
        text.SetTextThickness(pcbnew.FromMM(0.12))
        text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)

    functional_names = {entry[0] for entry in FUNCTION_LABELS}
    obsolete_names = set()
    for item in list(board.GetDrawings()):
        if (item.GetClass() == "PCB_TEXT" and
                item.GetText() in functional_names | obsolete_names):
            board.Remove(item)

    for value, x, y, angle, side, size in FUNCTION_LABELS:
        text = pcbnew.PCB_TEXT(board)
        text.SetText(value)
        back = side == "B"
        text.SetLayer(pcbnew.B_SilkS if back else pcbnew.F_SilkS)
        text.SetMirrored(back)
        text.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        text.SetTextAngleDegrees(angle)
        text.SetTextSize(pcbnew.VECTOR2I_MM(size, size))
        text.SetTextThickness(pcbnew.FromMM(0.14))
        text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        board.Add(text)
