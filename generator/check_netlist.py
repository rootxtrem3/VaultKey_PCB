#!/usr/bin/env python3
"""Compare the schematic netlist against the routed board's pad nets."""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew
import sexpr

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / "VaultKey_USB.kicad_pcb"
NET = (Path(sys.argv[1]) if len(sys.argv) > 1
       else Path("/tmp/opencode/sch_net.net"))


def pcb_pairs():
    board = pcbnew.LoadBoard(str(PCB))
    out = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            name = pad.GetNetname()
            if name:
                out[(ref, pad.GetNumber())] = name
    return out


def sch_pairs():
    tree = sexpr.parse(NET.read_text())
    nets = sexpr.find_all(tree, "nets")
    out = {}
    for block in nets:
        for net in block[1:]:
            if not isinstance(net, list) or net[0] != "net":
                continue
            name = None
            for c in net[1:]:
                if isinstance(c, list) and c[0] == "name":
                    name = sexpr.unquote(c[1])
            if name and name.startswith("/"):
                name = name[1:]
            if name and name.startswith("unconnected-"):
                name = None
            for c in net[1:]:
                if isinstance(c, list) and c[0] == "node":
                    ref = pin = None
                    for d in c[1:]:
                        if isinstance(d, list) and d[0] == "ref":
                            ref = sexpr.unquote(d[1])
                        if isinstance(d, list) and d[0] == "pin":
                            pin = sexpr.unquote(d[1])
                    if name is not None:
                        out[(ref, pin)] = name
    return out


def main():
    p, s = pcb_pairs(), sch_pairs()
    bad = 0
    for key in sorted(set(p) | set(s)):
        a, b = p.get(key), s.get(key)
        if a != b:
            print(f"MISMATCH {key}: pcb={a} sch={b}")
            bad += 1
    print(f"{len(p)} pcb pads, {len(s)} sch pins, {bad} mismatches")
    # every schematic net should have at least two pins
    single = [k for k in s if all(x == k for x in [k])]
    nets = {}
    for (ref, pin), name in s.items():
        nets.setdefault(name, []).append((ref, pin))
    for name, pins in sorted(nets.items()):
        if len(pins) < 2:
            print(f"single-pin net {name}: {pins}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
