#!/usr/bin/env python3
"""Minimal S-expression reader/writer used by the schematic generator."""

from __future__ import annotations

import re


class Sym(str):
    """Symbol/atom that keeps quoting style."""

    quoted: bool = False


TOKEN_RE = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text: str):
    tokens = TOKEN_RE.findall(text)
    pos = 0

    def read():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            out = []
            while tokens[pos] != ")":
                out.append(read())
            pos += 1
            return out
        if tok == ")":
            raise ValueError("unexpected )")
        if tok.startswith('"'):
            return tok
        return tok

    return read()


def dump(node, indent: int = 0) -> str:
    pad = "  " * indent
    if not isinstance(node, list):
        return str(node)
    # Keep short leaf lists on one line.
    if all(not isinstance(c, list) for c in node):
        return "(" + " ".join(str(c) for c in node) + ")"
    head = node[0]
    simple_head = not isinstance(head, list)
    first = str(head) if simple_head else dump(head, indent)
    rest = node[1:]
    one_liner = all(not isinstance(c, list) for c in rest)
    if one_liner:
        return "(" + " ".join([first] + [str(c) for c in rest]) + ")"
    lines = ["(" + first]
    for child in rest:
        lines.append(pad + "  " + dump(child, indent + 1))
    lines.append(pad + ")")
    return "\n".join(lines)


def find_all(node, name: str):
    out = []
    if isinstance(node, list):
        if node and node[0] == name:
            out.append(node)
        for c in node:
            out.extend(find_all(c, name))
    return out


def find(node, name: str):
    """Return the first direct-or-nested child whose head is `name`."""
    if not isinstance(node, list):
        return None
    if node and node[0] == name:
        return node
    for child in node:
        hit = find(child, name)
        if hit is not None:
            return hit
    return None


def child(node, name: str):
    """Return the first *direct* child whose head is `name`."""
    if not isinstance(node, list):
        return None
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == name:
            return c
    return None


def unquote(v: str) -> str:
    if isinstance(v, str) and len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return v
