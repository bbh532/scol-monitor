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
with open(os.path.join(REPO_DIR, "articles.json")) as _af:
    TOTALS = {a["id"]: a["total"] for a in json.load(_af)["articles"]}
FINISH_MARKER = os.path.join(REPO_DIR, "FINISHED")

with open(STATE) as f:
    state = json.load(f)

# 防重入：距上一次访问不足 3 分钟则跳过（防止 schedule 与外部触发撞车）
def _last_ts(tid):
    try:
        with open(os.path.join(REPO_DIR, f"log_{tid}.jsonl")) as f:
            for line in reversed(f.readlines()):
                line = line.strip()
                if line:
                    return json.loads(line)["ts"]
    except Exception:
        return None

from datetime import datetime
_last = _last_ts("8109061") or _last_ts("8095497") or _last_ts("8089700") or _last_ts("8089262")
if _last:
    _dt = datetime.strptime(_last, "%Y-%m-%d %H:%M:%S")
    _age = (datetime.now() - _dt).total_seconds()
    if 0 <= _age < 110:
        print(f"SKIP: last visit only {_age:.0f}s ago")
        raise SystemExit(0)

from datetime import datetime as _d, timedelta as _t

_CFG = {a["id"]: a for a in json.load(open(os.path.join(REPO_DIR, "articles.json")))["articles"]}

def _t72(tid):
    p = _CFG.get(tid, {}).get("publish")
    if not p:
        return None
    return _d.strptime(p, "%Y-%m-%d %H:%M") + _t(hours=72)

def _active(tid):
    """该文章是否还需继续访问：跑满目标次数 且 已过 72h，两者都满足才停"""
    left = state.get(tid, 0)
    t = _t72(tid)
    if left > 0:
        return True            # 未跑满，继续（无论是否到 72h）
    if t is None:
        return False
    return _d.now() < t        # 已跑满但 72h 未到，继续

_active_ids = [tid for tid in state if _active(tid)]
if not _active_ids:
    open(FINISH_MARKER, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
    print("ALL DONE (all articles reached 72h)")
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

for tid in _active_ids:
    fetch(tid, state.get(tid, 0))
    if state.get(tid, 0) > 0:
        state[tid] = state[tid] - 1
    time.sleep(random.uniform(5, 15))

# ---- 发布后 72 小时快照（到达时记录一次，之后不再改动）----
try:
    _snap_path = os.path.join(REPO_DIR, "at72h.json")
    _snap = json.load(open(_snap_path)) if os.path.exists(_snap_path) else {}
    _arts_cfg = json.load(open(os.path.join(REPO_DIR, "articles.json")))["articles"]
    from datetime import datetime as _dt, timedelta as _td
    _now = _dt.now()
    _changed = False
    for _a in _arts_cfg:
        _tid = _a["id"]
        if not _a.get("publish"):
            continue
        _t72 = _dt.strptime(_a["publish"], "%Y-%m-%d %H:%M") + _td(hours=72)
        _rec = _snap.get(_tid, {})
        if _now >= _t72 and _rec.get("status") != "recorded":
            _p = os.path.join(REPO_DIR, f"log_{_tid}.jsonl")
            _n = 0
            if os.path.exists(_p):
                for _line in open(_p, encoding="utf-8"):
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        if _dt.strptime(json.loads(_line)["ts"], "%Y-%m-%d %H:%M:%S") <= _t72:
                            _n += 1
                    except Exception:
                        pass
            _snap[_tid] = {
                "publish": _a["publish"],
                "t72": _t72.strftime("%Y-%m-%d %H:%M"),
                "count_at_t72": _n,
                "recorded_at": _now.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "recorded",
            }
            _changed = True
            print(f"SNAPSHOT {_tid}: {_n} visits by {_t72}")
    if _changed:
        json.dump(_snap, open(_snap_path, "w"), ensure_ascii=False, indent=2)
except Exception as _e:
    print("snapshot err:", str(_e)[:120])

with open(STATE, "w") as f:
    json.dump(state, f)
if all(v <= 0 for v in state.values()):
    open(FINISH_MARKER, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
    print("ALL DONE")
