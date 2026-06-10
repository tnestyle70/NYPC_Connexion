"""Render the two surviving geometry candidates as ASCII to compare with the
website screenshot (last move f6- should sit top-right; 8 holes spread evenly)."""

from recover_rules import parse_log, label_key, LOG, HEX_DIRS

CANDS = {
    "cand1": ((-2, 0), (-1, 1), (-1, 0)),
    "cand2": ((-2, 1), (-1, -1), (1, 0)),
}


def build(A, B, C):
    pos = {}
    for cx in range(6):
        for ry in range(6):
            for s in (0, 1):
                p = (cx * A[0] + ry * B[0] + s * C[0],
                     cx * A[1] + ry * B[1] + s * C[1])
                pos[(cx, ry, s)] = p
    return pos


def render(name, A, B, C, placed):
    pos = build(A, B, C)
    pts = {}
    for l, p in pos.items():
        cell = f"{chr(97+l[0])}{l[1]+1}{'+' if l[2]==0 else '-'}"
        if l in placed:
            pts[p] = cell
        else:
            pts[p] = "(" + cell + ")"  # hole
    # axial -> staggered pixel rows (pointy-top): col = 2*q + r, row = r
    rows = {}
    for (q, r), txt in pts.items():
        rows.setdefault(r, []).append((2 * q + r, txt))
    print(f"\n=== {name}: A={A} B={B} C={C} ===")
    minx = min(x for r in rows.values() for x, _ in r)
    for r in sorted(rows):
        line = {}
        for x, txt in rows[r]:
            line[x - minx] = txt
        width = max(line) + 1
        out = ""
        for x in range(width):
            out += f"{line.get(x, ''):<6}" if x in line else " " * 6
        print(out.rstrip())


def main():
    init, moves, scores = parse_log(LOG)
    placed = {label_key(c) for _, c, _, _, _ in moves}
    for name, (A, B, C) in CANDS.items():
        render(name, A, B, C, placed)


if __name__ == "__main__":
    main()
