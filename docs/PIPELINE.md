# Connexion Pipeline

## 올바른 방향

```text
rules-derived engine design
-> official bot / national opponent / self-play oracle 대전
-> official-format logs
-> replay into positions
-> oracle ANALYZE
-> value/regret labels
-> 나쁜 판단 분류
-> 변수, 구조체, 함수, 클래스 add/delete/keep/tune
-> fixed-depth holdout
-> official-style gate
-> main.cpp 또는 data.bin으로 bake
```

## 각 log source의 의미

`WebSiteBot`:
공식 웹사이트 봇 로그다. public baseline과 회귀 확인에 좋다.

`NationalOpp`:
전국구/실전 상대 로그다. 까다로운 연결/차단/위협 패턴을 찾는 데 좋다.

`SelfplayOracle`:
oracle 또는 현재 best pool과 생성한 대전 로그다. 많은 position을 싸게 만들 수 있다.

## 중요한 구분

```text
logs produce questions
oracle produces answer sheets
regret produces training signal
gates decide promotion
```

## 승급 근거

- illegal action 0
- timeout/fault 0
- labeled position에서 oracle regret 감소
- fixed holdout에서 회귀 없음
- official-style board/seed gate에서 개선

