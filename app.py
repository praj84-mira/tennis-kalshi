"""Local dashboard. Runs the monitor loop in a background thread and serves a
one-page UI: live gaps, point-level spot check, trade log, backtest report.

    python app.py            # http://127.0.0.1:8765
    python app.py --port 9000

No order code. Each row links to the market on kalshi.com; the order is one
tap there, and the trade is logged here first (standing rule).
"""
import argparse
import csv
import html
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import monitor
from fair import pair, pt
from tennis_markov import fair_and_update, solve_d
from backtest import REPORT

STATE = {"rows": [], "ts": None, "err": None, "n_espn": 0, "unmatched": 0}
TRADES = os.path.join(monitor.DATA, "trades.csv")
TCOLS = ["ts", "ticker", "side", "price", "contracts", "fair", "mid", "score", "reason"]
SLUG = {"KXATPMATCH": "atp-tennis-match", "KXWTAMATCH": "wta-tennis-match"}


def kalshi_url(event_ticker):
    series = event_ticker.split("-")[0]
    return f"https://kalshi.com/markets/{series.lower()}/{SLUG.get(series, series.lower())}/{event_ticker.lower()}"


def loop(interval):
    anchors, servers = monitor.load(monitor.ANCHORS, {}), monitor.load(monitor.SERVERS, {})
    os.makedirs(monitor.DATA, exist_ok=True)
    new = not os.path.exists(monitor.LOG)
    while True:
        try:
            rows, n, unmatched = monitor.tick(anchors, servers, lambda *a: print(*a, file=sys.stderr))
            with open(monitor.LOG, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=monitor.COLS, extrasaction="ignore")
                if new:
                    w.writeheader()
                    new = False
                w.writerows(rows)
            monitor.save(monitor.ANCHORS, anchors)
            monitor.save(monitor.SERVERS, servers)
            STATE.update(rows=rows, ts=datetime.now(timezone.utc).strftime("%H:%M:%SZ"), err=None, n_espn=n, unmatched=len(unmatched))
        except Exception as e:  # noqa: BLE001
            STATE["err"] = repr(e)
            traceback.print_exc()
        time.sleep(interval)


def read_trades():
    if not os.path.exists(TRADES):
        return []
    with open(TRADES) as f:
        return list(csv.DictReader(f))


PAGE = r"""<!doctype html><meta charset=utf-8><title>usopen-fairvalue</title>
<style>
body{font:14px/1.4 -apple-system,system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
header{padding:10px 16px;background:#161a22;display:flex;gap:18px;align-items:baseline;border-bottom:1px solid #2a2f3a}
header b{font-size:16px}header span{color:#9aa}
main{padding:12px 16px;max-width:1300px}
table{border-collapse:collapse;width:100%;margin:8px 0}th,td{padding:5px 8px;text-align:right;border-bottom:1px solid #22262e;white-space:nowrap}
th{color:#9aa;font-weight:500;text-align:right}td.l,th.l{text-align:left}
.pos{color:#6fd18c}.neg{color:#f08a7e}.big{font-weight:700}.dim{color:#778}
a{color:#7ab8ff;text-decoration:none}a:hover{text-decoration:underline}
section{margin:16px 0;padding:12px;background:#161a22;border:1px solid #2a2f3a;border-radius:6px}
h2{font-size:14px;margin:0 0 8px;color:#bcc}
input,select{background:#0f1115;color:#eee;border:1px solid #333;padding:4px 6px;border-radius:4px;width:80px}
input.w{width:320px}button{background:#2b5fd9;color:#fff;border:0;padding:5px 12px;border-radius:4px;cursor:pointer}
pre{white-space:pre;overflow-x:auto;font-size:12px;background:#0f1115;padding:10px;border-radius:4px}
.warn{color:#ffb454}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.v{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600}.v-act{background:#1f5c35;color:#9ff0b6}.v-look{background:#5c4a1f;color:#ffd58a}.v-walk{background:#2a2f3a;color:#9aa}
tr.hy td{white-space:normal;text-align:left;color:#cfd3da;background:#12151c;padding:6px 14px 8px 28px}tr.hy li{margin:2px 0}tr.hy b{font-size:11px;margin-right:6px}
</style>
<header><b>usopen-fairvalue</b><span id=st>starting…</span><span class=dim>read-only · fair = score-only model anchored to pre-match price · gap = fair − mid · upd = serve-pts the market re-rated A</span></header>
<main>
<section><h2>Live</h2><div id=live class=dim>waiting for first tick…</div>
<div class=dim>Read: big gap + small upd → disagreement about score mechanics, worth a look. Big gap + big upd → market thinks someone is playing differently; model has no opinion. "?" server → fair averaged over both. Standing rule: no taker entries 45–55¢.</div></section>

<section><h2>Spot check (point score inside a game; ESPN doesn't carry it)</h2>
<form id=ff class=row onsubmit="return spot(event)">
tour <select name=tour><option>ATP<option>WTA</select>
best-of <input name=best_of value=5 size=2>
anchor <input name=anchor placeholder=0.92>
sets <input name=sets value=0-0> games <input name=games value=0-0>
server <select name=server><option>A<option>B<option>?</select>
pts <input name=pts value=0-0 placeholder=30-40> tb <input name=tb placeholder=5-8>
mid <input name=mid placeholder=0.67>
<button>compute</button></form><pre id=fout class=dim>—</pre></section>

<section><h2>Trade log (log it BEFORE the match resolves)</h2>
<form id=tf class=row onsubmit="return trade(event)">
ticker <input name=ticker class=w placeholder=KXATPMATCH-26SEP03BERDEJ-BER>
side <select name=side><option>yes<option>no</select>
price <input name=price placeholder=0.31> contracts <input name=contracts value=10>
reason <input name=reason class=w placeholder="why, in one line">
<button>log</button></form><div id=tout></div><div id=trades></div></section>

<section><h2>Backtest report <span class=dim>(python backtest.py fetch && python backtest.py analyze)</span></h2><pre id=rep class=dim>—</pre></section>
<section><h2>Settle <button onclick="settle()">run settle.py --min-gap 0.05</button></h2><pre id=sout class=dim>—</pre></section>
</main>
<script>
const $=s=>document.querySelector(s);
const f=(v,p=2)=>(v===''||v==null)?'':Number(v).toFixed(p);
const cls=v=>v===''?'':(Number(v)>0?'pos':'neg');
async function live(){
  const d=await (await fetch('/api/live')).json();
  $('#st').textContent=(d.ts?`tick ${d.ts} · live ${d.rows.length} · espn ${d.n_espn} · kalshi unmatched ${d.unmatched}`:'starting…')+(d.err?` · ERROR ${d.err}`:'');
  if(!d.rows.length){$('#live').textContent='no live singles matches matched right now';return}
  d.rows.sort((a,b)=>Math.abs(b.gap||0)-Math.abs(a.gap||0));
  let h='<table><tr><th class=l>match (A v B)</th><th class=l>score</th><th>sv</th><th>bid</th><th>ask</th><th>anchor</th><th>fair</th><th>gap</th><th>upd</th><th>vol</th><th>book</th><th>age</th><th></th><th></th></tr>';
  for(const r of d.rows){
    const sc=`${r.sets_a}-${r.sets_b} ${r.games_a}-${r.games_b}`+(r.tb_a!==''?` (${r.tb_a}-${r.tb_b})`:'');
    const big=Math.abs(r.gap||0)>=0.05&&Math.abs(r.update_pts||0)<1.5;
    const sv=r.server==='?'&&r.fair_if_a_serves!==''?` <span class=dim title="fair if A serves / if B serves">${f(r.fair_if_a_serves)}/${f(r.fair_if_b_serves)}</span>`:'';
    const age=r.score_age_s!==''?`${Math.round(r.score_age_s/60)}m`:'';
    h+=`<tr><td class=l><a href="${r.url}" target=_blank>${r.a}</a> v ${r.b} <span class=dim>${r.tour} ${r.round||''}${r.bases?' · profiles':''}</span></td><td class=l>${sc}</td><td>${r.server}</td><td>${f(r.bid)}</td><td>${f(r.ask)}</td><td>${f(r.anchor)} <span class=dim>${r.anchor_src==='trade'?'':r.anchor_src||''}</span></td><td>${f(r.fair)}${sv}</td><td class="${cls(r.gap)} ${big?'big':''}">${f(r.gap,3)}</td><td class="${cls(r.update_pts)}">${f(r.update_pts,1)}</td><td>${f(r.volume,0)}</td><td class=dim>${f(r.bid_size,0)}/${f(r.ask_size,0)}</td><td class=dim>${age}</td><td><span class="v v-${r.verdict}">${r.verdict}</span></td><td><a href=# onclick="pre('${r.ticker_a}',${r.ask});return false">log</a></td></tr>`;
    h+=`<tr class=hy><td colspan=14><ul style="margin:0;padding-left:14px">${(r.hypotheses||[]).map(([s,t])=>`<li><b class="v v-${s}">${s}</b>${t}</li>`).join('')}</ul></td></tr>`;}
  $('#live').innerHTML=h+'</table>';
}
function pre(t,p){const tf=$('#tf');tf.ticker.value=t;tf.price.value=p;tf.reason.focus()}
async function spot(e){e.preventDefault();const q=new URLSearchParams(new FormData($('#ff')));$('#fout').textContent=await (await fetch('/api/fair?'+q)).text();return false}
async function trade(e){e.preventDefault();const fd=new FormData($('#tf'));const p=Number(fd.get('price'));
  if(p>=0.45&&p<=0.55&&!confirm('45–55¢ is the max-fee coin-flip zone. Standing rule says no taker entries here. Log anyway?'))return false;
  const r=await fetch('/api/trade',{method:'POST',body:new URLSearchParams(fd)});$('#tout').textContent=await r.text();trades();return false}
async function trades(){const t=await (await fetch('/api/trades')).json();if(!t.length){$('#trades').innerHTML='<span class=dim>no trades logged</span>';return}
  let h='<table><tr><th class=l>ts</th><th class=l>ticker</th><th>side</th><th>px</th><th>n</th><th>fair</th><th>mid</th><th class=l>score</th><th class=l>reason</th></tr>';
  for(const r of t.reverse())h+=`<tr><td class=l>${r.ts}</td><td class=l>${r.ticker}</td><td>${r.side}</td><td>${r.price}</td><td>${r.contracts}</td><td>${r.fair}</td><td>${r.mid}</td><td class=l>${r.score}</td><td class=l>${r.reason}</td></tr>`;$('#trades').innerHTML=h+'</table>'}
async function report(){$('#rep').textContent=await (await fetch('/api/report')).text()}
async function settle(){$('#sout').textContent='running…';$('#sout').textContent=await (await fetch('/api/settle')).text()}
live();trades();report();setInterval(live,30000);
</script>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="text/plain; charset=utf-8", code=200):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/":
            return self.send(PAGE, "text/html; charset=utf-8")
        if u.path == "/api/live":
            rows = [dict(r, url=kalshi_url(r["event_ticker"])) for r in STATE["rows"]]
            return self.send(json.dumps(dict(STATE, rows=rows)), "application/json")
        if u.path == "/api/fair":
            try:
                tour = q.get("tour", "ATP")
                best_of = int(q.get("best_of") or (5 if tour == "ATP" else 3))
                anchor = float(q["anchor"])
                server = None if q.get("server", "?") == "?" else "AB".index(q["server"])
                d_pre = solve_d(tour, best_of, anchor, server=None)
                state = {"sets": pair(q.get("sets") or "0-0"), "games": pair(q.get("games") or "0-0"), "server": server,
                         "pts": pair(q.get("pts") or "0-0", pt), "tb_pts": pair(q["tb"]) if q.get("tb") else None}
                mid = float(q["mid"]) if q.get("mid") else None
                fair, d_live, upd = fair_and_update(tour, best_of, d_pre, mid, **state)
                out = f"anchor {anchor:.3f} -> d_pre {d_pre:+.4f}\nfair  {fair:.3f}"
                if mid is not None:
                    out += f"\nmid   {mid:.3f}   gap {fair - mid:+.3f}   market re-rates A's serve by {upd:+.1f} pts"
                if server is not None and state["tb_pts"] is None:
                    pa, pb = state["pts"]
                    for lab, p in (("A wins next pt", (pa + 1, pb)), ("B wins next pt", (pa, pb + 1))):
                        f2, _, _ = fair_and_update(tour, best_of, d_pre, None, **dict(state, pts=p))
                        out += f"\n  {lab}: {f2:.3f} ({f2 - fair:+.3f})"
                return self.send(out)
            except Exception as e:  # noqa: BLE001
                return self.send(f"error: {e}", code=400)
        if u.path == "/api/trades":
            return self.send(json.dumps(read_trades()), "application/json")
        if u.path == "/api/report":
            try:
                with open(REPORT) as f:
                    return self.send(f.read())
            except OSError:
                return self.send("no backtest report yet. run: python backtest.py fetch && python backtest.py analyze")
        if u.path == "/api/settle":
            r = subprocess.run([sys.executable, "settle.py", "--min-gap", "0.05", "--trades"], capture_output=True, text=True,
                               cwd=os.path.dirname(os.path.abspath(__file__)), timeout=300)
            return self.send(r.stdout + r.stderr)
        self.send("not found", code=404)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        q = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
        if u.path == "/api/trade":
            try:
                ticker, side = q["ticker"].strip(), q["side"]
                price, n_ = float(q["price"]), float(q.get("contracts") or 1)
                reason = q.get("reason", "").strip()
                if not reason:
                    return self.send("reason is required (that's the point of the log)", code=400)
                r = next((x for x in STATE["rows"] if ticker in (x["ticker_a"], x["ticker_b"])), None)
                fair = mid = score = ""
                if r:
                    flip = ticker == r["ticker_b"]
                    fair = f"{1 - float(r['fair']):.3f}" if flip and r["fair"] != "" else r["fair"]
                    mid = f"{1 - float(r['mid']):.3f}" if flip and r["mid"] != "" else r["mid"]
                    score = f"{r['sets_a']}-{r['sets_b']} {r['games_a']}-{r['games_b']} sv={r['server']}"
                os.makedirs(monitor.DATA, exist_ok=True)
                new = not os.path.exists(TRADES)
                with open(TRADES, "a", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=TCOLS)
                    if new:
                        w.writeheader()
                    w.writerow({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "ticker": ticker, "side": side,
                                "price": price, "contracts": n_, "fair": fair, "mid": mid, "score": score, "reason": reason})
                return self.send(f"logged {side} {n_:g} @ {price} on {ticker}; model fair {fair or 'n/a'} mid {mid or 'n/a'} {score}")
            except Exception as e:  # noqa: BLE001
                return self.send(f"error: {e}", code=400)
        self.send("not found", code=404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--interval", type=float, default=30)
    a = ap.parse_args()
    threading.Thread(target=loop, args=(a.interval,), daemon=True).start()
    print(f"dashboard: http://127.0.0.1:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
