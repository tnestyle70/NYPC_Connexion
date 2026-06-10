# Log와 Regret Pipeline

## Raw Log 규칙

```text
Log/WebSiteBot/
Log/NationalOpp/
Log/SelfplayOracle/
```

raw log는 replay 가능하게 유지하고, 분석은 sidecar file로 둔다.

```text
game_000123.log
game_000123.oracle.csv
game_000123.regret.jsonl
game_000123.notes.md
```

## CSV Columns

```text
log_id,ply,side,phase,played,best_action,exact,legal_count,best_value,played_value,played_regret,nodes,samples,depth,reason_tags
```

## Reason Tags

```text
connectivity_miss
block_miss
threat_miss
belief_error
move_ordering
search_depth
endgame_exact_missing
feature_noise
new_function_needed
rules_mismatch
time_budget
```

