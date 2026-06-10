# main.cpp Architecture

`main.cpp`는 제출 가능한 단일 파일 형태를 유지하되, 내부적으로는 계층을 분리한다.

## 계층

```text
Rules
  State
  Action
  ActionInfo
  GenerateLegalActions
  ApplyAction
  Score
  IsTerminal

Connectivity
  Components
  Liberties
  Threats
  Blocks
  Regions

Features
  StateFeatures
  ActionFeatures
  ConnectivityFeatures
  BeliefFeatures
  ExtractStateFeatures
  ExtractActionFeatures

Evaluator
  RuntimeConfig
  EvaluateState
  ScoreAction
  ThreatPenalty
  BlockBonus

Search
  SearchConfig
  TimeBudget
  RankActions
  AlphaBeta/Beam/ISMCTS
  ExactEndgame
  TranspositionTable

Learning Interface
  FeatureSchema
  FeatureStatus: keep/tune/delete/add
  OracleRegretStats
```

## 판단 단위

```text
state
-> legal actions
-> connectivity features
-> action ordering
-> search/belief search
-> leaf evaluation
-> root adjustment
-> final action
```

학습 pipeline은 위 단계 중 어디가 실패했는지 말할 수 있어야 한다.

