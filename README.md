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

