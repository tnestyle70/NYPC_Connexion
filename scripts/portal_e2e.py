#!/usr/bin/env python3
"""포털 E2E: 소스 제출 → 채점 → 내역/로그 API 왕복 확인.

사용 (WSL, contest_server 가동 중이어야 함):
  python3 scripts/portal_e2e.py [--src docs/official_sample/sample-code.cpp] [--port 8733]
"""
import argparse
import json
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--src", default="docs/official_sample/sample-code.cpp")
ap.add_argument("--port", type=int, default=8733)
ap.add_argument("--note", default="E2E: official greedy sample")
args = ap.parse_args()
base = f"http://localhost:{args.port}"

src = open(args.src, encoding="utf-8").read()
body = json.dumps({"source": src, "note": args.note}).encode()
req = urllib.request.Request(base + "/api/submit", data=body,
                             headers={"Content-Type": "application/json"})
meta = json.load(urllib.request.urlopen(req, timeout=560))
if "error" in meta:
    raise SystemExit("submit error: " + meta["error"])
print("id:", meta["id"], "| compile:", meta["compile"], "| wins:", meta.get("wins"))
print("groups:", meta.get("groups"))
for b in meta.get("battles", []):
    print(f'  battle {b["no"]:>2} vs {b["tier"]} ({"선공" if b["my_seat"]==0 else "후공"}): '
          f'{b["result"]}  {b["score_first"]}:{b["score_second"]}  '
          f'⏱ {b["ms_first"]}ms/{b["ms_second"]}ms' + (f'  fault={b["fault"]}' if b["fault"] else ""))

subs = json.load(urllib.request.urlopen(base + "/api/submissions", timeout=30))
print("submissions:", len(subs), "| 최신:", subs[0]["id"], subs[0]["wins"], "승")
log1 = urllib.request.urlopen(f"{base}/api/log/{meta['id']}/1", timeout=30).read().decode()
rec = json.loads(log1)
print("log battle1: moves", len(rec["moves"]), "| hands0", "OK" if rec.get("hands0") else "없음",
      "| score", rec["score_first"], rec["score_second"])
print("E2E OK")
