# Scripts

계획 중인 scripts:

- `collect_logs.py`: official-format log를 `Log/*` 아래로 정규화한다.
- `export_positions.py`: log를 replay해서 state/action position을 뽑는다.
- `run_oracle_analyze.py`: oracle을 호출해서 value/regret label을 저장한다.
- `analyze_regret.py`: 나쁜 판단을 feature/function failure로 분류한다.
- `gate_candidate.py`: fixed holdout과 official-style gate를 실행한다.

```text
raw log -> positions -> oracle analysis -> regret report -> bot update decision
```

