#pragma once
// ============================================================================
// src/core.hpp — Connexion rules engine (규칙 단일 진실원)
// 명세: NYPC 2025 finals_1 (https://nypc.github.io/2025-codebattle/finals_1)
// 설계: .md/guide/04_SAMPLE_AI_LADDER.md
//
// 좌표: 열 a..f(0..5) × 행 1..6(0..5) × 부호 -(0)/+(1) → raw = col*12+row*2+sign
//       미사용 8칸(a1-,a4-,c3+,c6+,d1-,d4-,f3+,f6+) 제외 → 압축 id 0..63
// 인접: '-'칸 → {같은 열·행 '+', 왼쪽 열 '+', 아랫 행 '+'}, '+'칸은 그 대칭. 칸당 최대 3.
// 타일: 색 R,G,B,Y(0..3) × 문양 1..4 → type id = color*4 + (pattern-1), 16종.
// 점수: 보드 전체(소유 무관). 선공 = 문양 연결성분 size² 합, 후공 = 색 동일.
// ============================================================================

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace cx {

constexpr int RAW_N = 72;
constexpr int CELL_N = 64;
constexpr int TYPE_N = 16;
constexpr int HAND_INIT = 5;
constexpr int PLIES = 64;

constexpr int raw_of(int col, int row, int sign) { return col * 12 + row * 2 + sign; }

struct Topology {
    std::array<int8_t, RAW_N> raw2id{};
    std::array<int8_t, CELL_N> id2raw{};
    std::array<std::array<int8_t, 3>, CELL_N> nb{};
    std::array<int8_t, CELL_N> nb_cnt{};

    Topology() {
        std::array<bool, RAW_N> removed{};
        const int rem[8] = {
            raw_of(0, 0, 0), raw_of(0, 3, 0),  // a1-, a4-
            raw_of(2, 2, 1), raw_of(2, 5, 1),  // c3+, c6+
            raw_of(3, 0, 0), raw_of(3, 3, 0),  // d1-, d4-
            raw_of(5, 2, 1), raw_of(5, 5, 1),  // f3+, f6+
        };
        for (int r : rem) removed[r] = true;

        raw2id.fill(-1);
        int id = 0;
        for (int raw = 0; raw < RAW_N; ++raw) {
            if (removed[raw]) continue;
            raw2id[raw] = static_cast<int8_t>(id);
            id2raw[id] = static_cast<int8_t>(raw);
            ++id;
        }
        for (int i = 0; i < CELL_N; ++i) {
            int raw = id2raw[i];
            int col = raw / 12, row = (raw % 12) / 2, sign = raw & 1;
            nb[i].fill(-1);
            auto push = [&](int c, int r, int s) {
                if (c < 0 || c >= 6 || r < 0 || r >= 6) return;
                int8_t v = raw2id[raw_of(c, r, s)];
                if (v < 0) return;
                nb[i][nb_cnt[i]++] = v;
            };
            if (sign == 0) { push(col, row, 1); push(col - 1, row, 1); push(col, row - 1, 1); }
            else           { push(col, row, 0); push(col + 1, row, 0); push(col, row + 1, 0); }
        }
    }
};

inline const Topology& topo() {
    static const Topology t;
    return t;
}

constexpr char COLOR_CH[4] = {'R', 'G', 'B', 'Y'};

constexpr int tile_color(int t) { return t >> 2; }
constexpr int tile_pattern(int t) { return t & 3; }

// "c5-" → 압축 id, 미사용/형식 오류 → -1
inline int parse_cell(const std::string& s) {
    if (s.size() != 3) return -1;
    int c = s[0] - 'a', r = s[1] - '1';
    int sg = s[2] == '-' ? 0 : s[2] == '+' ? 1 : -1;
    if (c < 0 || c >= 6 || r < 0 || r >= 6 || sg < 0) return -1;
    return topo().raw2id[raw_of(c, r, sg)];
}

inline std::string cell_name(int id) {
    int raw = topo().id2raw[id];
    int c = raw / 12, r = (raw % 12) / 2, sg = raw & 1;
    return {static_cast<char>('a' + c), static_cast<char>('1' + r), sg ? '+' : '-'};
}

// "R3" → type id, "X0"/형식 오류 → -1
inline int parse_tile(const std::string& s) {
    if (s.size() != 2) return -1;
    int c = -1;
    for (int i = 0; i < 4; ++i)
        if (s[0] == COLOR_CH[i]) c = i;
    int p = s[1] - '1';
    if (c < 0 || p < 0 || p >= 4) return -1;
    return c * 4 + p;
}

inline std::string tile_name(int t) {
    return {COLOR_CH[tile_color(t)], static_cast<char>('1' + tile_pattern(t))};
}

// 롤백 가능한 union-find + 연결성분 size² 합 증분 유지 (path compression 없음, union by size)
// undo 로그는 고정 배열: 게임 전체 병합 ≤ 63회/그래프 + 탐색 스택 여유 → 256 충분, 할당 없음.
struct GroupSet {
    static constexpr int OPS_MAX = 256;
    std::array<int8_t, CELL_N> parent{};  // -1 = 미배치
    std::array<int8_t, CELL_N> sz{};
    long long sum_sq = 0;
    struct Op { int8_t into, from; };
    std::array<Op, OPS_MAX> ops{};
    uint32_t ops_n = 0;

    void reset() {
        parent.fill(-1);
        sz.fill(0);
        sum_sq = 0;
        ops_n = 0;
    }
    int find(int x) const {
        while (parent[x] != x) x = parent[x];
        return x;
    }
    void activate(int c) {
        parent[c] = static_cast<int8_t>(c);
        sz[c] = 1;
        sum_sq += 1;
    }
    void link(int a, int b) {
        int ra = find(a), rb = find(b);
        if (ra == rb) return;
        if (sz[ra] < sz[rb]) std::swap(ra, rb);
        long long sa = sz[ra], sb = sz[rb];
        sum_sq += (sa + sb) * (sa + sb) - sa * sa - sb * sb;
        parent[rb] = static_cast<int8_t>(ra);
        sz[ra] = static_cast<int8_t>(sa + sb);
        ops[ops_n++] = {static_cast<int8_t>(ra), static_cast<int8_t>(rb)};
    }
    // place 한 번 분량(병합 기록 mark 이후 + cell 활성화)을 역순 복원
    void rollback(uint32_t mark, int cell) {
        while (ops_n > mark) {
            Op o = ops[--ops_n];
            long long s = sz[o.into], sb = sz[o.from], sa = s - sb;
            sum_sq += sa * sa + sb * sb - s * s;
            sz[o.into] = static_cast<int8_t>(sa);
            parent[o.from] = o.from;
        }
        parent[cell] = -1;
        sz[cell] = 0;
        sum_sq -= 1;
    }
};

struct Move {
    int8_t cell = -1;
    int8_t type = -1;
};

struct State {
    std::array<int8_t, CELL_N> tile{};  // -1 = 빈칸
    uint64_t occ = 0;
    GroupSet pat, col;
    std::array<std::array<int8_t, TYPE_N>, 2> hand{};  // [player][type] 장수 (양측 공개)
    std::array<int8_t, 2> hand_n{};
    int ply = 0;  // 0..63, ply&1 = 둘 사람 (0 = 선공)

    void reset() {
        tile.fill(-1);
        occ = 0;
        pat.reset();
        col.reset();
        for (auto& h : hand) h.fill(0);
        hand_n = {0, 0};
        ply = 0;
    }
    int to_move() const { return ply & 1; }
    long long pattern_score() const { return pat.sum_sq; }  // 선공 점수
    long long color_score() const { return col.sum_sq; }    // 후공 점수
    long long metric(int player) const { return player == 0 ? pat.sum_sq : col.sum_sq; }
    long long margin(int player) const { return metric(player) - metric(player ^ 1); }

    void give(int player, int type) {
        hand[player][type]++;
        hand_n[player]++;
    }

    struct Mark {
        uint32_t pat_ops, col_ops;
        int8_t cell, type, player;
    };

    Mark place(int player, int cell, int type) {
        Mark mk{pat.ops_n, col.ops_n,
                static_cast<int8_t>(cell), static_cast<int8_t>(type), static_cast<int8_t>(player)};
        tile[cell] = static_cast<int8_t>(type);
        occ |= 1ull << cell;
        hand[player][type]--;
        hand_n[player]--;
        pat.activate(cell);
        col.activate(cell);
        const Topology& T = topo();
        for (int k = 0; k < T.nb_cnt[cell]; ++k) {
            int n = T.nb[cell][k];
            int nt = tile[n];
            if (nt < 0) continue;
            if (tile_pattern(nt) == tile_pattern(type)) pat.link(cell, n);
            if (tile_color(nt) == tile_color(type)) col.link(cell, n);
        }
        ++ply;
        return mk;
    }

    void unplace(const Mark& mk) {
        --ply;
        pat.rollback(mk.pat_ops, mk.cell);
        col.rollback(mk.col_ops, mk.cell);
        hand[mk.player][mk.type]++;
        hand_n[mk.player]++;
        occ &= ~(1ull << mk.cell);
        tile[mk.cell] = -1;
    }
};

}  // namespace cx
