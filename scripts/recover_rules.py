"""Reverse-engineer Connexion board geometry + scoring from a finished game log.

Approach:
  - Labels are (col a..f, row 1..6, sign +/-) -> 72 possible, 64 used in the log.
  - Hypothesis: label maps linearly into hex axial coords:
        pos(cx, ry, s) = cx*A + ry*B + s*C   (s = 0 for '+', 1 for '-')
    with A, B small lattice vectors and C one of the 6 hex unit directions.
  - For each injective, connected candidate, build the final board and test
    scoring functions:  FIRST scores on patterns (digit), SECOND on colors
    (letter).  Keep candidates reproducing SCOREFIRST=196, SCORESECOND=304.
"""

import sys
from collections import defaultdict
from itertools import product

LOG = r"C:\Users\tnest\Desktop\Connexion\Log\WebSiteBot\2026-06-11_sampleai_p1human_196-304.log"

HEX_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def parse_log(path):
    init, moves, scores = None, [], {}
    for line in open(path, encoding="utf-8"):
        t = line.split()
        if not t:
            continue
        if t[0] == "INIT":
            init = t[1:]
        elif t[0] in ("FIRST", "SECOND"):
            side, cell, placed, drawn, flag = t[0], t[1], t[2], t[3], t[4]
            moves.append((side, cell, placed, drawn, flag))
        elif t[0] == "SCOREFIRST":
            scores["FIRST"] = int(t[1])
        elif t[0] == "SCORESECOND":
            scores["SECOND"] = int(t[1])
    return init, moves, scores


def verify_hands(init, moves):
    """Check: first 5 INIT tiles = FIRST hand, last 5 = SECOND hand,
    each move plays from hand then draws the listed tile."""
    hands = {"FIRST": list(init[:5]), "SECOND": list(init[5:])}
    for i, (side, cell, placed, drawn, _) in enumerate(moves):
        if placed not in hands[side]:
            return False, f"move {i}: {side} played {placed} not in hand {hands[side]}"
        hands[side].remove(placed)
        if drawn != "X0":
            hands[side].append(drawn)
    return True, {s: h for s, h in hands.items()}


def label_key(cell):
    cx = ord(cell[0]) - ord("a")
    ry = int(cell[1]) - 1
    s = 0 if cell[2] == "+" else 1
    return cx, ry, s


def components(cells, attr_of, adj):
    """Connected components among `cells` grouped by equal attribute."""
    seen, comps = set(), []
    for c in cells:
        if c in seen:
            continue
        a = attr_of[c]
        stack, comp = [c], []
        seen.add(c)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj[u]:
                if v in cells and v not in seen and attr_of[v] == a:
                    seen.add(v)
                    stack.append(v)
        comps.append((a, len(comp)))
    return comps


def same_attr_edges(cells, attr_of, adj):
    e = 0
    for c in cells:
        for v in adj[c]:
            if v in cells and attr_of[v] == attr_of[c]:
                e += 1
    return e // 2


SCORERS = {
    "sum n^2": lambda sizes: sum(n * n for n in sizes),
    "sum n(n-1)": lambda sizes: sum(n * (n - 1) for n in sizes),
    "sum n(n-1)/2": lambda sizes: sum(n * (n - 1) // 2 for n in sizes),
    "sum n(n+1)/2": lambda sizes: sum(n * (n + 1) // 2 for n in sizes),
    "sum (n-1)^2": lambda sizes: sum((n - 1) ** 2 for n in sizes),
    "sum n^2, n>=2": lambda sizes: sum(n * n for n in sizes if n >= 2),
    "sum 2n(n-1)": lambda sizes: sum(2 * n * (n - 1) for n in sizes),
}


def main():
    init, moves, scores = parse_log(LOG)
    ok, hands = verify_hands(init, moves)
    print("hand model consistent:", ok, "| final hands:", hands)
    census = defaultdict(int)
    for _, _, placed, _, _ in moves:
        census[placed] += 1
    print("tile census (16 types x 4 copies expected):",
          sorted(census.items()), "total", sum(census.values()))

    placed_label = {}
    for side, cell, placed, drawn, _ in moves:
        k = label_key(cell)
        assert k not in placed_label, f"cell reused: {cell}"
        placed_label[k] = (placed, side)

    all_labels = [(cx, ry, s) for cx in range(6) for ry in range(6) for s in (0, 1)]
    missing = [l for l in all_labels if l not in placed_label]
    print("missing labels (8 expected):",
          [f"{chr(97+cx)}{ry+1}{'+' if s==0 else '-'}" for cx, ry, s in missing])

    target_first, target_second = scores["FIRST"], scores["SECOND"]
    rng = range(-3, 4)
    vecs = [(a, b) for a in rng for b in rng if (a, b) != (0, 0)]
    matches = []
    seen_signatures = set()

    for A, B, C in product(vecs, vecs, HEX_DIRS):
        pos = {}
        bad = False
        for l in all_labels:
            p = (l[0] * A[0] + l[1] * B[0] + l[2] * C[0],
                 l[0] * A[1] + l[1] * B[1] + l[2] * C[1])
            if p in pos:
                bad = True
                break
            pos[p] = l
        if bad:
            continue

        cell_of = {l: p for p, l in pos.items()}
        placed_cells = {cell_of[l] for l in placed_label}
        adj = {c: [(c[0] + d[0], c[1] + d[1]) for d in HEX_DIRS] for c in placed_cells}

        # placed cells must form one connected blob
        start = next(iter(placed_cells))
        stack, seen = [start], {start}
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v in placed_cells and v not in seen:
                    seen.add(v)
                    stack.append(v)
        if len(seen) != len(placed_cells):
            continue

        color = {cell_of[l]: t[0] for l, (t, _) in placed_label.items()}
        pat = {cell_of[l]: t[1] for l, (t, _) in placed_label.items()}

        # adjacency signature dedupe (graph on labels)
        lab_adj = []
        for l, p in cell_of.items():
            if l not in placed_label:
                continue
            for d in HEX_DIRS:
                q = (p[0] + d[0], p[1] + d[1])
                if q in pos and pos[q] in placed_label:
                    lab_adj.append(tuple(sorted((l, pos[q]))))
        sig = frozenset(lab_adj)
        is_new = sig not in seen_signatures
        seen_signatures.add(sig)

        pat_sizes = [n for _, n in components(placed_cells, pat, adj)]
        col_sizes = [n for _, n in components(placed_cells, color, adj)]
        e_pat = same_attr_edges(placed_cells, pat, adj)
        e_col = same_attr_edges(placed_cells, color, adj)

        for name, f in SCORERS.items():
            if f(pat_sizes) == target_first and f(col_sizes) == target_second:
                matches.append((name, A, B, C, sig, sorted(pat_sizes, reverse=True),
                                sorted(col_sizes, reverse=True)))
                if is_new:
                    print(f"MATCH {name}: A={A} B={B} C={C} "
                          f"pat={sorted(pat_sizes, reverse=True)} col={sorted(col_sizes, reverse=True)}")
        for ename, ev in (("edges", (e_pat, e_col)), ("2*edges", (2 * e_pat, 2 * e_col))):
            if ev == (target_first, target_second):
                matches.append((ename, A, B, C, sig, e_pat, e_col))
                if is_new:
                    print(f"MATCH {ename}: A={A} B={B} C={C} e_pat={e_pat} e_col={e_col}")

    print(f"\ntotal raw matches: {len(matches)}; distinct adjacency signatures tried: {len(seen_signatures)}")
    by_sig = defaultdict(set)
    for m in matches:
        by_sig[m[4]].add(m[0])
    print(f"distinct matching adjacency structures: {len(by_sig)}")


if __name__ == "__main__":
    main()
