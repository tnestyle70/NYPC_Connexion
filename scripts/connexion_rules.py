#!/usr/bin/env python3
"""Connexion 규칙의 파이썬 미러 (referee/테스트 공용).

C++ src/core.hpp 와 이중 구현이며, 골든 테스트(scripts/golden_test.py)로 양쪽을 핀 고정한다.
명세: NYPC 2025 finals_1. 설계: .md/guide/04_SAMPLE_AI_LADDER.md
"""

COLS = "abcdef"
COLORS = "RGBY"
REMOVED = {"a1-", "a4-", "c3+", "c6+", "d1-", "d4-", "f3+", "f6+"}


def _gen_cells():
    names = [f"{c}{r}{s}" for c in COLS for r in "123456" for s in "-+"]
    return [n for n in names if n not in REMOVED]


CELLS = _gen_cells()           # 압축 id 순서 = raw 오름차순 (C++ 과 동일)
CELL_SET = set(CELLS)
CELL_ID = {n: i for i, n in enumerate(CELLS)}

TYPES = [f"{c}{p}" for c in COLORS for p in "1234"]  # type id = color*4 + (pattern-1)


def _neighbors(name):
    col = COLS.index(name[0])
    row = int(name[1]) - 1
    sign = name[2]
    if sign == "-":
        cand = [(col, row, "+"), (col - 1, row, "+"), (col, row - 1, "+")]
    else:
        cand = [(col, row, "-"), (col + 1, row, "-"), (col, row + 1, "-")]
    out = []
    for c, r, s in cand:
        if 0 <= c < 6 and 0 <= r < 6:
            n = f"{COLS[c]}{r + 1}{s}"
            if n in CELL_SET:
                out.append(n)
    return out


NEIGH = {n: _neighbors(n) for n in CELLS}


def component_sq_sum(board, key_index):
    """board: dict cell->tile("R3"). key_index: 0=색, 1=문양. 연결성분 size² 합."""
    seen = set()
    total = 0
    for start in board:
        if start in seen:
            continue
        seen.add(start)
        stack = [start]
        size = 0
        while stack:
            x = stack.pop()
            size += 1
            for nb in NEIGH[x]:
                if nb in board and nb not in seen and board[nb][key_index] == board[x][key_index]:
                    seen.add(nb)
                    stack.append(nb)
        total += size * size
    return total


def score(board):
    """(선공=문양 점수, 후공=색 점수)"""
    return component_sq_sum(board, 1), component_sq_sum(board, 0)


def full_bag():
    """한 플레이어의 주머니: 16종 x 2장 = 32장 (셔플 전, 고정 순서)."""
    return [t for t in TYPES for _ in range(2)]
