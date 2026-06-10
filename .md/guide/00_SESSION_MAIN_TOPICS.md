# 세션 메인 토픽

## 1. main.cpp Bot 설계

목표:

```text
rules correctness -> connectivity model -> move ordering -> search/ISMCTS -> endgame exact -> regret-based correction
```

`main.cpp`는 빠른 판단 주체다. 연결 성분, threat/block, hidden information 또는 belief를 분리해서 판단해야 한다.

## 2. Oracle 설계

oracle은 느린 teacher다.

```text
position input
-> legal action 생성
-> action 적용
-> recursive/beam/belief search
-> action value 계산
-> best action과 regret 보고
```

`EXACT=1`은 증명된 value label이고, `EXACT=0`은 budget-limited hint다.

## 3. Log와 Regret Pipeline

raw log는 replay 가능한 형식으로 유지한다.

```text
raw replay log
-> parsed positions
-> oracle analyze
-> played action regret
-> reason tags
-> bot update decision
```

