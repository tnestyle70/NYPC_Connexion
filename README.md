# NYPC Connexion

NYPC Connexion 게임을 처음부터 분석하고 강한 bot을 만들기 위한 clean-room 워크스페이스다.

핵심 방향:

```text
main.cpp
  = 빠른 제출 엔진
  = rules + connectivity features + evaluator + search/belief + time budget

data.bin
  = 오프라인에서 압축한 지식
  = 튜닝된 weight, pattern table, policy/value hint, opponent model cache

oracle
  = 느린 teacher / regret judge
  = EXACT=1이면 완전정보 또는 belief-expanded 정답 label
  = EXACT=0이면 budget-limited search/belief hint

pipeline
  = logs/self-play -> positions -> oracle value/regret -> feature/function update -> gate
```

Connexion은 연결 성분, 영역, 타일/배치, hidden information 또는 belief가 핵심일 가능성이 크다. 따라서 단순 greedy보다 `component value`, `threat/block`, `belief`, `ISMCTS/beam search`를 분리해서 설계한다.

## 폴더 구조

```text
main.cpp                  # 제출 형태를 유지하는 엔진 skeleton
src/                      # 로컬 실험용 분리 source
oracle/                   # 느린 oracle / regret judge
scripts/                  # log parsing, label export, analysis, gate
Log/
  WebSiteBot/             # 공식 웹사이트 봇 로그
  NationalOpp/            # 전국구/실전 상대 로그
  SelfplayOracle/         # self-play / oracle 대전 로그
data/
  boards/                 # seed, board, scenario set
  oracle_labels/          # state/action/value/regret jsonl
  reports/                # 분석 리포트와 gate 결과
  experiments/            # 임시 실험 상태
build/                    # 로컬 binary
```

## 첫 번째 원칙

대전 결과 자체는 학습 정답이 아니다.

```text
game/log result = position source
oracle exact/deep analysis = answer sheet
regret = learning signal
win rate = final gate
```

## Sample AI 사다리 (2026-06-11)

공식 "샘플 AI와의 대결" 채점의 로컬 미러. 설계와 게이트 정의: `.md/guide/04_SAMPLE_AI_LADDER.md`

```text
src/core.hpp            # 규칙 엔진 (64칸 u64 비트보드, 롤백 union-find 증분 그룹² 점수)
src/bots.hpp            # 사다리 c1~c7 (c2 = 공식 예제 코드와 전 수 일치, G1 검증)
src/sample_ai_main.cpp  # 프로토콜 실행기: build/sample_ai <c1..c7> | --selftest
scripts/referee.py      # 채점 하네스: pair / ladder(14배틀 "X승/14 (A/B/C)")
scripts/golden_test.py  # G2: 토폴로지 + 예시 보드(선공 24/후공 20)
scripts/ladder_check.py # G3 단조성 + G4 결정론
scripts/g1_check.py     # G1: 공식 sample-code 섀도 대조
docs/official_sample/   # 공식 예제 코드 보존 (cpp/rs)
```

전체 빌드+게이트 (WSL): `bash scripts/dev_smoke.sh`
게이트 현황: G1 8/8 일치, G2 PASS, G3 단조(0.75~1.00), G4 PASS, 타이밍 최대 16ms/수.

## 시각화 (2026-06-11)

`docs/visualizer.html` — 브라우저로 여는 오프라인 단일 페이지 시뮬레이터.

- AI vs AI 관전(c1/c2/c3/s1/c4, 시드·속도), 사람 vs AI 대국, **사이트 로그·referee JSONL 리플레이**
- 문양/색 연결 렌즈(Σn² 성분이 눈에 보임), 수별 Δ문양/Δ색 로그, 양측 손패·주머니 표시
- 엔진 = `docs/visualizer_engine.js` (C++ core.hpp 의 JS 미러).
  핀 고정: `node scripts/visualizer_engine_test.js` → 골든 24/20 + 사이트 로그 **196/304 재현**
  + **s1 섀도 32/32** (c3/c2 첫 불일치 위치까지 C++와 동일)

## 로컬 컨테스트 포털 (2026-06-11)

contest.nypc.co.kr/problems/1 의 로컬 미러 — 제출 → 컴파일 → **14배틀 채점** → 내역/재생.

```bash
# WSL (사전: bash scripts/dev_smoke.sh 로 build/sample_ai 빌드)
python3 scripts/contest_server.py --port 8733
# 브라우저: http://localhost:8733/problems/1
```

- 제출 탭: C++ 소스 붙여넣기/파일 → g++ 컴파일 → 사다리 c1~c7 × 선후공 = 14배틀 (고정 시드)
- 제출 내역: 배틀 테이블(내 결과/1P/2P, 시간), **▶ = 시뮬레이터 재생**, ⬇ = 로그 다운로드, 코드 보기
- 중간 평가 탭: 로컬 X승/14 (A/B/C) 지표
- E2E: `python3 scripts/portal_e2e.py` (공식 greedy 샘플 제출 → 3승/14, 사다리 서열 일치 확인)
- 저장: `data/experiments/submissions/<id>/` (gitignore 영역)

