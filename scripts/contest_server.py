#!/usr/bin/env python3
"""로컬 NYPC 컨테스트 포털 백엔드 — contest.nypc.co.kr/problems/1 의 Connexion판 미러.

제출(C++ 소스) → g++ 컴파일 → 사다리 c1~c7 × 선후공 = 14배틀 채점(고정 시드) →
제출 내역/배틀 테이블/로그 다운로드/시뮬레이터 재생.

실행 (WSL — g++ 와 build/sample_ai 가 리눅스 바이너리):
  python3 scripts/contest_server.py --port 8733
브라우저: http://localhost:8733/problems/1

저장 위치 (gitignore 영역):
  data/experiments/submissions/<id>/  source.cpp, meta.json, battle_<n>.jsonl
  build/submissions/<id>/main         컴파일 산출물
"""

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from referee import LADDER_TIERS, TIER_GROUP, play_game, points  # noqa: E402

DOCS = ROOT / "docs"
SUB_DIR = ROOT / "data" / "experiments" / "submissions"
BUILD_DIR = ROOT / "build" / "submissions"
SAMPLE_AI = str(ROOT / "build" / "sample_ai")

TIER_DESC = {
    "c1": "최소 타일을 최소 칸에 (바닥)",
    "c2": "자기 점수 그리디 (공식 예제 동작)",
    "c3": "1수 마진 그리디",
    "c4": "minimax d0 (중간 방어)",
    "c5": "minimax d1 (중간 공격)",
    "c6": "minimax d2 (어려운 방어)",
    "c7": "minimax d3 (어려운 공격)",
}

# 배틀 1..14 = c1~c7 × (제출봇 선공, 후공). 시드 고정 — "항상 고정된 입력" (공식 규칙 동일)
BATTLES = []
for _i, _tier in enumerate(LADDER_TIERS):
    BATTLES.append({"no": 2 * _i + 1, "tier": _tier, "target_first": True, "seed": 1000 + 2 * _i})
    BATTLES.append({"no": 2 * _i + 2, "tier": _tier, "target_first": False, "seed": 1001 + 2 * _i})

GROUP_MAX = {"A": 4, "B": 6, "C": 4}


def grade(sub_id, note, source):
    sdir = SUB_DIR / sub_id
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "source.cpp").write_text(source, encoding="utf-8")
    bdir = BUILD_DIR / sub_id
    bdir.mkdir(parents=True, exist_ok=True)
    exe = bdir / "main"

    meta = {
        "id": sub_id,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": note or "",
        "lang": "C++20 (g++, WSL)",
        "battles": [],
        "wins": 0.0,
        "groups": {g: [0.0, GROUP_MAX[g]] for g in "ABC"},
    }

    cp = subprocess.run(
        ["g++", "-O2", "-std=c++20", "-o", str(exe), str(sdir / "source.cpp")],
        capture_output=True, text=True, timeout=180,
    )
    if cp.returncode != 0:
        meta["compile"] = "error"
        meta["compile_msg"] = cp.stderr[-4000:]
        (sdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return meta
    meta["compile"] = "ok"

    for b in BATTLES:
        tier_cmd = f"{SAMPLE_AI} {b['tier']}"
        if b["target_first"]:
            cf, cs = str(exe), tier_cmd
        else:
            cf, cs = tier_cmd, str(exe)
        r = play_game(cf, cs, b["seed"])
        my_seat = 0 if b["target_first"] else 1
        p = points(r, my_seat)
        ms = [sum(m["ms"] for m in r["moves"] if m["seat"] == s) for s in (0, 1)]
        entry = {
            "no": b["no"], "tier": b["tier"], "desc": TIER_DESC[b["tier"]],
            "my_seat": my_seat, "points": p,
            "result": "승리" if p == 1.0 else "무승부" if p == 0.5 else "패배",
            "score_first": r["score_first"], "score_second": r["score_second"],
            "ms_first": ms[0], "ms_second": ms[1],
            "fault": r["fault"],
        }
        meta["battles"].append(entry)
        meta["wins"] += p
        g = TIER_GROUP[b["tier"]]
        meta["groups"][g][0] += p
        (sdir / f"battle_{b['no']}.jsonl").write_text(
            json.dumps(r, ensure_ascii=False) + "\n", encoding="utf-8")

    (sdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def list_submissions():
    out = []
    if SUB_DIR.exists():
        for d in SUB_DIR.iterdir():
            mp = d / "meta.json"
            if mp.exists():
                try:
                    m = json.loads(mp.read_text(encoding="utf-8"))
                    out.append({k: m.get(k) for k in
                                ("id", "ts", "note", "lang", "compile", "wins", "groups")})
                except Exception:
                    pass
    out.sort(key=lambda m: m.get("ts") or "", reverse=True)
    return out


CTYPE = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".jsonl": "application/json; charset=utf-8",
         ".json": "application/json; charset=utf-8", ".md": "text/plain; charset=utf-8",
         ".svg": "image/svg+xml"}
ID_RE = re.compile(r"^[0-9a-f]{8}$")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def log_message(self, fmt, *args):
        sys.stderr.write("[portal] " + (fmt % args) + "\n")

    def do_GET(self):
        path = self.path.split("?")[0]
        q = self.path.split("?")[1] if "?" in self.path else ""
        if path in ("/", "/problems/1"):
            return self._send(200, (DOCS / "portal.html").read_bytes(), CTYPE[".html"])
        if path == "/api/submissions":
            return self._json(list_submissions())
        m = re.match(r"^/api/submission/([0-9a-f]{8})$", path)
        if m:
            mp = SUB_DIR / m.group(1) / "meta.json"
            if mp.exists():
                return self._send(200, mp.read_bytes(), CTYPE[".json"])
            return self._json({"error": "not found"}, 404)
        m = re.match(r"^/api/source/([0-9a-f]{8})$", path)
        if m:
            sp = SUB_DIR / m.group(1) / "source.cpp"
            if sp.exists():
                return self._send(200, sp.read_bytes(), "text/plain; charset=utf-8")
            return self._json({"error": "not found"}, 404)
        m = re.match(r"^/api/log/([0-9a-f]{8})/(\d+)$", path)
        if m:
            lp = SUB_DIR / m.group(1) / f"battle_{m.group(2)}.jsonl"
            if lp.exists():
                extra = {}
                if "dl=1" in q:
                    extra["Content-Disposition"] = \
                        f"attachment; filename=connexion_{m.group(1)}_b{m.group(2)}.jsonl"
                return self._send(200, lp.read_bytes(), CTYPE[".jsonl"], extra)
            return self._json({"error": "not found"}, 404)
        # 정적 파일 (docs/) — visualizer 등
        target = (DOCS / path.lstrip("/")).resolve()
        if target.is_file() and str(target).startswith(str(DOCS.resolve())):
            return self._send(200, target.read_bytes(),
                              CTYPE.get(target.suffix, "application/octet-stream"))
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/submit":
            return self._json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8"))
            source = body.get("source", "")
            if not source.strip():
                return self._json({"error": "소스가 비었습니다"}, 400)
            sub_id = uuid.uuid4().hex[:8]
            meta = grade(sub_id, body.get("note", ""), source)
            return self._json(meta)
        except Exception as e:  # 채점기 예외는 클라이언트에 그대로 보고
            return self._json({"error": f"server error: {e}"}, 500)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8733)
    args = ap.parse_args()
    if not Path(SAMPLE_AI).exists():
        print("경고: build/sample_ai 없음 — 먼저 bash scripts/dev_smoke.sh 로 빌드하세요")
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Connexion 컨테스트 포털: http://localhost:{args.port}/problems/1")
    srv.serve_forever()


if __name__ == "__main__":
    main()
