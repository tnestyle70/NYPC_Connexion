# Oracle 바닥부터 설계

## 목표

Connexion oracle은 특정 position에서 각 action의 value와 regret을 계산한다.

```text
AnalyzePosition(position, playedAction):
  actions = GenerateLegalActions(position)
  for action in actions:
    value = SearchOrBeliefSearch(position, action)
  bestValue = max(value)
  regret = bestValue - playedValue
```

## Exactness

- `EXACT=1`: 완전정보 game tree를 terminal까지 계산했다.
- `EXACT=0`: hidden information, sample, depth, node budget 때문에 일부만 계산했다.

## 필수 함수

```cpp
State ParsePosition(std::istream& input);
std::vector<ActionInfo> GenerateLegalActions(const State& state);
State ApplyAction(const State& state, const Action& action);
ConnectivityInfo BuildConnectivity(const State& state);
OracleValue Search(const State& state, int depth, OracleBudget& budget);
PositionAnalysis AnalyzePosition(const State& state, const std::optional<Action>& playedAction);
void PrintActionValues(const PositionAnalysis& analysis, std::ostream& output);
```

