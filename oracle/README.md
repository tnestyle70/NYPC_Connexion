# Oracle

oracle은 느린 teacher이자 regret judge다.

첫 번째 운영 규칙:

```text
EXACT=1 label은 ground truth로 사용한다.
EXACT=0 label은 low-confidence hint로만 취급한다.
```

oracle의 역할:

```text
position 입력
-> 모든 legal action value 계산
-> best action 산출
-> played action과 비교
-> regret 계산
-> main.cpp의 판단 실패 원인 추적
```

처음에는 완전정보 endgame에서 `EXACT=1`을 확보하고, 이후 hidden information/belief search로 확장한다.

