# 04. Sample AI 사다리 — 설계 고정

작성: 2026-06-11. 원본 분석: Mushroom lab `.md/guide/10_SAMPLE_AI_LADDER_DESIGN.md`
(공식 버섯 AI1~7 / Yacht 10종 해부). 이 문서는 Connexion용 자체 Sample AI 사다리와
채점 하네스의 구현 기준을 고정한다.

## 왜 만드는가

- 2025 파이널 Connexion은 공식 난이도 사다리가 없다 (greedy 예제 코드뿐).
- 2026 예선 채점 = "샘플 AI 채점, X승 (A/B/C)" + 대표답안 자격 게이트. 이 시스템이 로컬 미러다.
- 메인 엔진(main.cpp 계열)의 진척은 이 사다리를 기준으로 측정한다 (PIPELINE.md의 gate 역할).

## 공식 문법 (해부 결론, 그대로 계승)

1. stdin 한 줄 = 한 명령. 내 턴 명령에만 출력 + flush. 봇은 게임당 1프로세스, 양쪽 풀 상태 유지.
2. 결정론: 고정 시드/무작위 비사용, 시계 비의존. 같은 입력 스트림 → 같은 출력.
3. 사다리 = 바닥 앵커 + **예제 코드 재현 배틀** + 단일 엔진 depth 노브(짝수=방어/홀수=공격).
4. 채점 = 봇당 선후공 교대, 승 1 / 무 0.5 / 패 0, 티어 묶음 (A/B/C).

## 게임 코어 (src/core.hpp)

- 좌표: 열 a..f × 행 1..6 × 부호 -,+ = 72 − 미사용 8칸(a1-,a4-,c3+,c6+,d1-,d4-,f3+,f6+) = 64칸.
  raw = col*12+row*2+sign → 압축 id 0..63 (**u64 비트보드 한 워드**).
- 인접: '-'칸 → {같은열행 +, 왼쪽열 +, 아랫행 +}, '+'칸 대칭. 칸당 최대 3.
- 타일: 색 R,G,B,Y × 문양 1..4 = 16종, type id = color*4+(pattern-1). 주머니 = 16종×2장.
- 점수: 보드 전체(소유 무관). 선공 = 문양 연결성분 size² 합, 후공 = 색 동일.
  롤백 가능한 union-find 2벌(pat/col)로 증분 유지: 병합 시 `(a+b)²−a²−b²`.
- 정보: 손패 5장 양측 공개(INIT/OPP/GET) → 완전관측 + 주머니 카운팅. 은닉은 주머니 순서뿐.
- 마진 핵심: **한 수가 문양·색 두 그래프를 동시에 바꾼다** → ΔV = Δ(내 메트릭) − Δ(상대 메트릭)
  한 번의 place/unplace로 계산.

## 프로토콜 (finals_1 명세)

```text
READY (FIRST|SECOND)          → "OK" (3,000ms)
INIT A1..A5 B1..B5            (A=내 손패, B=상대 손패)
TIME t1 t2                    → "PUT p T" (t1ms 이내, 초기 10,000ms 게임당 총시간)
GET T                         (내 드로우, 없으면 X0)
OPP p T1 T2 t                 (상대 배치 T1@p, 상대 드로우 T2)
FINISH                        → 즉시 종료
```

## 사다리 (src/bots.hpp)

| 봇 | 전략 | 폭 (w_root/w_inner) | 역할 |
|----|------|----------------------|------|
| c1 | 최소 type 손패 → 최소 id 빈칸 | - | 바닥 앵커 |
| c2 | 자기 점수 최대 — 공식 순회: **타일(손패 도착순) outer × 칸(id asc) inner, strict >** | - | **공식 예제 재현** (sample-code.cpp 대조 확정) |
| c3 | 마진 ΔV 최대 | - | 핑크빈 역할 (1수 swing) |
| c4 | minimax d0 (내 수 + 상대 정적 최선) | ALL / - | 중간 방어 |
| c5 | minimax d1 | 24 / 12 | 중간 공격 |
| c6 | minimax d2 | 16 / 8 | 어려운 방어 |
| c7 | minimax d3 | 12 / 6 | 어려운 공격 |

사다리 외 추가 봇:

| 봇 | 정체 |
|----|------|
| s1 | **사이트 샘플 AI 레플리카** (2026-06-11 로그 섀도 32/32 일치). 정책 = 1-ply 마진 그리디, 순회 = 칸 outer(행우선: 행1→6×열a→f×−,+) × 타일 inner(손패 도착순), strict >. c3와 기력 동급, 타이브레이크만 다름. 회귀 게이트·사이트 예측용. 추가 로그 확보 시 `scripts/shadow_replay.py`로 재확증 |

- 버섯 AI4~7 구조 이식: 리프(depth 0) = 수 두는 쪽의 모든 수에 대한 정적 swing 스캔.
  Connexion엔 패스가 없으므로 stand-pat 없음 (수가 없을 때만 현재 마진 반환).
- 드로우는 탐색에서 무시 (손패 고정, 양측 공개라 결정론 유지). 정교한 기대값/ISMCTS는 메인 엔진 몫.
- 폭 제한은 10초 총시계 안에서 결정론을 지키기 위한 고정 상수. 시간 적응 금지 (시계를 읽되 쓰지 않는다).
- 동률 해소: (ΔV, cell asc, type asc) 전순서 → 완전 결정론. RNG 자체가 없다.

## 채점 하네스 (scripts/)

- `connexion_rules.py` — 파이썬 측 규칙 미러 (referee/테스트 공용). C++과 이중 구현이며 골든으로 핀 고정.
- `referee.py` — 서버 역할: 주머니 셔플(시드), 프로토콜 구동, 수 검증, 점수, JSONL 로그
  (`Log/SelfplayOracle/`). `pair`(2봇 N판) / `ladder`(c1~c7 × 선후 2판 = 14배틀, A: c1-c2 4판 /
  B: c3-c5 6판 / C: c6-c7 4판, "X승/14") 모드.
- `golden_test.py` — G2: 토폴로지(64칸, 인접 예시 c5-↔{c5+,b5+,c4+}, f4+↔{f4-,f5-}, 대칭) +
  finals_1 예시 보드 10타일 = **선공 24 / 후공 20** + C++ `--selftest` 호출.
- `ladder_check.py` — G3: 인접 티어 승률 단조성 (리포트 우선) / G4: 동일 시드 2회 = 동일 로그.
- `g1_check.py` — G1: 공식 sample-code 바이너리와 c2를 동일 입력 스트림으로 섀도 비교, 전 수 일치.

## 게이트 (완료 조건)

| 게이트 | 기준 |
|---|---|
| G1 규칙/예제 일치 | 공식 sample-code vs c2, 동일 스트림 전 수 일치 (불일치 시 c2 타이브레이크 보정) |
| G2 점수 골든 | 예시 보드 = 선공 24 / 후공 20, 토폴로지 검증 |
| G3 사다리 단조성 | 시드 배터리에서 상위 티어 승률 우위 (리포트, 임계 60% 권고) |
| G4 결정론 | 동일 시드 2회 → 수순 동일 |

## 빌드/실행

```bash
# WSL
g++ -O2 -std=c++20 -Wall -Wextra -o build/sample_ai src/sample_ai_main.cpp
./build/sample_ai --selftest
python3 scripts/golden_test.py --exe build/sample_ai
python3 scripts/referee.py pair --a "build/sample_ai c3" --b "build/sample_ai c2" --games 2 --seed-base 1
python3 scripts/referee.py ladder --target "build/sample_ai c7" --exe build/sample_ai --seed-base 100
python3 scripts/ladder_check.py --exe build/sample_ai
```

## 6/29 리스킨 플레이북

예선 문제 공개 시: ① core.hpp의 토폴로지/타일/점수 함수 교체 → ② 새 공식 예제 재현 = c2 교체(G1)
→ ③ c3~c7은 평가만 그대로 → ④ referee/게이트 무수정 재사용. Connexion 그대로면 ①~③ 생략.
