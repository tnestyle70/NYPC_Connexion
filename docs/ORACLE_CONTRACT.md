# Oracle Contract

Connexion oracle은 마법의 정답기가 아니다.

oracle은 confidence에 따라 다르게 신뢰한다.

```text
EXACT=1
  완전정보 상태에서 terminal search가 끝났다
  best value와 move value가 game-theoretic label이다

EXACT=0
  hidden information, sample, time, depth, node budget에 걸렸다
  value는 estimate다
  low-confidence guidance로만 사용한다
```

## 필수 Oracle Output

```text
position_id
side_to_move
phase
legal_count
exact
best_value
best_actions
actions: action, value, regret
diagnostics: nodes, samples, depth, cap_hit, elapsed_ms
```

## Oracle 업그레이드 트랙

1. 공식 rule parity 확보.
2. board/state hashing.
3. connectivity/component cache.
4. deterministic node-budget mode.
5. exact endgame expansion.
6. beam search.
7. ISMCTS 또는 belief search.
8. `EXACT=0`에서 더 좋은 connectivity evaluator.

