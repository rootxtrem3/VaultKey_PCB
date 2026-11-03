#!/usr/bin/env python3
"""Apply readable reference and functional silkscreen labels."""

from pathlib import Path

import pcbnew

import labels


ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    labels.apply(board)
    pcbnew.SaveBoard(str(BOARD), board)
    print("applied component and functional silkscreen labels")


if __name__ == "__main__":
    main()
