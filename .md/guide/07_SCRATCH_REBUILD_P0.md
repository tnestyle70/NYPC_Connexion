# 07. 바닥부터 직접 재구축 — P0 커리큘럼 (사용자 직접 반영)

작성: 2026-06-11. 운영 방식: Claude가 이 문서에 **개념 + 코드**를 유닛 단위로 박제하고,
**모든 파일은 사용자가 직접 `scratch/`에 작성**한다. 채점은 기존 게이트가 한다.

## 운영 룰

1. 작업 공간 = `scratch/` (기존 `src/`는 정답지 — **막혔을 때만** 연다. 먼저 보지 않기).
2. 유닛 하나 끝날 때마다 게이트 실행 → PASS 화면 확인 → 다음 유닛 요청.
3. 빌드는 전부 WSL: `g++ -O2 -std=c++20 -Wall -Wextra -o build/scratch_test scratch/selftest_main.cpp`
4. 게이트 통과 전에는 다음 유닛으로 넘어가지 않는다 (Mushroom lab 불변식 3 계승).

## 커리큘럼 맵

| 유닛 | 직접 만들 것 | 게이트 (채점기) |
|---|---|---|
| **1** | `scratch/core.hpp` 1부 — 좌표계·토폴로지·파싱 + `scratch/selftest_main.cpp` | TOPOLOGY PASS: 64칸, 차수 {2:32, 3:32}, 인접 예시 3건, 이름 왕복 |
| **2** | `core.hpp` 2부 — GroupSet(롤백 DSU)·State·place/unplace | **GOLDEN 24/20** + 롤백 왕복 |
| 3 | `scratch/sample_ai_main.cpp` — 프로토콜 루프 + c1 | referee pair 64수 완주 (vs `build/sample_ai c1`) |
| 4 | 그리디 c2·c3·s1 | G1 8/8 (공식 예제 대조) + 섀도 s1 **32/32** |
| 5 | minimax c4~c7 | ladder_check G3/G4 + 단일파일 병합 → **포털 제출 14배틀** |
| 6~ | P1 종반 exact 솔버 | (정답지 없음 — 창작 구간, guide 05 §Phase 6 스펙) |

유닛 3~6 자료는 각 유닛 도달 시 이 문서에 증분 박제한다.

---

## 유닛 1 — 좌표계와 토폴로지

### 개념 요점

- 보드는 6×6 격자가 아니라 좌표(열×행)마다 `−`/`+` 두 칸 = 72자리 − 결번 8 = **64칸**.
- 64라는 수가 보배: 점유 상태가 `uint64_t` 한 워드 → "빈 칸 순회"가 비트 연산이 된다.
- 인코딩: `raw = 열×12 + 행×2 + 부호` (열 a..f=0..5, 행 1..6=0..5, −=0/+=1).
  결번 8개를 건너뛰며 0..63 압축 id 부여. raw 오름차순 = 압축 id 오름차순 (동률 해소의 기준 순서).
- 인접 규칙 (공식 명세 그대로):
  `(c,r,−)` ~ {같은 칸 `(c,r,+)`, 왼쪽 열 `(c−1,r,+)`, 아랫 행 `(c,r−1,+)`} — `+`는 그 대칭.
  모든 간선은 정확히 −칸 하나와 +칸 하나를 잇는다 (이분 그래프) → +쪽만 돌면 전 간선 1회씩.
- **테이블 철학**: 인접/매핑은 시작 시 1회 계산해 배열로 — 이후 모든 규칙 질의는 배열 조회.

### 함정 포인트 (디버깅 예상 지점)

1. 인접 후보의 경계(열<0, 행>6)와 **결번 칸 제외**를 둘 다 걸러야 함.
2. 결번 리스트의 부호: `a1-`, `a4-`는 −, `c3+`, `c6+`, `f3+`, `f6+`는 + (행·열 비대칭).
3. `cell_name` 왕복: 64개 전부 `parse_cell(cell_name(i)) == i`.
4. 차수 분포는 정확히 **2가 32칸, 3이 32칸** (결번 1개당 이웃 ≤3칸의 차수를 1씩 깎는다).

### 코드 — `scratch/core.hpp` (1부)

```cpp
#pragma once
// scratch/core.hpp — 바닥부터 직접 재구축 (유닛 1: 좌표계·토폴로지)
// 명세: docs/GAME_RULES.md (finals_1). 게이트: scratch/selftest_main.cpp

#include <array>
#include <cstdint>
#include <string>

namespace cx {

constexpr int RAW_N  = 72;   // 6열 × 6행 × 2부호
constexpr int CELL_N = 64;   // 결번 8 제외
constexpr int TYPE_N = 16;   // 색 4 × 문양 4
constexpr int HAND_INIT = 5;

// raw 인코딩: 열(0..5)*12 + 행(0..5)*2 + 부호(−=0, +=1)
constexpr int raw_of(int col, int row, int sign) { return col * 12 + row * 2 + sign; }

struct Topology {
    std::array<int8_t, RAW_N>  raw2id{};   // 결번 = -1
    std::array<int8_t, CELL_N> id2raw{};
    std::array<std::array<int8_t, 3>, CELL_N> nb{};   // 이웃 id, -1 패딩
    std::array<int8_t, CELL_N> nb_cnt{};

    Topology() {
        // 1) 결번 8칸 표시
        std::array<bool, RAW_N> removed{};
        const int rem[8] = {
            raw_of(0, 0, 0), raw_of(0, 3, 0),   // a1-, a4-
            raw_of(2, 2, 1), raw_of(2, 5, 1),   // c3+, c6+
            raw_of(3, 0, 0), raw_of(3, 3, 0),   // d1-, d4-
            raw_of(5, 2, 1), raw_of(5, 5, 1),   // f3+, f6+
        };
        for (int r : rem) removed[r] = true;

        // 2) raw 오름차순으로 압축 id 부여 (이 순서가 모든 동률 해소의 기준)
        raw2id.fill(-1);
        int id = 0;
        for (int raw = 0; raw < RAW_N; ++raw) {
            if (removed[raw]) continue;
            raw2id[raw] = static_cast<int8_t>(id);
            id2raw[id]  = static_cast<int8_t>(raw);
            ++id;
        }

        // 3) 인접 테이블: '−'칸 → {같은칸+, 왼쪽열+, 아랫행+} / '+'칸은 대칭
        for (int i = 0; i < CELL_N; ++i) {
            int raw = id2raw[i];
            int col = raw / 12, row = (raw % 12) / 2, sign = raw & 1;
            nb[i].fill(-1);
            auto push = [&](int c, int r, int s) {
                if (c < 0 || c >= 6 || r < 0 || r >= 6) return;   // 경계
                int8_t v = raw2id[raw_of(c, r, s)];
                if (v < 0) return;                                 // 결번
                nb[i][nb_cnt[i]++] = v;
            };
            if (sign == 0) { push(col, row, 1); push(col - 1, row, 1); push(col, row - 1, 1); }
            else           { push(col, row, 0); push(col + 1, row, 0); push(col, row + 1, 0); }
        }
    }
};

inline const Topology& topo() { static const Topology t; return t; }

// ---- 이름 ↔ id ----
constexpr char COLOR_CH[4] = {'R', 'G', 'B', 'Y'};
constexpr int tile_color(int t)   { return t >> 2; }   // type id = 색*4 + (문양-1)
constexpr int tile_pattern(int t) { return t & 3; }

inline int parse_cell(const std::string& s) {          // "c5-" → id (결번/오류 -1)
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
inline int parse_tile(const std::string& s) {          // "R3" → 0..15, "X0" → -1
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

}  // namespace cx
```

### 코드 — `scratch/selftest_main.cpp` (유닛 1 버전)

```cpp
// scratch/selftest_main.cpp — 단계별 자가검증 러너 (유닛마다 검사 블록을 늘려간다)
#include <algorithm>
#include <iostream>
#include <vector>

#include "core.hpp"

static int FAILS = 0;
static void check(bool ok, const char* msg) {
    if (!ok) { std::cerr << "FAIL: " << msg << "\n"; ++FAILS; }
}

static std::vector<std::string> neigh_names(const std::string& cell) {
    std::vector<std::string> out;
    int id = cx::parse_cell(cell);
    const auto& T = cx::topo();
    for (int k = 0; k < T.nb_cnt[id]; ++k) out.push_back(cx::cell_name(T.nb[id][k]));
    std::sort(out.begin(), out.end());
    return out;
}

int main() {
    using namespace cx;
    const auto& T = topo();

    // [유닛 1] 토폴로지
    int mapped = 0, deg2 = 0, deg3 = 0;
    for (int raw = 0; raw < RAW_N; ++raw)
        if (T.raw2id[raw] >= 0) ++mapped;
    check(mapped == 64, "64칸 매핑");
    const char* removed[8] = {"a1-", "a4-", "c3+", "c6+", "d1-", "d4-", "f3+", "f6+"};
    for (auto r : removed) check(parse_cell(r) == -1, "결번 8칸은 id 없음");
    for (int i = 0; i < CELL_N; ++i) {
        if (T.nb_cnt[i] == 2) ++deg2;
        if (T.nb_cnt[i] == 3) ++deg3;
        for (int k = 0; k < T.nb_cnt[i]; ++k) {            // 대칭성
            int j = T.nb[i][k];
            bool back = false;
            for (int k2 = 0; k2 < T.nb_cnt[j]; ++k2)
                if (T.nb[j][k2] == i) back = true;
            check(back, "인접 대칭");
        }
        check(parse_cell(cell_name(i)) == i, "칸 이름 왕복");
    }
    check(deg2 == 32 && deg3 == 32, "차수 분포 {2:32, 3:32}");
    check(neigh_names("c5-") == std::vector<std::string>({"b5+", "c4+", "c5+"}), "neigh(c5-)");
    check(neigh_names("f4+") == std::vector<std::string>({"f4-", "f5-"}), "neigh(f4+)");
    check(neigh_names("a4+") == std::vector<std::string>({"a5-", "b4-"}), "neigh(a4+)");
    for (int t = 0; t < TYPE_N; ++t) check(parse_tile(tile_name(t)) == t, "타일 이름 왕복");
    check(parse_tile("X0") == -1, "X0 = 타일 없음");
    std::cout << (FAILS ? "TOPOLOGY FAIL\n" : "TOPOLOGY PASS (64칸, 차수 2:32/3:32, 인접 예시)\n");

    return FAILS ? 1 : 0;
}
```

### 게이트 (유닛 1)

```bash
g++ -O2 -std=c++20 -Wall -Wextra -o build/scratch_test scratch/selftest_main.cpp
./build/scratch_test    # 기대: TOPOLOGY PASS (64칸, 차수 2:32/3:32, 인접 예시)
```

---

## 유닛 2 — Σn² 증분 점수와 롤백 union-find

### 개념 요점

- 점수 = 연결성분 크기² 합. 매수마다 BFS는 낭비 — **병합 순간의 변화량만 더한다**:
  크기 a, b 두 성분 병합 = `(a+b)² − a² − b² = 2ab`. 새 타일 활성화 = `+1`.
  (검산: 3-성분과 2-성분을 다리로 이으면 +2·3·2=12 → 9+4=13에서 25로 ✓)
- 한 수는 **문양 그래프와 색 그래프를 동시에** 바꾼다 → GroupSet 2벌(pat/col)을 같은 place가 갱신.
- 탐색은 "두고 → 보고 → 무르고"의 LIFO → **경로압축 없는 union-by-size + undo 스택**이 정확히 맞는다.
  - 경로압축을 안 쓰는 이유: 압축은 되돌리기 어렵다. size-union만으로 트리 깊이 ≤ log₂64 = 6.
  - undo 기록 = 병합 1건당 (붙은 루트, 붙인 루트) 2바이트. 게임 전체 병합 ≤ 63회/그래프
    + 탐색 스택 여유 → **고정 배열 256이면 힙 할당 0**.
- Mark 패턴: `place()`가 (양 그래프 undo 위치, 칸, 타입, 플레이어)를 반환 → `unplace(mark)`가
  정확히 역순 복원. 이 한 쌍이 이후 모든 탐색(그리디 평가, minimax, P1 종반 솔버)의 노드 연산이 된다.

### 함정 포인트

1. rollback의 산술: 병합을 풀 때 `sa = s − sb` 를 먼저 구하고 `sum_sq += sa² + sb² − s²`.
   **pop 순서는 push의 역순** — LIFO를 어기면 size가 꼬인다.
2. rollback 마지막에 활성화 해제(`parent=-1, size=0, sum_sq -= 1`)를 잊기 쉽다.
3. place에서 이웃 검사 시 "빈 칸"을 타일 배열 `-1`로 거르기 (점유 비트보드와 이중 표현 동기).
4. ply 증감: place에서 `++`, unplace에서 `--` — 한쪽만 하면 패리티(선후공)가 틀어진다.
5. 손패 카운트 음수 방지: place는 `hand[player][type]--` — 검증은 referee가 하므로 봇 내부는 신뢰.

### 코드 — `scratch/core.hpp` 에 이어 붙일 2부

```cpp
// ===== 유닛 2: Σn² 증분 + 롤백 union-find + State =====
namespace cx {

struct GroupSet {
    static constexpr int OPS_MAX = 256;
    std::array<int8_t, CELL_N> parent{};   // -1 = 미배치
    std::array<int8_t, CELL_N> sz{};
    long long sum_sq = 0;                  // Σ(성분 크기)² — 이 그래프의 점수
    struct Op { int8_t into, from; };      // from 루트가 into 루트에 붙었다
    std::array<Op, OPS_MAX> ops{};
    uint32_t ops_n = 0;

    void reset() { parent.fill(-1); sz.fill(0); sum_sq = 0; ops_n = 0; }
    int find(int x) const { while (parent[x] != x) x = parent[x]; return x; }

    void activate(int c) { parent[c] = static_cast<int8_t>(c); sz[c] = 1; sum_sq += 1; }

    void link(int a, int b) {
        int ra = find(a), rb = find(b);
        if (ra == rb) return;                       // 이미 같은 성분
        if (sz[ra] < sz[rb]) std::swap(ra, rb);     // union by size
        long long sa = sz[ra], sb = sz[rb];
        sum_sq += (sa + sb) * (sa + sb) - sa * sa - sb * sb;   // = 2ab
        parent[rb] = static_cast<int8_t>(ra);
        sz[ra] = static_cast<int8_t>(sa + sb);
        ops[ops_n++] = {static_cast<int8_t>(ra), static_cast<int8_t>(rb)};
    }

    // place 1회 분량 복원: mark 이후의 병합을 역순으로 풀고, cell 활성화 해제
    void rollback(uint32_t mark, int cell) {
        while (ops_n > mark) {
            Op o = ops[--ops_n];
            long long s = sz[o.into], sb = sz[o.from], sa = s - sb;
            sum_sq += sa * sa + sb * sb - s * s;
            sz[o.into] = static_cast<int8_t>(sa);
            parent[o.from] = o.from;
        }
        parent[cell] = -1; sz[cell] = 0; sum_sq -= 1;
    }
};

struct Move { int8_t cell = -1; int8_t type = -1; };

struct State {
    std::array<int8_t, CELL_N> tile{};                 // -1 = 빈칸
    uint64_t occ = 0;                                  // 점유 비트보드
    GroupSet pat, col;                                 // 문양/색 그래프 (동시 갱신)
    std::array<std::array<int8_t, TYPE_N>, 2> hand{};  // [플레이어][타입] 장수 (공개)
    std::array<int8_t, 2> hand_n{};
    int ply = 0;                                       // ply&1 = 둘 사람 (0=선공)

    void reset() {
        tile.fill(-1); occ = 0; pat.reset(); col.reset();
        for (auto& h : hand) h.fill(0);
        hand_n = {0, 0}; ply = 0;
    }
    int to_move() const { return ply & 1; }
    long long pattern_score() const { return pat.sum_sq; }   // 선공 점수
    long long color_score()  const { return col.sum_sq; }    // 후공 점수
    long long metric(int p)  const { return p == 0 ? pat.sum_sq : col.sum_sq; }
    long long margin(int p)  const { return metric(p) - metric(p ^ 1); }

    void give(int p, int t) { hand[p][t]++; hand_n[p]++; }

    struct Mark { uint32_t pat_ops, col_ops; int8_t cell, type, player; };

    Mark place(int player, int cell, int type) {
        Mark mk{pat.ops_n, col.ops_n,
                static_cast<int8_t>(cell), static_cast<int8_t>(type),
                static_cast<int8_t>(player)};
        tile[cell] = static_cast<int8_t>(type);
        occ |= 1ull << cell;
        hand[player][type]--; hand_n[player]--;
        pat.activate(cell); col.activate(cell);
        const Topology& T = topo();
        for (int k = 0; k < T.nb_cnt[cell]; ++k) {
            int n = T.nb[cell][k];
            int nt = tile[n];
            if (nt < 0) continue;                                  // 빈 이웃
            if (tile_pattern(nt) == tile_pattern(type)) pat.link(cell, n);
            if (tile_color(nt)   == tile_color(type))   col.link(cell, n);
        }
        ++ply;
        return mk;
    }

    void unplace(const Mark& mk) {
        --ply;
        pat.rollback(mk.pat_ops, mk.cell);
        col.rollback(mk.col_ops, mk.cell);
        hand[mk.player][mk.type]++; hand_n[mk.player]++;
        occ &= ~(1ull << mk.cell);
        tile[mk.cell] = -1;
    }
};

}  // namespace cx
```

### 코드 — `selftest_main.cpp` 의 main 끝(return 직전)에 추가할 블록

```cpp
    // [유닛 2] 골든 보드 (finals_1 점수 계산 예시: 선공 24 / 후공 20) + 롤백 왕복
    {
        const char* seq[10][2] = {{"a4+", "G2"}, {"a5-", "G1"}, {"b4-", "B2"}, {"b4+", "Y2"},
                                  {"b5-", "Y4"}, {"b5+", "R4"}, {"b6-", "B4"}, {"c4+", "R3"},
                                  {"c5-", "R2"}, {"c5+", "Y2"}};
        State st;
        st.reset();
        std::vector<State::Mark> marks;
        for (int i = 0; i < 10; ++i) {
            int pl = i & 1, cell = parse_cell(seq[i][0]), ty = parse_tile(seq[i][1]);
            st.give(pl, ty);
            marks.push_back(st.place(pl, cell, ty));
        }
        check(st.pattern_score() == 24, "골든: 선공(문양) 24");
        check(st.color_score()   == 20, "골든: 후공(색) 20");
        for (int i = 9; i >= 0; --i) st.unplace(marks[i]);
        check(st.occ == 0 && st.pat.sum_sq == 0 && st.col.sum_sq == 0 && st.ply == 0,
              "롤백: 완전 복원");
        std::cout << (FAILS ? "GOLDEN FAIL\n" : "GOLDEN PASS (24/20 + 롤백)\n");
    }
```

### 게이트 (유닛 2)

```bash
g++ -O2 -std=c++20 -Wall -Wextra -o build/scratch_test scratch/selftest_main.cpp
./build/scratch_test
# 기대:
#   TOPOLOGY PASS (64칸, 차수 2:32/3:32, 인접 예시)
#   GOLDEN PASS (24/20 + 롤백)
```

PASS 두 줄이 뜨면 유닛 3(프로토콜 + c1, referee 완주)을 이 문서에 박제한다.
