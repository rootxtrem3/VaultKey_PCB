#!/usr/bin/env python3
"""Create local STEP models missing from the distro KiCad 3D package.

Both models are dimensionally representative assembly envelopes, not
vendor-controlled CAD, and must not be used to machine mating parts.
Run with FreeCADCmd, not the system Python interpreter.
"""

from pathlib import Path

import FreeCAD as App
import Import
import Part


try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:  # FreeCADCmd -c executes without defining __file__.
    ROOT = Path.cwd()
OUT = ROOT / "lib" / "VaultKey.3dshapes"
OUT.mkdir(parents=True, exist_ok=True)


def feature(doc, name, shape, color):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
    return obj


def esp32_model():
    doc = App.newDocument("ESP32_S3_WROOM_1U")
    objs = []
    # Module substrate: datasheet/fab outline 18.0 x 19.2 mm.
    objs.append(feature(doc, "Module_PCB",
                        Part.makeBox(18.0, 19.2, 0.80,
                                     App.Vector(-9.0, -9.6, 0.0)),
                        (0.08, 0.22, 0.12)))
    # Metal RF can and the U.FL/I-PEX antenna connector envelope.
    objs.append(feature(doc, "RF_Shield",
                        Part.makeBox(15.8, 13.4, 1.55,
                                     App.Vector(-7.9, -4.2, 0.80)),
                        (0.72, 0.74, 0.75)))
    objs.append(feature(doc, "UFL_Base",
                        Part.makeBox(2.6, 2.6, 0.75,
                                     # STEP-model Y is opposite KiCad's
                                     # footprint-local Y direction.
                                     App.Vector(4.7, 5.84, 0.80)),
                        (0.78, 0.74, 0.42)))
    objs.append(feature(doc, "UFL_Ring",
                        Part.makeCylinder(0.90, 1.20,
                                          App.Vector(6.0, 7.14, 1.55)),
                        (0.82, 0.78, 0.48)))
    Import.export(objs, str(OUT / "ESP32-S3-WROOM-1U.step"))
    App.closeDocument(doc.Name)


def reset_switch_model():
    """Wuerth 434133025816: 4.2 x 3.2 mm body, 2.5 mm total height."""
    doc = App.newDocument("Wuerth_434133025816")
    objs = []
    # Frame/body envelope, seated on the board.
    objs.append(feature(doc, "Switch_Body",
                        Part.makeBox(4.2, 3.2, 1.5,
                                     App.Vector(-2.1, -1.6, 0.0)),
                        (0.10, 0.10, 0.10)))
    # Oval actuator, 1.7 x 2.2 mm, bringing the total height to 2.5 mm.
    objs.append(feature(doc, "Actuator",
                        Part.makeBox(1.7, 2.2, 1.0,
                                     App.Vector(-0.85, -1.1, 1.5)),
                        (0.16, 0.16, 0.16)))
    Import.export(objs, str(OUT / "SW_Push_1P1T_NO_Vertical_Wuerth_434133025816.step"))
    App.closeDocument(doc.Name)


esp32_model()
reset_switch_model()
print(f"wrote local assembly-envelope STEP models to {OUT}")
