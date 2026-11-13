#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""长循环运行器：在 runner 内连续跑约 5.5 小时，每 3 分钟一轮访问+提交。
全部目标跑满后立即退出且不续命；否则到点写 exit=42 让 rerun 步骤自我续命。"""
import subprocess, sys, time, os, json, glob

os.environ["TZ"] = "Asia/Shanghai"
time.tzset()
REPO = os.path.dirname(os.path.abspath(__file__))
os.chdir(REPO)

DURATION = 325 * 60      # 单次 job 循环时长（留余量给 setup 与 rerun）
INTERVAL = 180           # 目标访问周期
END = time.time() + DURATION


def mark(code):
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        with open(p, "a") as f:
            f.write(f"exit={code}\n")


def newest_visit_age():
    """全部日志里最新一条访问距今的秒数（无日志返回 None）"""
    newest = 0
    for p in glob.glob("log_*.jsonl"):
        try:
            with open(p, encoding="utf-8") as f:
                lines = [l for l in f.read().strip().split("\n") if l][-3:]
            for line in reversed(lines):
                ts = json.loads(line)["ts"]
                t = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
                newest = max(newest, t)
                break
        except Exception:
            pass
    return None if not newest else time.time() - newest


def commit_push(msg):
    subprocess.run(["git", "config", "user.name", "monitor-bot"])
    subprocess.run(["git", "config", "user.email", "monitor-bot@users.noreply.github.com"])
    subprocess.run(["git", "add", "-A"])
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return
    subprocess.run(["git", "commit", "-q", "-m", msg])
    for _ in range(3):
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], capture_output=True)
        pr = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
        if pr.returncode == 0:
            return
        print("push retry:", (pr.stderr or "")[-200:])
        time.sleep(15)


# 防堆积：若其他实例 10 分钟内仍在访问，本实例退出且不续命
age = newest_visit_age()
if age is not None and age < 600:
    print(f"SKIP: another instance active (last visit {age:.0f}s ago)")
    mark(0)
    sys.exit(0)

n = 0
while time.time() < END:
    n += 1
    t0 = time.time()
    r = subprocess.run([sys.executable, "monitor_once.py"], capture_output=True, text=True)
    print(f"--- round {n} rc={r.returncode}")
    if r.stdout:
        print(r.stdout.strip()[-600:])
    if r.returncode != 0 and r.stderr:
        print(r.stderr[-400:])

    if "ALL DONE" in (r.stdout or ""):
        commit_push(f"done: {time.strftime('%Y-%m-%d %H:%M')} [skip ci]")
        print("ALL TARGETS REACHED -> stop, no rerun")
        mark(0)
        sys.exit(0)

    commit_push(f"loop: {time.strftime('%Y-%m-%d %H:%M')} [skip ci]")
    dt = time.time() - t0
    time.sleep(max(15, INTERVAL - dt))

mark(42)
print(f"LOOP DONE after {n} rounds, rerun step will re-dispatch")
sys.exit(0)
