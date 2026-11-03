#!/usr/bin/env python3
"""Point U1 and SW5 at their project-local assembly-envelope STEP models."""

from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"
MODELS = {
    "U1": "${KIPRJMOD}/lib/VaultKey.3dshapes/ESP32-S3-WROOM-1U.step",
    "SW5": "${KIPRJMOD}/lib/VaultKey.3dshapes/"
           "SW_Push_1P1T_NO_Vertical_Wuerth_434133025816.step",
}


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    for ref, path in MODELS.items():
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            raise RuntimeError(f"missing footprint {ref}")
        fp.Models().clear()
        model = pcbnew.FP_3DMODEL()
        model.m_Filename = path
        fp.Add3DModel(model)
    pcbnew.SaveBoard(str(BOARD), board)
    print("applied project-local U1 and SW5 STEP models")


if __name__ == "__main__":
    main()
