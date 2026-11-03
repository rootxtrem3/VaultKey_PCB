#!/usr/bin/env python3
"""Generate project-local footprint variants from KiCad 10 libraries."""

from pathlib import Path

import sexpr


ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path("/usr/share/kicad/footprints/Display.pretty/Adafruit_SSD1306.kicad_mod")
OUTPUT = ROOT / "lib" / "VaultKey.pretty" / "Adafruit_SSD1306_NoMountingHoles.kicad_mod"


def main() -> None:
    fp = sexpr.parse(SOURCE.read_text())
    fp[1] = '"Adafruit_SSD1306_NoMountingHoles"'
    cleaned = fp[:2]
    removed_pads = 0
    for item in fp[2:]:
        if isinstance(item, list) and item:
            if item[0] == "pad" and sexpr.unquote(item[1]) == "":
                removed_pads += 1
                continue
            layer = sexpr.child(item, "layer")
            if layer and sexpr.unquote(layer[1]) in ("F.CrtYd", "B.CrtYd"):
                continue
        cleaned.append(item)
    if removed_pads != 4:
        raise RuntimeError(f"expected four OLED corner pads, removed {removed_pads}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(sexpr.dump(cleaned) + "\n")
    print(f"wrote {OUTPUT} without the four OLED corner drills")


if __name__ == "__main__":
    main()
