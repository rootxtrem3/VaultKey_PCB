#!/usr/bin/env python3
"""Import a FreeRouting session file, refill zones and save the board."""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "VaultKey_USB.kicad_pcb"
SES = ROOT / "fabrication" / "VaultKey_USB.ses"


def main() -> None:
    board = pcbnew.LoadBoard(str(BOARD))
    if not SES.exists():
        raise SystemExit(f"missing {SES}; run route.sh first")
    ok = pcbnew.ImportSpecctraSES(board, str(SES))
    print(f"import SES: {ok}")

    # Refill both ground pours after importing the tracks.
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

    # Tent every via created by the autorouter.
    for track in board.GetTracks():
        if track.GetClass() == "PCB_VIA":
            track.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
            track.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)

    pcbnew.SaveBoard(str(BOARD), board)

    unconnected = board.GetConnectivity().GetUnconnectedCount(False)
    print(f"saved {BOARD}")
    print(f"unconnected pads after import: {unconnected}")


if __name__ == "__main__":
    main()
