# AGENTS.md

이 워크스페이스는 NYPC Connexion bot을 새로 설계하기 위한 clean-room lab이다.

## 목표

재현 가능한 competition AI pipeline을 만든다.

1. 공식 규칙을 정확히 구현한다.
2. 연결 성분, threat/block, hidden information 또는 belief를 분리해서 모델링한다.
3. `main.cpp`는 제출 가능한 형태로 작고 빠르게 유지한다.
4. oracle은 느린 teacher이자 regret judge로 사용한다.
5. log와 self-play는 position source로 사용하고, raw win-rate만으로 튜닝하지 않는다.

현재 방향은 아래 순서로 고정한다.

```text
rules correctness -> connectivity model -> move ordering -> search/ISMCTS -> endgame exact -> regret-based correction
```

feature 개수 자체가 핵심 레버가 아니다. 핵심은 봇이 왜 특정 placement/action을 선택했는지 설명할 수 있고, oracle과 비교한 뒤 어떤 변수/구조체/함수/클래스를 유지, 튜닝, 삭제, 추가해야 하는지 결정할 수 있는 구조다.

## 프로젝트 계약

- `main.cpp`는 빠른 student다.
- `oracle/`은 느린 teacher다.
- `data.bin`은 optional compressed knowledge다.
- `Log/WebSiteBot`, `Log/NationalOpp`, `Log/SelfplayOracle`은 replay 가능한 로그를 저장한다.
- `data/oracle_labels`는 오래 보존할 학습 자산을 저장한다.
- `.md/guide`는 구현 전에 설계와 코드 스니펫을 고정하는 공간이다.
- `CLAUDE.md`는 Claude와 병렬 작업할 때의 cross-agent 운영 규칙이다.

## 세션 메인 토픽

1. `main.cpp` bot 설계
   - 날짜별 bot snapshot은 `bot/MM-DD/bot_00`, `bot_01` 형태로 보관한다.
   - 구체화된 bot snapshot은 candidate `main.cpp`, design note, feature schema, validation report를 함께 보존한다.
   - 설계 계층은 Rules, Features, Evaluator, Search, LearningInterface다.

2. Oracle 설계
   - 완전정보로 풀 수 있는 구간은 `EXACT=1`로 terminal까지 푼다.
   - hidden information이 있으면 belief sample 또는 determinization을 명시하고 `EXACT=0`으로 분리한다.
   - oracle output에는 best action, played action value, regret, node/sample count, depth, exactness가 포함되어야 한다.

3. Log와 regret pipeline
   - raw log는 웹사이트 replay 가능한 형식을 유지한다.
   - 분석 파일은 sidecar로 둔다.
   - 모든 bot 변경은 regret case로 설명 가능해야 한다.

## 직접 반영 원칙

bot, oracle, regret pipeline을 설계할 때 Codex는 먼저 guide 문서와 코드 스니펫을 작성한다. 사용자가 검토하고 직접 반영하는 것을 원칙으로 한다. 단, 사용자가 명시적으로 구현 파일 생성/수정을 요청하면 Codex가 반영한다.

## 개발 순서

1. Rules engine: `State`, `Action`, legal actions, transition, scoring, terminal.
2. Connectivity engine: component, liberties, threat, block, region value.
3. Oracle/search: exact 가능한 구간부터 만들고, 이후 ISMCTS/beam을 실험한다.
4. Feature map: state features, action features, connectivity features, belief features.
5. Analysis: regret을 feature/function failure로 분류한다.
6. Compression: 안정적인 table/weight를 `main.cpp` 또는 `data.bin`으로 압축한다.

## 학습 규칙

raw win rate만 보고 튜닝하지 않는다.

```text
position -> oracle action values -> regret -> feature/function update -> holdout gate
```

`EXACT=1` oracle label은 true optimal result로 신뢰한다. `EXACT=0` label은 시간/노드/샘플 제한이 걸린 approximation이므로 low-confidence hint로만 취급한다.

