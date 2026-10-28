#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单次监控：由 GitHub Actions 每 5 分钟调度，两页各访问一次后把进度提交回仓库"""
import requests, re, time, json, os, random, os as _os
_os.environ["TZ"] = "Asia/Shanghai"
time.tzset()

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(REPO_DIR, "state.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
TOTALS = {"8089262": 500, "8089700": 600}
FINISH_MARKER = os.path.join(REPO_DIR, "FINISHED")

with open(STATE) as f:
    state = json.load(f)

if all(v <= 0 for v in state.values()):
    open(FINISH_MARKER, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
    print("ALL DONE")
    raise SystemExit(0)

session = requests.Session()
session.headers.update(HEADERS)

def fetch(tid, left):
    t0 = time.time()
    rec = {"seq": left, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        r = session.get(f"https://cbgc.scol.com.cn/news/{tid}", timeout=30)
        rec["status"] = r.status_code
        rec["ms"] = int((time.time() - t0) * 1000)
        m = re.search(r"<title>(.*?)</title>", r.text)
        rec["title"] = m.group(1)[:60] if m else ""
        c = re.search(r'comments_count">\s*(\d+)', r.text)
        rec["comments"] = int(c.group(1)) if c else None
        rec["bytes"] = len(r.content)
    except Exception as e:
        rec["status"] = "ERR"
        rec["error"] = str(e)[:120]
    with open(os.path.join(REPO_DIR, f"log_{tid}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"#{rec['seq']} id={tid} status={rec['status']} ms={rec.get('ms','')}")

for tid in list(state):
    if state[tid] > 0:
        fetch(tid, state[tid])
        state[tid] -= 1
        time.sleep(random.uniform(5, 15))

with open(STATE, "w") as f:
    json.dump(state, f)
if all(v <= 0 for v in state.values()):
    open(FINISH_MARKER, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
    print("ALL DONE")
