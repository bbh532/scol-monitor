#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成静态看板 docs/index.html，由 GitHub Pages 托管，不依赖任何云函数"""
import json, os, time
os.environ["TZ"] = "Asia/Shanghai"
time.tzset()
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(REPO, "docs")
os.makedirs(DOCS, exist_ok=True)


def load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


articles = load(os.path.join(REPO, "articles.json"), {"articles": []})["articles"]
state = load(os.path.join(REPO, "state.json"), {})
snap = load(os.path.join(REPO, "at72h.json"), {})
now = datetime.now()

rows = []
done_all = 0
reached72 = 0
total_visits = 0
for a in articles:
    tid, total = a["id"], a["total"]
    log_p = os.path.join(REPO, f"log_{tid}.jsonl")
    cnt = ok = 0
    last = None
    if os.path.exists(log_p):
        with open(log_p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                cnt += 1
                if r.get("status") == 200:
                    ok += 1
                last = r
    pct = min(100.0, cnt * 100.0 / total) if total else 0
    total_visits += cnt

    t72 = None
    left72_txt, left72_cls = "—", "un72"
    if a.get("publish"):
        try:
            t72 = datetime.strptime(a["publish"], "%Y-%m-%d %H:%M") + timedelta(hours=72)
        except Exception:
            t72 = None
    stopped = bool(a.get("stopped"))
    if stopped:
        left72_txt, left72_cls = "已停止", "stop"
    elif t72:
        delta = (t72 - now).total_seconds()
        if delta > 0:
            h, m = int(delta // 3600), int(delta % 3600 // 60)
            left72_txt, left72_cls = f"还有 {h}h{m:02d}m", "pend"
        else:
            left72_txt, left72_cls = "已到点", "ok72"
            reached72 += 1

    snap_v = snap.get(tid, {}).get("count_at_t72")
    snap_txt = f"{snap_v} 次" if snap_v is not None else "待记录"

    if cnt >= total and t72 and now >= t72:
        done_all += 1

    st = last.get("status") if last else "-"
    ms = last.get("ms", "") if last else ""
    st_cls = "ok" if st == 200 else ("err" if st not in (200, "-") else "")
    rows.append(f"""<tr>
<td class="mono">{tid}</td>
<td>{a.get('title','')}</td>
<td><div class="bar"><div style="width:{pct:.1f}%"></div></div><span class="pct">{pct:.1f}%</span></td>
<td class="num">{cnt}<span class="dim"> / {total}</span></td>
<td class="num">{max(0, total - cnt)}</td>
<td class="{left72_cls}">{left72_txt}</td>
<td class="{st_cls}">{st}{(' · ' + str(ms) + 'ms') if ms != '' else ''}</td>
<td class="mono dim">{last.get('ts','-') if last else '-'}</td>
<td class="num">{snap_txt}</td>
</tr>""")

html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>川观新闻监控看板</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:system-ui,'Microsoft YaHei',sans-serif;background:#f5f7fa;margin:0;padding:22px;color:#1b2330}}
h1{{font-size:19px;margin:0 0 4px}}
.sub{{color:#6b7480;font-size:13px;margin:0 0 18px}}
.kpi{{display:flex;gap:14px;margin-bottom:16px;flex-wrap:wrap}}
.card{{background:#fff;border-radius:10px;padding:12px 18px;box-shadow:0 1px 4px rgba(0,0,0,.07);min-width:132px}}
.card .v{{font-size:22px;font-weight:650;color:#1e64d5}}
.card .k{{font-size:12px;color:#6b7480;margin-top:2px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
th,td{{padding:10px;font-size:13px;text-align:left;border-bottom:1px solid #eef1f5;vertical-align:middle}}
th{{background:#1e64d5;color:#fff;font-weight:600;font-size:12.5px;white-space:nowrap}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#f8fafd}}
.mono{{font-variant-numeric:tabular-nums;font-family:ui-monospace,Menlo,monospace;font-size:12.5px}}
.num{{font-variant-numeric:tabular-nums;white-space:nowrap}}
.dim{{color:#98a2b0;font-size:12px}}
.bar{{width:86px;height:8px;background:#e5e9f0;border-radius:4px;display:inline-block;vertical-align:middle;margin-right:6px}}
.bar div{{height:100%;background:linear-gradient(90deg,#4b8ef1,#1e64d5);border-radius:4px}}
.pct{{font-size:12px;color:#455}}
.stop{{color:#8a8f99;font-weight:600}} .ok{{color:#0a7d33}} .err{{color:#c93636}} .pend{{color:#b7791f}} .ok72{{color:#0a7d33}}
.foot{{margin-top:14px;color:#98a2b0;font-size:12px}}
</style></head><body>
<h1>川观新闻文章监控看板</h1>
<p class="sub">执行引擎：GitHub Actions · 数据时间 {now.strftime('%Y-%m-%d %H:%M:%S')} · 页面每 2 分钟自动刷新</p>
<div class="kpi">
<div class="card"><div class="v">{len(articles)}</div><div class="k">监控文章</div></div>
<div class="card"><div class="v">{reached72}</div><div class="k">已过 72h</div></div>
<div class="card"><div class="v">{done_all}</div><div class="k">跑满且过 72h</div></div>
<div class="card"><div class="v">{total_visits}</div><div class="k">累计访问次数</div></div>
</div>
<table><tr>
<th>文章ID</th><th>标题</th><th>进度</th><th>已访问次数</th><th>距目标</th><th>距发布 72h</th><th>最近状态</th><th>最近访问</th><th>72h 时点累计</th>
</tr>
{''.join(rows)}
</table>
<p class="foot">停止规则：跑满目标次数 <b>且</b> 已过发布后 72 小时，两者都满足才停止。跑满后仍按节奏继续访问，直至 72h 节点。</p>
<script>setTimeout(function(){{location.replace('?t='+Date.now())}},120000)</script>
</body></html>"""

with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("board written", len(html), "bytes")
