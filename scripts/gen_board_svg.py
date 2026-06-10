"""Generate an SVG of the final board using the OFFICIAL connection graph
(honeycomb, see docs/GAME_RULES.md). Cells drawn as circles on a 12x6 brick
layout; connection lines drawn explicitly; 2P's largest color component
(Y, 10 cells) highlighted in pink."""

import sys

sys.path.insert(0, "scripts")
from analyze_game import SLOTS, ADJ, LAYOUT, comps  # noqa: E402
from recover_rules import parse_log, LOG  # noqa: E402

X0, Y0, DX, DY, R = 70, 64, 49, 64, 19

FILL = {"R": "#A85638", "B": "#4B2D4F", "G": "#9FD9BC", "Y": "#BCCB4F"}
TXT = {"R": "#F5EDE4", "B": "#F5EDE4", "G": "#1F3A2E", "Y": "#2C2C2A"}


def pix(cell):
    x, y = LAYOUT[cell]
    return X0 + x * DX, Y0 + y * DY


def main():
    init, moves, scores = parse_log(LOG)
    board = {c: (t, side) for side, c, t, _, _ in moves}
    fin = {c: t for c, (t, _) in board.items()}
    ycomp = set(max((m for a, m in comps(fin, 0) if a == "Y"), key=len))

    out = []
    out.append('<svg width="100%" viewBox="0 0 680 478" role="img" xmlns="http://www.w3.org/2000/svg">')
    out.append("<title>Connexion final board, official connection graph</title>")
    out.append("<desc>64 cells on a honeycomb graph; fill = tile color, digit = pattern; "
               "pink = the AI's 10-tile yellow color component worth 100 points.</desc>")

    drawn = set()
    for c in SLOTS:
        for n in ADJ[c]:
            e = tuple(sorted((c, n)))
            if e in drawn:
                continue
            drawn.add(e)
            (x1, y1), (x2, y2) = pix(c), pix(n)
            hot = c in ycomp and n in ycomp
            col = "#D4537E" if hot else "#888780"
            w = "5" if hot else "2"
            out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{w}"/>')

    for c in SLOTS:
        t, side = board[c]
        x, y = pix(c)
        ring = ' stroke="#D4537E" stroke-width="3.5"' if c in ycomp else ' stroke="#00000033" stroke-width="1"'
        out.append(f'<circle cx="{x}" cy="{y}" r="{R}"{ring} fill="{FILL[t[0]]}"/>')
        out.append(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="central" '
                   f'style="fill:{TXT[t[0]]};font-family:var(--font-sans);font-size:14px;font-weight:500">{t[1]}</text>')
        if c in ycomp and side == "FIRST":
            out.append(f'<circle cx="{x + 14}" cy="{y - 14}" r="5" fill="#D4537E"/>')

    for col in range(6):
        x = X0 + (2 * col) * DX + DX // 2
        out.append(f'<text class="ts" x="{x}" y="{Y0 + 5 * DY + 38}" text-anchor="middle">{chr(97 + col)}</text>')
    for row in range(6):
        y = Y0 + (6 - row - 1) * DY
        out.append(f'<text class="ts" x="{X0 - 46}" y="{y + 4}">{row + 1}</text>')

    ly = 440
    for i, (k, label) in enumerate([("R", "R"), ("G", "G"), ("B", "B"), ("Y", "Y")]):
        out.append(f'<rect x="{30 + i * 38}" y="{ly}" width="13" height="13" fill="{FILL[k]}"/>')
        out.append(f'<text class="ts" x="{47 + i * 38}" y="{ly + 11}">{label}</text>')
    out.append(f'<text class="ts" x="185" y="{ly + 11}">숫자 = 문양 · 선 = 공식 연결 · 분홍 = 2P 최대 색 성분(Y 10칸=100점) · 점 = 그중 1P가 놓은 타일</text>')
    out.append("</svg>")

    svg = "\n".join(out)
    with open(r"data\experiments\final_board.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {len(svg)} chars, edges={len(drawn)}, ycomp={len(ycomp)}")


if __name__ == "__main__":
    main()
