# CLAUDE.md

이 파일은 Claude가 이 repository에서 작업할 때 따라야 하는 cross-agent 규칙이다.

## 먼저 읽을 것

1. `AGENTS.md`
2. `README.md`
3. `docs/MAIN_ARCHITECTURE.md`
4. `docs/ORACLE_CONTRACT.md`
5. `docs/PIPELINE.md`
6. 작업 대상 파일

## 작업 원칙

- `main.cpp`는 champion/submission-shaped file로 취급한다.
- 사용자가 명시적으로 요청하지 않으면 `main.cpp`를 직접 덮어쓰지 않는다.
- 실험 후보는 `bot/MM-DD/bot_00`, `bot_01`처럼 snapshot으로 보존한다.
- Codex, Claude, 사용자의 변경을 되돌리지 않는다.
- raw log는 replay 가능한 format을 유지한다.
- 분석 결과는 sidecar file로 둔다.

## 병렬 작업 규칙

- 같은 파일을 동시에 크게 수정하지 않는다.
- 다른 agent가 만든 변경은 먼저 읽고 이해한다.
- 충돌이 나면 성능보다 재현성과 기록 보존을 우선한다.
- 승급은 regret report와 holdout gate를 통과했을 때만 한다.

## Connexion 특이점

- 연결 성분과 threat/block 판단을 분리한다.
- hidden information이 있으면 belief와 actual state를 섞지 않는다.
- oracle의 `EXACT=1`과 `EXACT=0`을 반드시 구분한다.

