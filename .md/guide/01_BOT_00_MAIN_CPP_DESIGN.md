# bot_00 main.cpp 설계

이 문서는 첫 Connexion bot snapshot을 사용자가 직접 반영하기 위한 guide다.

## 계층 지도

Rules:

- `State`
- `Action`
- `ActionInfo`
- `GenerateLegalActions`
- `ApplyAction`
- `Score`
- `IsTerminal`

Connectivity:

- `ComponentInfo`
- `RegionInfo`
- `ThreatInfo`
- `UpdateComponents`

Features:

- `StateFeatures`
- `ActionFeatures`
- `ConnectivityFeatures`
- `BeliefFeatures`

Evaluator:

- `RuntimeConfig`
- `EvaluateState`
- `ScoreAction`
- `ThreatPenalty`
- `BlockBonus`

Search:

- `RankActions`
- `AlphaBeta`
- `BeamSearch`
- `ISMCTS`
- `ExactEndgame`
- `TimeBudget`

LearningInterface:

- `FeatureName`
- `CurrentWeight`
- `Status`: `keep`, `tune`, `delete`, `add`
- `OracleRegretStats`

## 최소 C++ Skeleton

```cpp
enum class Player : int { First = 0, Second = 1 };
enum class FeatureStatus : int { Keep, Tune, Delete, Add };

struct Action {
    int type = 0;
    int r = 0;
    int c = 0;
    int tile = 0;
};

struct ActionInfo {
    Action action;
    int immediateValue = 0;
    int connectionGain = 0;
    int blockValue = 0;
    int threatRisk = 0;
    int orderingScore = 0;
};

struct State {
    int rows = 0;
    int cols = 0;
    int turn = 0;
    Player sideToMove = Player::First;
};
```

규칙이 확정되면 `State`에 board, tile bag, hidden/public info, score, pass state 등을 추가한다.

