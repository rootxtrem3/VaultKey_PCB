#!/usr/bin/env python3
"""Build VaultKey_USB.kicad_sch from the canonical description in design.py.

The schematic is generated rather than drawn by hand so that it can never
drift away from the PCB netlist.  Every component pin gets a short wire stub
and a local net label; the resulting connectivity is identical to the track
list on the board.
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path

import sexpr
from design import PARTS, Part

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "VaultKey_USB.kicad_sch"
SYMBOL_DIR = Path("/usr/share/kicad/symbols")

PROJECT = "VaultKey_USB"

# ---------------------------------------------------------------------------
# Layout: reference -> (x, y, rotation)
# ---------------------------------------------------------------------------

LAYOUT = {
    # USB input / protection
    "J1": (52, 62, 0),
    "F1": (97, 46, 90),
    "C9": (97, 80, 0),
    "U5": (148, 62, 0),

    # 3V3 regulator and power LED
    "U3": (52, 142, 0),
    "C1": (92, 142, 0),
    "C2": (122, 142, 0),
    "R5": (155, 132, 90),
    "D1": (180, 132, 90),

    # ESP32-S3
    "U1": (268, 88, 0),
    "C3": (318, 44, 0),
    "C6": (318, 148, 0),

    # OLED
    "DS1": (392, 78, 0),
    "R1": (356, 120, 90),
    "R2": (376, 120, 90),
    "R3": (396, 120, 90),
    "R4": (416, 120, 90),

    # RTC
    "U2": (482, 78, 0),
    "X1": (452, 122, 90),
    "C4": (512, 122, 0),
    "C8": (552, 122, 0),
    "BT1": (552, 78, 0),

    # I2C level shifter
    "U4": (482, 196, 0),
    "C5": (522, 196, 0),
    "R8": (548, 196, 90),

    # Controls
    "SW1": (46, 252, 0),
    "SW2": (46, 288, 0),
    "SW3": (100, 252, 0),
    "SW4": (100, 288, 0),
    "SW5": (154, 252, 0),
    "R6": (196, 240, 90),
    "C7": (222, 240, 0),
    "R7": (196, 282, 90),

    # Mounting holes
    "H1": (470, 330, 0),
    "H2": (510, 330, 0),
    "H3": (550, 330, 0),
    "H4": (470, 366, 0),
}

CAPTIONS = [
    (20, 27, "USB INPUT, ESD PROTECTION AND POLYFUSE"),
    (20, 112, "5 V TO 3.3 V REGULATOR AND POWER LED"),
    (212, 27, "ESP32-S3-WROOM-1U MODULE"),
    (340, 27, "1.3 in 128x64 I2C OLED AND 3.3 V PULL-UPS"),
    (436, 27, "DS1307 REAL-TIME CLOCK AND CR2032 BACKUP"),
    (436, 166, "PCA9306 I2C LEVEL TRANSLATOR (3.3 V <-> 5 V)"),
    (20, 214, "USER CONTROLS AND RECESSED RESET (NEEDLE ACCESS)"),
    (436, 318, "MOUNTING HOLES"),
]

NOTES = [
    "VaultKey USB \u2013 ESP32-S3 hardware key with OLED UI and battery-backed RTC.",
    "All board nets are named; every pin is labelled so the schematic and the PCB share one netlist.",
    "Power budget: USB 5 V @ 0.5 A polyfuse, AMS1117-3.3 supplies the module and display logic.",
    "I2C: ESP32 + OLED use the 3.3 V side; PCA9306 translates to the 5 V DS1307. RTC keeps time on VBAT.",
    "BOOT button removed: R7 holds GPIO0 high, so the module boots from flash on every USB power-up.",
    "Firmware download uses the ESP32-S3 native USB-Serial/JTAG interface (automatic download mode).",
    "RESET: R6 (10k) pulls EN high, C7 (100nF) delays release; SW5 is a recessed needle-access switch to GND.",
]

# ---------------------------------------------------------------------------
# Custom symbols
# ---------------------------------------------------------------------------

CUSTOM = {
    "VaultKey:USB_A_Male_Edge": """(symbol "VaultKey:USB_A_Male_Edge"
      (pin_names (offset 1.016))
      (exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
      (property "Reference" "J" (at -2.54 9.525 0) (show_name no) (do_not_autoplace no)
        (effects (font (size 1.27 1.27))))
      (property "Value" "USB_A_Male_Edge" (at -2.54 -9.525 0) (show_name no) (do_not_autoplace no)
        (effects (font (size 1.27 1.27))))
      (property "Footprint" "VaultKey:VaultKey_USB_A_Male_PCB_Edge" (at 0 0 0) (show_name no)
        (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes)
        (effects (font (size 1.27 1.27))))
      (property "Description" "USB 2.0 Type-A male plug formed by the PCB tongue" (at 0 0 0)
        (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "USB_A_Male_Edge_0_1"
        (rectangle (start -3.81 7.62) (end 5.08 -8.89) (stroke (width 0.254) (type default))
          (fill (type background))))
      (symbol "USB_A_Male_Edge_1_1"
        (pin power_in line (at 7.62 2.54 180) (length 2.54)
          (name "VBUS" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin bidirectional line (at 7.62 0 180) (length 2.54)
          (name "D-" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27)))))
        (pin bidirectional line (at 7.62 -2.54 180) (length 2.54)
          (name "D+" (effects (font (size 1.27 1.27))))
          (number "3" (effects (font (size 1.27 1.27)))))
        (pin power_in line (at 7.62 -5.08 180) (length 2.54)
          (name "GND" (effects (font (size 1.27 1.27))))
          (number "4" (effects (font (size 1.27 1.27)))))))""",
    "VaultKey:OLED_SSD1306_I2C": """(symbol "VaultKey:OLED_SSD1306_I2C"
      (pin_names (offset 1.016))
      (exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes)
      (property "Reference" "DS" (at -3.81 12.7 0) (show_name no) (do_not_autoplace no)
        (effects (font (size 1.27 1.27))))
      (property "Value" "OLED_SSD1306_I2C" (at -3.81 -12.7 0) (show_name no) (do_not_autoplace no)
        (effects (font (size 1.27 1.27))))
      (property "Footprint" "Display:Adafruit_SSD1306" (at 0 0 0) (show_name no)
        (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes)
        (effects (font (size 1.27 1.27))))
      (property "Description" "Adafruit 128x64 I2C OLED breakout, 8 pin header" (at 0 0 0)
        (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "OLED_SSD1306_I2C_0_1"
        (rectangle (start -3.81 11.43) (end 5.08 -11.43) (stroke (width 0.254) (type default))
          (fill (type background))))
      (symbol "OLED_SSD1306_I2C_1_1"
        (pin bidirectional line (at 7.62 8.89 180) (length 2.54)
          (name "SDA" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin input line (at 7.62 6.35 180) (length 2.54)
          (name "SCL" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27)))))
        (pin input line (at 7.62 3.81 180) (length 2.54)
          (name "DC/SA0" (effects (font (size 1.27 1.27))))
          (number "3" (effects (font (size 1.27 1.27)))))
        (pin input line (at 7.62 1.27 180) (length 2.54)
          (name "RST" (effects (font (size 1.27 1.27))))
          (number "4" (effects (font (size 1.27 1.27)))))
        (pin input line (at 7.62 -1.27 180) (length 2.54)
          (name "CS" (effects (font (size 1.27 1.27))))
          (number "5" (effects (font (size 1.27 1.27)))))
        (pin power_out line (at 7.62 -3.81 180) (length 2.54)
          (name "3V3_OUT" (effects (font (size 1.27 1.27))))
          (number "6" (effects (font (size 1.27 1.27)))))
        (pin power_in line (at 7.62 -6.35 180) (length 2.54)
          (name "VIN" (effects (font (size 1.27 1.27))))
          (number "7" (effects (font (size 1.27 1.27)))))
        (pin power_in line (at 7.62 -8.89 180) (length 2.54)
          (name "GND" (effects (font (size 1.27 1.27))))
          (number "8" (effects (font (size 1.27 1.27)))))))""",
}

# lib_id -> (library nickname, symbol name)
SYMBOL_MAP = {
    "J1": "Connector:USB_A",
    "F1": "Device:Polyfuse",
    "C9": "Device:C", "C1": "Device:C", "C2": "Device:C", "C3": "Device:C",
    "C6": "Device:C", "C5": "Device:C", "C4": "Device:C", "C7": "Device:C",
    "C8": "Device:C",
    "U5": "Power_Protection:USBLC6-2SC6",
    "U3": "Regulator_Linear:AMS1117-3.3",
    "R5": "Device:R", "R6": "Device:R", "R7": "Device:R",
    "R8": "Device:R",
    "R1": "Device:R", "R2": "Device:R", "R3": "Device:R", "R4": "Device:R",
    "D1": "Device:LED",
    "U1": "RF_Module:ESP32-S3-WROOM-1",
    "DS1": "Connector_Generic:Conn_01x08",
    "U2": "Timer_RTC:DS1307+",
    "X1": "Device:Crystal",
    "BT1": "Device:Battery_Cell",
    "U4": "Interface:PCA9306",
    "SW1": "Switch:SW_Push", "SW2": "Switch:SW_Push", "SW3": "Switch:SW_Push",
    "SW4": "Switch:SW_Push", "SW5": "Switch:SW_Push",
    "H1": "Mechanical:MountingHole", "H2": "Mechanical:MountingHole",
    "H3": "Mechanical:MountingHole", "H4": "Mechanical:MountingHole",
}


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "vaultkey-usb/" + tag))


def snap(value: float) -> float:
    """Snap schematic connection points to KiCad's 50 mil grid."""
    return round(value / 1.27) * 1.27


# ---------------------------------------------------------------------------
# Symbol library handling
# ---------------------------------------------------------------------------

_cache: dict[str, dict] = {}


def load_symbol(lib_id: str):
    if lib_id in _cache:
        return _cache[lib_id]

    if lib_id in CUSTOM:
        node = sexpr.parse(CUSTOM[lib_id])
        _cache[lib_id] = {"node": node, "pins": pins_of(node)}
        return _cache[lib_id]

    nick, name = lib_id.split(":", 1)
    tree = sexpr.parse((SYMBOL_DIR / f"{nick}.kicad_sym").read_text())
    symbols = {sexpr.unquote(s[1]): s for s in tree[1:]
               if isinstance(s, list) and s[0] == "symbol"}

    node = symbols[name]
    parent_name = sexpr.child(node, "extends")
    if parent_name:
        parent = symbols[sexpr.unquote(parent_name[1])]
        base = sexpr.parse(sexpr.dump(parent))
        # take the derived part's properties, keep the parent's graphics
        keep = {"property", "pin_names", "pin_numbers", "power", "offset"}
        props = [c for c in node[1:] if isinstance(c, list) and c[0] == "property"]
        base = [c for c in base if not (isinstance(c, list) and c[0] == "property")]
        base.extend(props)
        base[1] = f'"{lib_id}"'
        for c in base:
            if isinstance(c, list) and c[0] == "symbol":
                sub = sexpr.unquote(c[1])
                suffix = sub.split("_", 1)[1] if "_" in sub else sub
                c[1] = f'"{name}_{suffix}"'
        node = base
    else:
        node = sexpr.parse(sexpr.dump(node))
        node[1] = f'"{lib_id}"'

    _cache[lib_id] = {"node": node, "pins": pins_of(node)}
    return _cache[lib_id]


def pins_of(node):
    out = []
    for p in sexpr.find_all(node, "pin"):
        at = sexpr.child(p, "at")
        length = sexpr.child(p, "length")
        num = sexpr.child(p, "number")
        nm = sexpr.child(p, "name")
        if at is None or num is None:
            continue
        out.append({
            "number": sexpr.unquote(num[1]),
            "name": sexpr.unquote(nm[1]) if nm else "",
            "type": p[1],
            "x": float(at[1]),
            "y": float(at[2]),
            "angle": int(float(at[3])) if len(at) > 3 else 0,
            "length": float(length[1]) if length else 2.54,
        })
    return out


def transform(px: float, py: float, rot: float):
    """Symbol coords (y up) -> sheet delta (y down) for a CCW rotation."""
    x, y = px, -py
    if rot == 0:
        return x, y
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    # screen-space counter-clockwise rotation
    return x * c + y * s, -x * s + y * c


def bbox_of(footprint_node, pins):
    xs, ys = [], []
    for p in pins:
        for d in (0.0, p["length"]):
            dx = d * math.cos(math.radians(p["angle"]))
            dy = d * math.sin(math.radians(p["angle"]))
            xs.append(p["x"] + dx)
            ys.append(p["y"] + dy)
    for kind in ("rectangle", "circle", "polyline", "arc"):
        for g in sexpr.find_all(footprint_node, kind):
            for key in ("start", "end", "center", "mid"):
                pt = sexpr.child(g, key)
                if pt is not None:
                    xs.append(float(pt[1]))
                    ys.append(float(pt[2]))
            pts = sexpr.child(g, "pts")
            if pts is not None:
                for xy in sexpr.find_all(pts, "xy"):
                    xs.append(float(xy[1]))
                    ys.append(float(xy[2]))
            rad = sexpr.child(g, "radius")
            if rad is not None:
                xs.extend([float(rad[1]), -float(rad[1])])
                ys.extend([float(rad[1]), -float(rad[1])])
    if not xs:
        xs, ys = [-2.54, 2.54], [-2.54, 2.54]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    sch = []

    write_local_libraries()

    lib_used = {}
    for part in PARTS:
        lib_id = SYMBOL_MAP[part.ref]
        lib_used[lib_id] = load_symbol(lib_id)
    pwr = load_symbol("power:PWR_FLAG")
    lib_used["power:PWR_FLAG"] = pwr

    out = [
        '(kicad_sch',
        '  (version 20260306)',
        '  (generator "eeschema")',
        '  (generator_version "10.0")',
        f'  (uuid "{uid("root")}")',
        '  (paper "A2")',
        '  (title_block',
        '    (title "VaultKey USB - ESP32-S3 Hardware Key")',
        '    (date "2026-11-11")',
        '    (rev "D")',
        '    (company "VaultKey")',
        '    (comment 1 "112.5 x 50.0 mm USB-A dongle, 2-layer 1.6 mm FR4")',
        '    (comment 2 "Generated from generator/design.py")',
        '  )',
        '  (lib_symbols',
    ]
    for lib_id, data in lib_used.items():
        out.append(indent(sexpr.dump(data["node"]), 2))
    out.append('  )')

    # graphical captions / notes -------------------------------------------
    for x, y, text in CAPTIONS:
        out.append(
            f'  (text "{escape(text)}" (exclude_from_sim no) (at {x} {y} 0)\n'
            f'    (effects (font (size 1.8 1.8) (thickness 0.3) bold) (justify left bottom))\n'
            f'    (uuid "{uid("text/" + text)}")\n  )'
        )
    for i, text in enumerate(NOTES):
        out.append(
            f'  (text "{escape(text)}" (exclude_from_sim no) (at 24 {372 + i * 4} 0)\n'
            f'    (effects (font (size 1.27 1.27)) (justify left bottom))\n'
            f'    (uuid "{uid(f"note/{i}")}")\n  )'
        )

    # components ------------------------------------------------------------
    boxes = []
    for part in PARTS:
        lib_id = SYMBOL_MAP[part.ref]
        data = lib_used[lib_id]
        x, y, rot = LAYOUT[part.ref]
        x, y = snap(x), snap(y)
        node_pins = data["pins"]

        # property positions from the body box
        bx0, by0, bx1, by1 = bbox_of(data["node"], node_pins)
        dx0, dy0 = transform(bx0, by0, rot)
        dx1, dy1 = transform(bx1, by1, rot)
        top = y + min(dy0, dy1)
        bottom = y + max(dy0, dy1)

        out.append(f'  (symbol')
        out.append(f'    (lib_id "{lib_id}")')
        out.append(f'    (at {x} {y} {rot})')
        out.append('    (unit 1)')
        out.append('    (body_style 1)')
        out.append('    (exclude_from_sim no)')
        out.append(f'    (in_bom {"no" if part.ref.startswith("H") else "yes"})')
        out.append('    (on_board yes)')
        out.append('    (in_pos_files yes)')
        out.append('    (dnp no)')
        out.append(f'    (uuid "{uid("sym/" + part.ref)}")')
        out.append(f'    (property "Reference" "{part.ref}" (at {x:.3f} {top - 2.2:.3f} 0)')
        out.append('      (effects (font (size 1.27 1.27)))')
        out.append('    )')
        out.append(f'    (property "Value" "{escape(part.value)}" (at {x:.3f} {bottom + 3.0:.3f} 0)')
        out.append('      (effects (font (size 1.27 1.27)))')
        out.append('    )')
        out.append(f'    (property "Footprint" "{part.lib}:{part.fp}"')
        out.append(f'      (at {x:.3f} {y:.3f} {rot}) (hide yes)')
        out.append('      (effects (font (size 1.27 1.27)))')
        out.append('    )')
        out.append(f'    (property "Datasheet" "" (at {x:.3f} {y:.3f} {rot}) (hide yes)')
        out.append('      (effects (font (size 1.27 1.27)))')
        out.append('    )')
        out.append(f'    (property "Description" "{escape(part.description)}"')
        out.append(f'      (at {x:.3f} {y:.3f} {rot}) (hide yes)')
        out.append('      (effects (font (size 1.27 1.27)))')
        out.append('    )')
        for p in node_pins:
            out.append(f'    (pin "{p["number"]}" (uuid "{uid(f"pin/{part.ref}/{p["number"]}")}"))')
        out.append('    (instances')
        out.append(f'      (project "{PROJECT}"')
        out.append(f'        (path "/{uid("root")}"')
        out.append(f'          (reference "{part.ref}") (unit 1)')
        out.append('        )')
        out.append('      )')
        out.append('    )')
        out.append('  )')

        boxes.append((part.ref, x + min(dx0, dx1), top, x + max(dx0, dx1), bottom))

        # wires + labels + no-connects
        drawn = set()
        for p in node_pins:
            px, py = transform(p["x"], p["y"], rot)
            sx, sy = x + px, y + py
            if (round(sx, 3), round(sy, 3)) in drawn:
                continue
            drawn.add((round(sx, 3), round(sy, 3)))
            net = part.pads.get(p["number"])
            if net is None:
                out.append(f'  (no_connect (at {sx:.4f} {sy:.4f})')
                out.append(f'    (uuid "{uid(f"nc/{part.ref}/{p["number"]}")}")')
                out.append('  )')
                continue
            # outward direction in sheet coords
            ox, oy = transform(
                math.cos(math.radians(p["angle"])) * 1.0,
                math.sin(math.radians(p["angle"])) * 1.0, rot)
            ox, oy = -ox, -oy
            ex, ey = sx + ox * STUB, sy + oy * STUB
            out.append(f'  (wire (pts (xy {sx:.4f} {sy:.4f}) (xy {ex:.4f} {ey:.4f}))')
            out.append('    (stroke (width 0) (type default))')
            out.append(f'    (uuid "{uid(f"wire/{part.ref}/{p["number"]}")}")')
            out.append('  )')
            angle = 0
            if abs(ox) > abs(oy):
                angle = 0 if ox > 0 else 180
            else:
                angle = 90 if oy < 0 else 270
            out.append(f'  (global_label "{net}" (shape bidirectional) '
                       f'(at {ex:.4f} {ey:.4f} {angle}) (fields_autoplaced)')
            out.append('    (effects (font (size 1.27 1.27)) (justify left))')
            out.append(f'    (uuid "{uid(f"lbl/{part.ref}/{p["number"]}")}")')
            out.append(f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                       f'(at {ex:.4f} {ey:.4f} 0)')
            out.append('      (effects (font (size 1.27 1.27)) (hide yes))')
            out.append('    )')
            out.append('  )')

    # PWR_FLAG markers ------------------------------------------------------
    for i, net in enumerate(("GND", "USB_VBUS", "+5V", "VBAT", "I2C_BIAS")):
        px, py = snap(270 + i * 30), snap(340)
        out.append('  (symbol')
        out.append('    (lib_id "power:PWR_FLAG")')
        out.append(f'    (at {px} {py} 0)')
        out.append('    (unit 1) (body_style 1) (exclude_from_sim no) (in_bom no)')
        out.append('    (on_board no) (in_pos_files no) (dnp no)')
        out.append(f'    (uuid "{uid(f"pwr/{net}")}")')
        out.append(f'    (property "Reference" "#FLG0{i + 1}" (at {px} {py - 3.6} 0) (hide yes)')
        out.append('      (effects (font (size 1.27 1.27))))')
        out.append(f'    (property "Value" "PWR_FLAG" (at {px} {py + 4.5} 0) (hide yes)')
        out.append('      (effects (font (size 1.27 1.27))))')
        out.append(f'    (property "Footprint" "" (at {px} {py} 0) (hide yes)')
        out.append('      (effects (font (size 1.27 1.27))))')
        out.append(f'    (property "Datasheet" "" (at {px} {py} 0) (hide yes)')
        out.append('      (effects (font (size 1.27 1.27))))')
        out.append(f'    (pin "1" (uuid "{uid(f"pw pin/{net}")}"))')
        out.append('    (instances')
        out.append(f'      (project "{PROJECT}"')
        out.append(f'        (path "/{uid("root")}"')
        out.append(f'          (reference "#FLG0{i + 1}") (unit 1))))')
        out.append('  )')
        # wire down from the flag pin and a label
        out.append(f'  (wire (pts (xy {px} {py}) (xy {px} {py + 5.08}))')
        out.append('    (stroke (width 0) (type default))')
        out.append(f'    (uuid "{uid(f"pwrwire/{net}")}")')
        out.append('  )')
        out.append(f'  (global_label "{net}" (shape bidirectional) '
                   f'(at {px} {py + 5.08} 270) (fields_autoplaced)')
        out.append('    (effects (font (size 1.27 1.27)) (justify left))')
        out.append(f'    (uuid "{uid(f"pwrlbl/{net}")}")')
        out.append(f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                   f'(at {px} {py + 5.08} 0)')
        out.append('      (effects (font (size 1.27 1.27)) (hide yes))')
        out.append('    )')
        out.append('  )')

    out.append('  (sheet_instances')
    out.append('    (path "/" (page "1"))')
    out.append('  )')
    out.append('  (embedded_fonts no)')
    out.append(')')

    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT} ({len(PARTS)} parts)")
    return boxes


STUB = 3.81


def write_local_libraries() -> None:
    """Write the project-local footprint table used by PCB and ERC."""
    # All schematic symbols now come from the KiCad 10 standard libraries.
    # Remove stale generated symbol-table files from older generator passes.
    (ROOT / "sym-lib-table").unlink(missing_ok=True)
    (ROOT / "lib" / "VaultKey.kicad_sym").unlink(missing_ok=True)
    (ROOT / "fp-lib-table").write_text(
        '(fp_lib_table\n'
        '  (lib (name "VaultKey")(type "KiCad")'
        '(uri "${KIPRJMOD}/lib/VaultKey.pretty")'
        '(options "")(descr "VaultKey local footprints"))\n)\n'
    )


def indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in text.splitlines())


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


if __name__ == "__main__":
    build()
