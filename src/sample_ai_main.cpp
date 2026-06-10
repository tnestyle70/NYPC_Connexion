// ============================================================================
// src/sample_ai_main.cpp — Sample AI 프로토콜 실행기
// 사용:  sample_ai <c1..c7>     (기본 c2)
//        sample_ai --selftest   (G2 토폴로지/골든/롤백 자체검증)
// 프로토콜: .md/guide/04 (READY/INIT/TIME→PUT/GET/OPP/FINISH, 매 출력 flush)
// ============================================================================

#include <algorithm>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "bots.hpp"
#include "core.hpp"

namespace cx {

static bool expect(bool ok, const char* msg, int& fails) {
    if (!ok) {
        std::cerr << "FAIL: " << msg << "\n";
        ++fails;
    }
    return ok;
}

static std::vector<std::string> neighbor_names(const std::string& cell) {
    std::vector<std::string> out;
    int id = parse_cell(cell);
    if (id < 0) return out;
    const Topology& T = topo();
    for (int k = 0; k < T.nb_cnt[id]; ++k) out.push_back(cell_name(T.nb[id][k]));
    std::sort(out.begin(), out.end());
    return out;
}

// G2: 토폴로지 + finals_1 예시 보드(선공 24/후공 20) + 롤백 왕복
static int selftest() {
    int fails = 0;

    // --- 토폴로지 ---
    const char* removed[8] = {"a1-", "a4-", "c3+", "c6+", "d1-", "d4-", "f3+", "f6+"};
    for (const char* r : removed) expect(parse_cell(r) == -1, "removed cell must be unmapped", fails);
    int mapped = 0;
    for (int raw = 0; raw < RAW_N; ++raw)
        if (topo().raw2id[raw] >= 0) ++mapped;
    expect(mapped == CELL_N, "64 cells mapped", fails);

    expect(neighbor_names("c5-") == std::vector<std::string>({"b5+", "c4+", "c5+"}),
           "neigh(c5-) == {b5+, c4+, c5+}", fails);
    expect(neighbor_names("f4+") == std::vector<std::string>({"f4-", "f5-"}),
           "neigh(f4+) == {f4-, f5-}", fails);
    expect(neighbor_names("a4+") == std::vector<std::string>({"a5-", "b4-"}),
           "neigh(a4+) == {a5-, b4-} (a4- 미사용)", fails);

    const Topology& T = topo();
    for (int i = 0; i < CELL_N; ++i) {
        expect(T.nb_cnt[i] >= 1 && T.nb_cnt[i] <= 3, "neighbor count in 1..3", fails);
        for (int k = 0; k < T.nb_cnt[i]; ++k) {
            int j = T.nb[i][k];
            bool back = false;
            for (int k2 = 0; k2 < T.nb_cnt[j]; ++k2)
                if (T.nb[j][k2] == i) back = true;
            expect(back, "adjacency symmetric", fails);
        }
    }

    // --- 파싱 왕복 ---
    for (int i = 0; i < CELL_N; ++i) expect(parse_cell(cell_name(i)) == i, "cell name roundtrip", fails);
    for (int t = 0; t < TYPE_N; ++t) expect(parse_tile(tile_name(t)) == t, "tile name roundtrip", fails);
    expect(parse_tile("X0") == -1, "X0 = no tile", fails);

    // --- 골든 보드 (finals_1 점수 계산 예시) ---
    const char* seq[10][2] = {{"a4+", "G2"}, {"a5-", "G1"}, {"b4-", "B2"}, {"b4+", "Y2"},
                              {"b5-", "Y4"}, {"b5+", "R4"}, {"b6-", "B4"}, {"c4+", "R3"},
                              {"c5-", "R2"}, {"c5+", "Y2"}};
    State st;
    st.reset();
    std::vector<State::Mark> marks;
    for (int i = 0; i < 10; ++i) {
        int pl = i & 1;
        int cell = parse_cell(seq[i][0]);
        int ty = parse_tile(seq[i][1]);
        expect(cell >= 0 && ty >= 0, "golden seq parse", fails);
        st.give(pl, ty);
        marks.push_back(st.place(pl, cell, ty));
    }
    expect(st.pattern_score() == 24, "golden: first(pattern) == 24", fails);
    expect(st.color_score() == 20, "golden: second(color) == 20", fails);

    // --- 롤백 왕복 ---
    for (int i = 9; i >= 0; --i) st.unplace(marks[i]);
    expect(st.occ == 0, "rollback: occ empty", fails);
    expect(st.pat.sum_sq == 0 && st.col.sum_sq == 0, "rollback: scores zero", fails);
    expect(st.ply == 0, "rollback: ply zero", fails);
    bool hands_ok = true;
    for (int p = 0; p < 2; ++p)
        for (int t = 0; t < TYPE_N; ++t)
            if (st.hand[p][t] < 0) hands_ok = false;
    expect(hands_ok, "rollback: hands non-negative", fails);

    if (fails == 0) std::cout << "SELFTEST PASS (topology + golden 24/20 + rollback)\n";
    else std::cout << "SELFTEST FAIL: " << fails << " case(s)\n";
    return fails;
}

}  // namespace cx

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);

    std::string arg = argc > 1 ? argv[1] : "c2";
    if (arg == "--selftest") return cx::selftest() == 0 ? 0 : 1;

    std::unique_ptr<cx::IBot> bot = cx::make_bot(arg);
    if (!bot) {
        std::cerr << "unknown bot: " << arg << " (use c1..c7 | --selftest)\n";
        return 2;
    }

    cx::State st;
    st.reset();
    int me = 0;

    // 손패 도착 순서 (공식 예제 코드의 vector<Tile> 순회 재현용): INIT 순서 + 드로우 append,
    // 사용 시 첫 등장 제거. c2가 hand_seq 포인터로 읽는다.
    std::vector<int8_t> hand_seq[2];
    bot->hand_seq[0] = &hand_seq[0];
    bot->hand_seq[1] = &hand_seq[1];
    auto seq_give = [&](int player, int ty) {
        if (ty < 0) return;
        st.give(player, ty);
        hand_seq[player].push_back(static_cast<int8_t>(ty));
    };
    auto seq_remove_first = [&](int player, int ty) {
        auto& v = hand_seq[player];
        auto it = std::find(v.begin(), v.end(), static_cast<int8_t>(ty));
        if (it != v.end()) v.erase(it);
    };

    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream is(line);
        std::string cmd;
        is >> cmd;
        if (cmd == "READY") {
            std::string role;
            is >> role;
            me = role == "FIRST" ? 0 : 1;
            bot->me = me;
            std::cout << "OK" << std::endl;
        } else if (cmd == "INIT") {
            std::string t;
            for (int i = 0; i < cx::HAND_INIT; ++i) {
                is >> t;
                seq_give(me, cx::parse_tile(t));
            }
            for (int i = 0; i < cx::HAND_INIT; ++i) {
                is >> t;
                seq_give(me ^ 1, cx::parse_tile(t));
            }
        } else if (cmd == "TIME") {
            long long t1 = 0, t2 = 0;
            is >> t1 >> t2;
            cx::Move mv = bot->choose(st, t1, t2);
            std::cout << "PUT " << cx::cell_name(mv.cell) << ' ' << cx::tile_name(mv.type)
                      << std::endl;
            st.place(me, mv.cell, mv.type);
            seq_remove_first(me, mv.type);
        } else if (cmd == "GET") {
            std::string t;
            is >> t;
            seq_give(me, cx::parse_tile(t));
        } else if (cmd == "OPP") {
            std::string p, t1s, t2s;
            long long tt = 0;
            is >> p >> t1s >> t2s >> tt;
            int t1ty = cx::parse_tile(t1s);
            st.place(me ^ 1, cx::parse_cell(p), t1ty);
            seq_remove_first(me ^ 1, t1ty);
            seq_give(me ^ 1, cx::parse_tile(t2s));
        } else if (cmd == "FINISH") {
            break;
        }
    }
    return 0;
}
