#!/usr/bin/env bash
# Sample AI 사다리 스모크 + 게이트 러너 (WSL)
# 사용: bash scripts/dev_smoke.sh
set -e
cd "$(dirname "$0")/.."

echo "=== build ==="
g++ -O2 -std=c++20 -Wall -Wextra -o build/sample_ai src/sample_ai_main.cpp
g++ -O2 -std=c++20 -o build/official_sample docs/official_sample/sample-code.cpp
ls -la build/

echo
echo "=== G2: selftest + golden ==="
./build/sample_ai --selftest
python3 scripts/golden_test.py --exe build/sample_ai

echo
echo "=== smoke: c3 vs c2 (2판) ==="
python3 scripts/referee.py pair --a "build/sample_ai c3" --b "build/sample_ai c2" --games 2 --seed-base 1

echo
echo "=== G3 + G4: ladder_check (시드 2) ==="
python3 scripts/ladder_check.py --exe build/sample_ai --seeds 2

echo
echo "=== G1: 공식 sample-code vs c2 섀도 대조 (시드 4 x 선후) ==="
python3 scripts/g1_check.py --official build/official_sample --shadow "build/sample_ai c2" --sparring "build/sample_ai c3" --seeds 4
