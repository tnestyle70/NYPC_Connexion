#pragma once
// ============================================================================
// src/bots.hpp — Sample AI 사다리 c1~c7 (.md/guide/04 설계 고정본)
//
// 공통 규약: RNG 없음(완전 결정론), 시계를 읽되 쓰지 않음(시간 적응 금지),
//           동률 해소 = (값, cell asc, type asc) 전순서.
// c4~c7 = 버섯 AI4~7 구조 이식: 리프(depth 0)에서 수 두는 쪽의 정적 swing 전수 스캔.
//         Connexion엔 패스가 없으므로 stand-pat 없음 (수가 없을 때만 현재 마진).
// ============================================================================

#include <algorithm>
#include <bit>
#include <climits>
#include <memory>
#include <string>
#include <vector>

#include "core.hpp"

namespace cx {

struct IBot {
    int me = 0;  // 0 = 선공(문양), 1 = 후공(색)
    // 손패 도착 순서 (INIT 순서 + 드로우 append, 사용 시 첫 등장 제거). 드라이버가 유지/주입.
    // 공식 예제 코드의 순회 순서 재현(c2)에 필요. nullptr 허용 (미주입 시 type id 순 폴백).
    const std::vector<int8_t>* hand_seq[2] = {nullptr, nullptr};
    virtual ~IBot() = default;
    virtual const char* name() const = 0;
    virtual Move choose(State& st, long long t_my, long long t_opp) = 0;
};

namespace detail {

struct Cand {
    Move mv;
    long long d;  // ΔV = Δ(margin(me))
};

// side가 두는 모든 합법수의 마진 변화량(me 시점). 생성 순서: cell asc × type asc.
inline void gen(State& st, int side, int me, std::vector<Cand>& out) {
    out.clear();
    long long v0 = st.margin(me);
    for (uint64_t e = ~st.occ; e; e &= e - 1) {
        int cell = std::countr_zero(e);
        for (int t = 0; t < TYPE_N; ++t) {
            if (st.hand[side][t] <= 0) continue;
            State::Mark mk = st.place(side, cell, t);
            long long d = st.margin(me) - v0;
            st.unplace(mk);
            out.push_back({{static_cast<int8_t>(cell), static_cast<int8_t>(t)}, d});
        }
    }
}

inline void sort_cands(std::vector<Cand>& v, bool desc) {
    std::sort(v.begin(), v.end(), [desc](const Cand& a, const Cand& b) {
        if (a.d != b.d) return desc ? a.d > b.d : a.d < b.d;
        if (a.mv.cell != b.mv.cell) return a.mv.cell < b.mv.cell;
        return a.mv.type < b.mv.type;
    });
}

// V = margin(me) 기준 minimax. depth 0 리프 = side의 정적 swing 스캔 (할당 없음).
inline long long alpha_beta(State& st, int depth, long long alpha, long long beta,
                            int side, int me, int w_inner) {
    long long v0 = st.margin(me);
    bool maximize = (side == me);

    if (depth == 0) {
        bool any = false;
        long long best = maximize ? alpha : beta;
        for (uint64_t e = ~st.occ; e; e &= e - 1) {
            int cell = std::countr_zero(e);
            for (int t = 0; t < TYPE_N; ++t) {
                if (st.hand[side][t] <= 0) continue;
                any = true;
                State::Mark mk = st.place(side, cell, t);
                long long v = st.margin(me);
                st.unplace(mk);
                if (maximize) {
                    if (v > best) { best = v; if (best >= beta) return beta; }
                } else {
                    if (v < best) { best = v; if (best <= alpha) return alpha; }
                }
            }
        }
        if (!any) return std::clamp(v0, alpha, beta);
        return best;
    }

    std::vector<Cand> cand;
    gen(st, side, me, cand);
    if (cand.empty()) return std::clamp(v0, alpha, beta);
    sort_cands(cand, maximize);
    if (w_inner > 0 && static_cast<int>(cand.size()) > w_inner) cand.resize(w_inner);

    if (maximize) {
        long long best = alpha;
        for (const Cand& c : cand) {
            State::Mark mk = st.place(side, c.mv.cell, c.mv.type);
            long long v = alpha_beta(st, depth - 1, best, beta, side ^ 1, me, w_inner);
            st.unplace(mk);
            if (v > best) { best = v; if (best >= beta) return beta; }
        }
        return best;
    } else {
        long long best = beta;
        for (const Cand& c : cand) {
            State::Mark mk = st.place(side, c.mv.cell, c.mv.type);
            long long v = alpha_beta(st, depth - 1, alpha, best, side ^ 1, me, w_inner);
            st.unplace(mk);
            if (v < best) { best = v; if (best <= alpha) return alpha; }
        }
        return best;
    }
}

}  // namespace detail

// c1: 최소 type 손패 → 최소 id 빈칸 (바닥 앵커)
struct FirstBot : IBot {
    const char* name() const override { return "c1"; }
    Move choose(State& st, long long, long long) override {
        int t = 0;
        while (t < TYPE_N && st.hand[me][t] <= 0) ++t;
        int cell = std::countr_zero(~st.occ);
        return {static_cast<int8_t>(cell), static_cast<int8_t>(t)};
    }
};

// c2: 자기 메트릭 최대 — 공식 예제 코드(docs/official_sample/sample-code.cpp) 동작 재현.
// 공식 순회: 타일(손패 도착 순서) outer × 칸(id 오름차순) inner, strict > (먼저 발견된 수 우선).
// G1(scripts/g1_check.py)으로 전 수 일치 검증. hand_seq 미주입 시 type id 순 폴백.
struct GreedySelfBot : IBot {
    const char* name() const override { return "c2"; }
    Move choose(State& st, long long, long long) override {
        long long best = LLONG_MIN;
        Move bm;
        long long m0 = st.metric(me);
        auto scan_cells = [&](int t) {
            for (uint64_t e = ~st.occ; e; e &= e - 1) {
                int cell = std::countr_zero(e);
                State::Mark mk = st.place(me, cell, t);
                long long d = st.metric(me) - m0;
                st.unplace(mk);
                if (d > best) {
                    best = d;
                    bm = {static_cast<int8_t>(cell), static_cast<int8_t>(t)};
                }
            }
        };
        if (hand_seq[me]) {
            for (int8_t t : *hand_seq[me]) scan_cells(t);
        } else {
            for (int t = 0; t < TYPE_N; ++t)
                if (st.hand[me][t] > 0) scan_cells(t);
        }
        return bm;
    }
};

// c3: 마진 ΔV 최대 (1수 swing 그리디 — 핑크빈 역할)
struct GreedyMarginBot : IBot {
    const char* name() const override { return "c3"; }
    Move choose(State& st, long long, long long) override {
        long long best = LLONG_MIN;
        Move bm;
        long long v0 = st.margin(me);
        for (uint64_t e = ~st.occ; e; e &= e - 1) {
            int cell = std::countr_zero(e);
            for (int t = 0; t < TYPE_N; ++t) {
                if (st.hand[me][t] <= 0) continue;
                State::Mark mk = st.place(me, cell, t);
                long long d = st.margin(me) - v0;
                st.unplace(mk);
                if (d > best) {
                    best = d;
                    bm = {static_cast<int8_t>(cell), static_cast<int8_t>(t)};
                }
            }
        }
        return bm;
    }
};

// s1: 사이트 샘플 AI 레플리카 (scripts/shadow_replay.py 로 동정, 2026-06-11 로그 32/32 일치).
// 정책 = 1-ply 마진 그리디 (c3와 동급). 순회 = 칸 outer(행우선: 행1→6 × 열a→f × −,+) ×
//        타일 inner(손패 도착 순서), strict > (먼저 발견된 수 우선). 사다리 외 회귀 게이트용.
struct SiteReplicaBot : IBot {
    const char* name() const override { return "s1"; }
    static const std::vector<int8_t>& rowmajor_cells() {
        static const std::vector<int8_t> v = [] {
            std::vector<int8_t> out;
            for (int r = 0; r < 6; ++r)
                for (int c = 0; c < 6; ++c)
                    for (int s = 0; s < 2; ++s) {
                        int8_t id = topo().raw2id[raw_of(c, r, s)];
                        if (id >= 0) out.push_back(id);
                    }
            return out;
        }();
        return v;
    }
    Move choose(State& st, long long, long long) override {
        long long best = LLONG_MIN;
        Move bm;
        long long v0 = st.margin(me);
        auto try_tile = [&](int cell, int t) {
            State::Mark mk = st.place(me, cell, t);
            long long d = st.margin(me) - v0;
            st.unplace(mk);
            if (d > best) {
                best = d;
                bm = {static_cast<int8_t>(cell), static_cast<int8_t>(t)};
            }
        };
        for (int8_t cell : rowmajor_cells()) {
            if ((st.occ >> cell) & 1ull) continue;
            if (hand_seq[me]) {
                for (int8_t t : *hand_seq[me]) try_tile(cell, t);
            } else {
                for (int t = 0; t < TYPE_N; ++t)
                    if (st.hand[me][t] > 0) try_tile(cell, t);
            }
        }
        return bm;
    }
};

// c4~c7: minimax d0~d3 (짝수 depth = 방어형, 홀수 = 공격형).
// 폭 상수는 10초 총시계 안에서 결정론을 지키는 고정값 (guide 04 표).
struct MinimaxBot : IBot {
    const char* nm;
    int depth, w_root, w_inner;  // w_root 0 = 전수
    MinimaxBot(const char* n, int d, int wr, int wi) : nm(n), depth(d), w_root(wr), w_inner(wi) {}
    const char* name() const override { return nm; }

    Move choose(State& st, long long, long long) override {
        std::vector<detail::Cand> cand;
        detail::gen(st, me, me, cand);
        if (cand.empty()) return {};
        detail::sort_cands(cand, true);
        if (w_root > 0 && static_cast<int>(cand.size()) > w_root) cand.resize(w_root);

        long long best = LLONG_MIN;
        Move bm = cand.front().mv;
        for (const detail::Cand& c : cand) {
            State::Mark mk = st.place(me, c.mv.cell, c.mv.type);
            long long alpha = best == LLONG_MIN ? LLONG_MIN : best;
            long long v = detail::alpha_beta(st, depth, alpha, LLONG_MAX, me ^ 1, me, w_inner);
            st.unplace(mk);
            if (v > best) {
                best = v;
                bm = c.mv;
            }
        }
        return bm;
    }
};

inline std::unique_ptr<IBot> make_bot(const std::string& name) {
    if (name == "c1") return std::make_unique<FirstBot>();
    if (name == "c2") return std::make_unique<GreedySelfBot>();
    if (name == "c3") return std::make_unique<GreedyMarginBot>();
    if (name == "s1") return std::make_unique<SiteReplicaBot>();
    if (name == "c4") return std::make_unique<MinimaxBot>("c4", 0, 0, 0);
    if (name == "c5") return std::make_unique<MinimaxBot>("c5", 1, 24, 12);
    if (name == "c6") return std::make_unique<MinimaxBot>("c6", 2, 16, 8);
    if (name == "c7") return std::make_unique<MinimaxBot>("c7", 3, 12, 6);
    return nullptr;
}

}  // namespace cx
