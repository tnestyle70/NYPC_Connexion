# 05. Connexion 챔피언 엔진 로드맵 (bot_00 설계)

작성: 2026-06-11 (Claude). 계보: Mushroom `.md/guide/06_CHAMPION_BOT_ROADMAP.md`(Phase 체계)
+ `10_SAMPLE_AI_LADDER_DESIGN.md`(depth 사다리 문법)를 Connexion에 이식.
사다리/하네스는 본 repo `.md/guide/04_SAMPLE_AI_LADDER.md`(Codex)를 그대로 기준으로 쓰고,
이 문서는 그 사다리를 **이기는 쪽**(챔피언 엔진, bot_00 계열)의 설계를 고정한다.
규칙 출처는 `docs/GAME_RULES.md`(공식 finals_1, 리플레이 196/304 재현 검증 완료)가 단일 진실원이다.

> 정정 메모: 04 문서 게임 코어 절의 "주머니 = 16종×2장"은 검증 결과와 다르다.
> 실측(로그 타일 센서스 + 핸드 리플레이): **16종 × 4장 = 총 64장. 초기 손패 5+5 배분 후
> 주머니 54장, 55수째부터 X0.** 구현은 이 수치를 따른다.

## 0. 북극성 원칙 (Mushroom 계승, 그대로 적용)

1. **탐색 골격 > 수치 튜닝.** ID+TT+루트 윈도우가 서기 전에는 평가 계수를 튜닝하지 않는다.
2. **오염된 값 금지.** 타임아웃으로 끊긴 depth의 값은 통째로 버린다. 항상 "마지막 완료 depth"만 채택.
3. **좋은 수를 구조적으로 못 보는 상태 금지.** 하드 프루닝은 정렬 오류와 곱으로 악화된다.
   (Mushroom D5/LMR 기각 교훈: 이런 "모든 수가 swing인 게임"에서는 폭 축소가 특히 위험하다.)
4. **evaluator는 리프마다 불리는 게 정상.** 줄일 대상은 호출 횟수가 아니라 호출 단가다.
5. **측정 없는 변경 금지.** 모든 변경은 사다리 배틀 + self-play A/B(고정 시드, 선후공 교대)
   + oracle regret으로 설명 가능해야 승급한다. 승급 시 `bot/MM-DD/bot_NN` snapshot 보존.

## 1. Connexion의 핵심 본질 — 엔진이 모델링해야 할 6가지

| # | 본질 | 엔진에서의 대응물 |
|---|------|-------------------|
| E1 | 한 수가 문양·색 **두 그래프를 동시에** 바꾼다 | 마진 `ΔV = Δ내메트릭 − Δ상대메트릭`이 모든 평가의 0차항 |
| E2 | 점수 = Σ(성분 크기)² — 확장 +2k+1, 병합 +2ab | 롤백 union-find 2벌(문양/색)로 O(1) 증분 점수 |
| E3 | 허니콤 차수≤3 — 끊기 쉬움. 무결 통로는 b·e열뿐 | 다리(병합 위협) 칸과 통로 점유를 평가 항으로 |
| E4 | 손패 양측 공개, 은닉 = 주머니 순서뿐 | belief 불필요. 주머니 멀티셋 카운팅 + 찬스 노드 |
| E5 | 55수부터 드로우 없음 = 완전 결정론 종반 | 주머니 소진 시 exact 솔버로 전환 (oracle EXACT=1 구간) |
| E6 | 마지막 손패 5장은 강제 배치 (버릴 수 없다) | 종반 손패 부채(상대 색 보유) 평가 + 미리 버리기 |

## 2. 파일 구조와 역할 분담

```text
src/core.hpp        # 규칙 단일 진실원 (04 문서와 공유) — 토폴로지, State, 증분 점수, 수 생성
src/bots.hpp        # c1~c7 사다리 (04 문서 소관)
src/engine.hpp      # ★ 본 문서 소관: 챔피언 탐색 (ID, TT, expectimax, endgame exact)
src/champion_main.cpp # 프로토콜 어댑터 + engine 호출 (제출 시 단일 main.cpp로 압축)
scripts/referee.py  # 04 문서 소관 (채점 하네스)
```

- 챔피언도 사다리 봇과 같은 `core.hpp` 위에 선다. 규칙 구현이 두 벌 생기면 안 된다.
- `main.cpp`(repo 루트)는 champion이 게이트를 통과했을 때만 사용자가 직접 갱신한다 (CLAUDE.md 계약).

## 3. 게임 코어 설계 (core.hpp 스니펫)

### 3.1 토폴로지 — 컴파일 타임 상수

```cpp
// 칸 id: raw = col*12 + (row-1)*2 + (sign=='-'), 존재하는 64칸만 0..63으로 압축
constexpr const char* kHoles[8] = {"a1-","a4-","c3+","c6+","d1-","d4-","f3+","f6+"};

struct Topology {
    int CompactId[72];          // raw -> 0..63, 구멍은 -1
    int NeighborCount[64];      // 2 or 3
    int Neighbor[64][3];        // 공식 인접: (c,r,-) ~ {(c,r,+),(c-1,r,+),(c,r-1,+)}, '+'는 대칭
};
Topology BuildTopology();       // init에서 1회. golden: c5- ~ {c5+,b5+,c4+}, f4+ ~ {f4-,f5-}
```

### 3.2 타일과 상태

```cpp
enum : int { kColors = 4, kPatterns = 4, kTypes = 16, kCopies = 4, kTotalTiles = 64 };
// type id = color*4 + (pattern-1). "X0" = -1.

struct State {
    int8_t  Board[64];          // type id 또는 -1(빈 칸)
    uint64_t Occupied;          // 비트보드 (수 생성, 종반 판정)
    int8_t  Hand[2][kTypes];    // 양측 손패 카운트 (공개 정보)
    int8_t  Bag[kTypes];        // 남은 주머니 멀티셋 (= 4 − 보드 − 양손패, 카운팅으로 유지)
    int     BagTotal;           // 합계. 0이면 드로우 없음 (X0 구간)
    int     Ply;                // 0..63
    int     SideToMove;         // 0=FIRST(문양), 1=SECOND(색)
    ScoreDsu Pat, Col;          // 아래 3.3 — 두 그래프의 증분 점수
    uint64_t Hash;              // Zobrist (5.2)
};
// 수 = (cell 0..63, type). 분기 = 빈칸 수 × 손패 distinct type 수 (≤ 64×5 = 320)
```

### 3.3 롤백 union-find — 증분 Σn²

탐색은 place/unplace가 LIFO이므로 경로압축 없는 union-by-size + undo 스택이 정확히 맞는다.

```cpp
struct ScoreDsu {
    int8_t Parent[64], Size[64], Attr[64]; // Attr: 이 그래프에서 보는 속성값 (문양 or 색), -1=비활성
    long long SumSq;                       // Σ(성분 크기)² — 이 그래프의 현재 점수
    struct UndoRec { int8_t Child, Root, ChildWasRoot; long long PrevSumSq; };
    vector<UndoRec> Undo;                  // place 1회당 마크 푸시

    int Find(int X) const { while (Parent[X] != X) X = Parent[X]; return X; }

    // 반환: 이 place로 인한 SumSq 증가량 (싱글턴 +1 포함)
    long long Place(int Cell, int AttrValue, const Topology& T) {
        long long Before = SumSq;
        Parent[Cell] = Cell; Size[Cell] = 1; Attr[Cell] = AttrValue; SumSq += 1;
        for (int K = 0; K < T.NeighborCount[Cell]; ++K) {
            int N = T.Neighbor[Cell][K];
            if (Attr[N] != AttrValue) continue;          // 빈 칸은 Attr -1
            int Ra = Find(Cell), Rb = Find(N);
            if (Ra == Rb) continue;
            if (Size[Ra] < Size[Rb]) swap(Ra, Rb);
            Undo.push_back({(int8_t)Rb, (int8_t)Ra, 1, SumSq});
            SumSq += 2LL * Size[Ra] * Size[Rb];          // (a+b)² − a² − b²
            Parent[Rb] = Ra; Size[Ra] += Size[Rb];
        }
        return SumSq - Before;
    }
    void UnplaceTo(size_t Mark, int Cell) {              // Place 직전 Undo.size()로 복원
        while (Undo.size() > Mark) {
            auto R = Undo.back(); Undo.pop_back();
            Size[R.Root] -= Size[R.Child]; Parent[R.Child] = R.Child; SumSq = R.PrevSumSq;
        }
        Attr[Cell] = -1; SumSq -= 1;                     // 싱글턴 제거
    }
};
```

마진 한 번 계산 = `Pat.Place + Col.Place → 읽기 → 양쪽 Unplace`. 이웃 ≤3 × 그래프 2 = 수십 연산.
320개 후보 전수 정적 스캔이 노드당 ~1만 연산 수준 → Mushroom식 "노드 다이어트"가 처음부터 내장된다.

### 3.4 골든 테스트 (구현 즉시 통과해야 하는 것)

1. finals_1 예시 보드 10타일 = 선공 24 / 후공 20 (04 문서 G2와 공유).
2. `Log/WebSiteBot/2026-06-11_*.log` 64수 리플레이 = 196 / 304.
3. 토폴로지 차수 분포 {2:32, 3:32}, 인접 예시 2건.
4. 임의 수순 place→unplace 퍼즈: SumSq/Parent/Size 완전 복원 (파이썬 `scripts/analyze_game.py`와 차분).

## 4. 평가함수 — v0부터 순서대로

관점 규약: 항상 "수 두는 쪽" 관점 마진 (negamax 일관성, Mushroom Phase 5 교훈).

```text
v0 (= 사다리 c3와 동일): Margin = (내 그래프 SumSq) − (상대 그래프 SumSq)
v1 = v0 + 템포: 리프에서 둘 차례 쪽의 최대 1수 ΔV를 더한다 (버섯 AI4~7 리프 공식의 이식)
v2 = v1 + 구조항 3개:
  (a) 다리 위협: 빈 칸 c가 같은 속성 성분 a,b를 잇는다면 위협 가치 ≈ 2ab.
      내 위협 합 − 상대 위협 합 (상대 위협은 절반 가중 — 내가 먼저 막을 수 있으므로)
  (b) 카운팅 상한: 속성값별 남은 공급량 (주머니+양손패) — 상대 대형 성분의 성장 여력 디스카운트
  (c) 손패 부채: 종반 가중 (Ply 비례) × "내 손패 중 상대 주력 속성과 일치하는 장수"
```

v2의 계수는 Phase O(oracle 회귀) 전까지 손튜닝 금지 — v0/v1로 골격 게이트를 먼저 통과한다.

## 5. 탐색 골격 — Phase 계획 (Mushroom Phase 매핑)

### Phase 1. ID + 루트 윈도우 + 타임아웃 격리 (Mushroom D1/D2/D3)

- depth 1부터 반복 심화. 각 depth는 **완료됐을 때만** Best 갱신, 끊긴 depth는 통째로 폐기.
- 루트 Alpha 누적 → 형제에게 좁은 윈도우. depth 완료 시 실측값으로 루트 재정렬.
- 다음 depth 시작 가드: `남은 예산 < 직전 depth 소요 × 2.5`면 시작하지 않는다.
- 드로우 처리(이 단계): **손패 고정 결정론 탐색** (사다리 c4~c7과 동일 규약).
  찬스 노드는 Phase E에서 도입 — 골격 검증과 분리한다.

### Phase 2. Transposition Table

- Zobrist: `Z_board[cell][type]` ⊕ `Z_side` ⊕ `Z_hand[side][type][count]`.
  (손패가 상태의 일부 — 같은 보드라도 손패가 다르면 다른 노드다. 주머니는 파생값이라 해시 불요.)
- 수순 교환 동형이 많다 (배치 제약이 없어 A→B와 B→A가 같은 보드). TT 이득이 버섯보다 클 것.
- depth-preferred 교체, 오염값 저장 금지, best move 저장 (Phase 3 재료).

### Phase 3. 정렬 사슬

① 이전 depth 루트 실측값 → ② TT move → ③ 정적 ΔV (3.3의 전수 스캔) → ④ 동률은 (cell asc, type asc).
killer는 보류 — Mushroom에서 폭 제한 체제와 상성이 나빠 게이트 2회 실패한 전례.

### Phase 4. 선택성 (신중하게)

- 분기 320은 전수 depth 4가 불가능하므로 폭 제한이 불가피하다. 단 북극성 #3:
  **루트는 전폭** (ID가 매 depth 재정렬하므로 안전), 내부만 `w_inner` 제한 (초기값 16, 04 문서보다 후하게).
- "타일 type 차원 먼저 자르기": 같은 칸에 두는 후보 중 정적 ΔV 최하위 type은 거의 항상 지배됨 —
  칸당 상위 2 type만 내부 후보로. (지배 검증을 oracle regret으로 확인 후 적용)
- LMR은 oracle 정렬 회귀 이후에만 재도전 (Mushroom 기각 교훈 그대로).

### Phase 5. 리프 안정화

- 이 게임은 패스가 없고 모든 수가 swing이므로 버섯식 quiescence 대신 **v1 템포 항**이 리프 안정화를 담당.
- 큰 병합(ΔV ≥ 상위 컷)이 걸린 리프만 1 ply 연장하는 "race 연장"은 게이트로 검증 후 도입.

### Phase 6. 종반 완전 해결 (E5)

- 트리거: `BagTotal == 0` (실전 55수~) 또는 양손패+보드로 잔여 수순이 결정론임이 확인될 때.
- 잔여 ≤10 ply, 분기 = 빈칸×distinct type (≤50) → alpha-beta + TT로 종단까지. 반환은 정확 점수차.
- 이 구간이 oracle의 `EXACT=1` 라벨 공장이다 (§7). bot == oracle 교차 검증 필수.
- 스트레치: `BagTotal ≤ 4`부터 찬스 노드 포함 expectimax-exact (가지 ≤16이 1~2회뿐).

### Phase 7. 시간 관리

- 총시계 10,000ms/게임 (TIME t1). 32수 기준 기본 ~280ms/수 + 초반 가중, 종반 exact는 저렴.
- 중단 판단은 depth 경계에서만. IO/flush 마진 10%.
- 결정론 옵션 (Mushroom r13 교훈): 사다리/회귀 검증 시에는 시간 대신 **노드 예산** 모드로 돌려
  같은 입력 → 같은 수순을 보장한다 (`--nodes` 플래그).

### Phase E. 찬스 노드 (드로우) — 골격 안정 후

단계적 도입, 각 단계가 게이트 통과해야 다음으로:

```text
E0 (기본): 드로우 무시 (손패 고정). 사다리와 동일 — 이미 꽤 강함 (샘플 AI가 이 체제로 0 regret)
E1: 리프에 "손패 기대 보충" 항 — 주머니 멀티셋 평균 ΔV의 할인 합 (탐색 구조 불변, 평가만 보강)
E2: 루트 1단 expectimax — 내 수 직후 드로우만 분포 전개 (가지 ≤16, 깊은 곳은 E0/E1)
E3: determinization K샘플 (고정 시드) 평균 — ISMCTS-lite. E2와 A/B로 승자 채택
```

## 6. 프로토콜 어댑터 (champion_main.cpp 골격)

```cpp
int main() {
    ios::sync_with_stdio(false);
    string Line;
    Engine E;                                   // core 초기화, 시계 시작 전
    while (getline(cin, Line)) {
        istringstream In(Line); string Cmd; In >> Cmd;
        if (Cmd == "READY")  { string Role; In >> Role; E.SetRole(Role == "FIRST");
                               cout << "OK" << endl; }            // endl = flush
        else if (Cmd == "INIT") { E.LoadHands(In); }              // 내 5장 + 상대 5장
        else if (Cmd == "TIME") { long long T1, T2; In >> T1 >> T2;
                               auto [Cell, Tile] = E.Choose(T1);  // 예산 = f(T1, 잔여 내 수)
                               cout << "PUT " << CellName(Cell) << ' ' << TileName(Tile) << endl; }
        else if (Cmd == "GET")  { E.OnMyDraw(In); }               // X0 처리 포함
        else if (Cmd == "OPP")  { E.OnOppMove(In); }              // 배치 + 상대 드로우 공개
        else if (Cmd == "FINISH") break;
    }
    return 0;
}
```

불변식: 출력은 내 턴 명령(TIME)에만, 한 줄 + flush. 상태는 OPP/GET에서만 전이.
모든 명령 처리 후 내부 State와 카운팅(Bag = 4 − Board − Hands)이 일치하는지 디버그 어서션.

## 7. Oracle / regret 파이프라인 연결

- `scripts/analyze_game.py`의 1-ply greedy가 oracle v0 (이번 샘플 AI전 분석에 사용한 것).
- oracle v1 = 엔진의 Phase 6 exact 솔버를 CLI로 노출 (`--solve <state>`): 종반 구간 EXACT=1 라벨.
- oracle v2 = 비종반 구간 깊은 탐색 (시간 무제한, EXACT=0 hint).
- 라벨 스키마는 `docs/ORACLE_CONTRACT.md` 그대로: best action, played value, regret, depth, exactness.
- 모든 패배 게임은 regret 케이스로 분류해 Phase/평가 항 중 어디 실패인지 적는다 (AGENTS.md 학습 규칙).

## 8. 게이트 (승급 조건)

| 게이트 | 기준 |
|---|---|
| GC0 골든 | §3.4 전부 (finals_1 예시 24/20, 리플레이 196/304, 토폴로지, DSU 퍼즈) |
| GC1 사다리 | 04 문서 c1~c7 × 선후공 14배틀 전승 (최소: C티어 c6·c7 4판 전승) |
| GC2 셀프 A/B | 변경마다 고정 시드 ≥16판 선후공 교대, 사전 선언 마진 기준 통과 |
| GC3 regret | 종반 exact 구간 regret 0. 전 구간 평균 regret이 이전 봇 대비 비악화 |
| GC4 결정론 | 노드 예산 모드에서 동일 시드 2회 = 동일 수순 (04 문서 G4와 공유) |
| GC5 실전 | 웹사이트 샘플 AI(= 1-ply greedy ΔV, 0 regret 확인됨) 선후공 모두 승리 |

## 9. 진행 현황 (박제 — 갱신은 반영 시점에)

| Phase | 내용 | 상태 |
|-------|------|------|
| 0 | core.hpp 규칙 코어 + 골든 (GC0) | 미착수 |
| 1 | ID + 루트 윈도우 + 타임아웃 격리 | 미착수 |
| 2 | TT (Zobrist: board+side+hands) | 미착수 |
| 3 | 정렬 사슬 (PV → TT → 정적 ΔV) | 미착수 |
| 4 | 내부 폭 제한 + type 지배 컷 | 미착수 |
| 5 | 평가 v1 (템포) → v2 (다리/카운팅/손패 부채) | 미착수 |
| 6 | 종반 exact (BagTotal==0) + oracle EXACT=1 공장 | 미착수 |
| 7 | 시간 관리 (10초 총시계, 노드 예산 모드) | 미착수 |
| E | 찬스 노드 E1→E2/E3 | 미착수 |
| O | oracle 회귀로 v2 계수 학습 | 미착수 |

권장 착수 순서: 0 → 1 → 6 → 2 → 3 → 5(v1) → 7 → 4 → E → 5(v2) → O.
(6을 앞당기는 이유: 구현이 가장 싸고, GC3 regret 게이트와 oracle 라벨 공장이 즉시 생기며,
Mushroom에서도 종반 exact가 승률 기여 1순위였다.)
