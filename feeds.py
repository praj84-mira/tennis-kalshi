"""Free, unauthenticated feeds: Kalshi public API + ESPN scoreboard.

No order code lives here or anywhere in this package, by design.
"""
import json
import math
import re
import time
import unicodedata
import urllib.request
import urllib.parse
from datetime import datetime, timezone

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"
SERIES = {"ATP": "KXATPMATCH", "WTA": "KXWTAMATCH"}
SET_SERIES = {"ATP": "KXATPSETWINNER", "WTA": "KXWTASETWINNER"}
UA = "usopen-fairvalue/0.1 (read-only monitor)"

# Fee schedule. fee_type on KXATPMATCH / KXWTAMATCH is
# "quadratic_with_maker_fees" (observed 2026-09-03 via /series). Rates are
# the published general schedule: taker 0.07, maker 0.0175, rounded UP to the
# cent per order. [Likely] -- confirm against kalshi.com/docs/fee-schedule.
TAKER_RATE = 0.07
MAKER_RATE = 0.0175


def fee(price, contracts=1, maker=False):
    """Fee in dollars for `contracts` at `price` (0..1)."""
    rate = MAKER_RATE if maker else TAKER_RATE
    return math.ceil(rate * contracts * price * (1 - price) * 100) / 100


def _get(url, params=None, retries=3, timeout=15):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def _f(x):
    try:
        return None if x in (None, "") else float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------- Kalshi
def kalshi_open_by_ticker(series):
    """All open markets in a series, keyed by ticker (used for set-winner markets)."""
    out, cursor = {}, None
    while True:
        params = {"series_ticker": series, "status": "open", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = _get(f"{KALSHI}/markets", params)
        for m in d.get("markets", []):
            out[m["ticker"]] = market_row(m)
        cursor = d.get("cursor")
        if not cursor:
            break
    return out


def kalshi_open_markets(tour):
    """All open markets in the tour's match series, grouped by event."""
    out = []
    cursor = None
    while True:
        params = {"series_ticker": SERIES[tour], "status": "open", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = _get(f"{KALSHI}/markets", params)
        out.extend(d.get("markets", []))
        cursor = d.get("cursor")
        if not cursor:
            break
    events = {}
    for m in out:
        events.setdefault(m["event_ticker"], []).append(market_row(m))
    return events


def market_row(m):
    bid, ask = _f(m.get("yes_bid_dollars")), _f(m.get("yes_ask_dollars"))
    mid = None
    if bid is not None and ask is not None and ask > 0:
        mid = 0.5 * (bid + ask)
    return {
        "ticker": m["ticker"],
        "event_ticker": m["event_ticker"],
        "player": m.get("yes_sub_title") or m.get("title", "").replace(" wins", ""),
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "last": _f(m.get("last_price_dollars")),
        "bid_size": _f(m.get("yes_bid_size_fp")),
        "ask_size": _f(m.get("yes_ask_size_fp")),
        "volume": _f(m.get("volume_fp")),
        "oi": _f(m.get("open_interest_fp")),
        "status": m.get("status"),
        "result": m.get("result"),
        "rules": m.get("rules_primary", ""),
    }


def kalshi_market(ticker):
    return market_row(_get(f"{KALSHI}/markets/{ticker}")["market"])


def kalshi_last_trade_before(ticker, ts):
    """Last trade price (yes, dollars) at or before unix `ts`, or None."""
    d = _get(f"{KALSHI}/markets/trades", {"ticker": ticker, "max_ts": int(ts), "limit": 1})
    tr = d.get("trades") or []
    if not tr:
        return None
    return _f(tr[0].get("yes_price_dollars"))


def kalshi_last_candle_before(series, ticker, ts, lookback_h=48):
    d = _get(f"{KALSHI}/series/{series}/markets/{ticker}/candlesticks",
             {"start_ts": int(ts - lookback_h * 3600), "end_ts": int(ts), "period_interval": 1})
    cs = d.get("candlesticks") or []
    for c in reversed(cs):
        b, a = _f(c.get("yes_bid", {}).get("close_dollars")), _f(c.get("yes_ask", {}).get("close_dollars"))
        if b is not None and a is not None and a > 0:
            return 0.5 * (a + b)
    return None


# --------------------------------------------------------------- ESPN
def espn_singles():
    """Live/scheduled/finished singles matches with parsed score state."""
    d = _get(ESPN)
    matches = []
    for ev in d.get("events", []):
        for g in ev.get("groupings", []):
            name = g.get("grouping", {}).get("displayName", "")
            if name == "Men's Singles":
                tour = "ATP"
            elif name == "Women's Singles":
                tour = "WTA"
            else:
                continue
            for c in g.get("competitions", []):
                m = parse_competition(c, tour, ev.get("name", ""))
                if m:
                    matches.append(m)
    return matches


def parse_competition(c, tour, event_name):
    comps = c.get("competitors", [])
    if len(comps) != 2 or any("athlete" not in x for x in comps):
        return None
    comps = sorted(comps, key=lambda x: x.get("order", 0))
    names = [x["athlete"].get("displayName", "") for x in comps]
    ls = [[(int(l.get("value") or 0), l.get("tiebreak")) for l in x.get("linescores", [])] for x in comps]
    n = min(len(ls[0]), len(ls[1]))
    sets = [0, 0]
    games = [0, 0]
    tb = None
    for i in range(n):
        ga, gb = ls[0][i][0], ls[1][i][0]
        done = (max(ga, gb) >= 6 and abs(ga - gb) >= 2) or max(ga, gb) == 7
        if done:
            sets[0 if ga > gb else 1] += 1
        elif i == n - 1:
            games = [ga, gb]
            if ga == 6 and gb == 6 and (ls[0][i][1] is not None or ls[1][i][1] is not None):
                tb = (int(ls[0][i][1] or 0), int(ls[1][i][1] or 0))
    server = None
    poss = [x.get("possession") for x in comps]
    if poss[0] is True and poss[1] is not True:
        server = 0
    elif poss[1] is True and poss[0] is not True:
        server = 1
    st = c.get("status", {}).get("type", {})
    best_of = int(c.get("format", {}).get("regulation", {}).get("periods") or (5 if tour == "ATP" else 3))
    winner = None
    for i, x in enumerate(comps):
        if x.get("winner") is True:
            winner = i
    start = c.get("date") or c.get("startDate")
    return {
        "id": c.get("id"),
        "event": event_name,
        "tour": tour,
        "best_of": best_of,
        "round": (c.get("round") or {}).get("displayName") if isinstance(c.get("round"), dict) else c.get("round"),
        "court": (c.get("venue") or {}).get("court"),
        "names": names,
        "keys": [name_key(x) for x in names],
        "seeds": [((x.get("curatedRank") or {}).get("current")) for x in comps],
        "state": st.get("state"),          # pre / in / post
        "detail": st.get("detail"),
        "sets": tuple(sets),
        "games": tuple(games),
        "tb_pts": tb,
        "server": server,
        "winner": winner,
        "start": start,
        "start_ts": iso_ts(start),
        "linescores": ls,
    }


def iso_ts(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None


# ------------------------------------------------------------ matching
def name_key(name):
    """Accent-stripped lowercase surname (last token), for Kalshi<->ESPN join."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z ]", "", s.lower()).strip()
    toks = s.split()
    return toks[-1] if toks else ""


def match_kalshi_to_espn(events, matches):
    """Return list of (espn_match, market_for_player0, market_for_player1)."""
    by_keys = {}
    for m in matches:
        by_keys[frozenset(m["keys"])] = m
    joined = []
    for ev, mkts in events.items():
        if len(mkts) != 2:
            continue
        k = frozenset(name_key(x["player"]) for x in mkts)
        m = by_keys.get(k)
        if not m:
            continue
        a = next(x for x in mkts if name_key(x["player"]) == m["keys"][0])
        b = next(x for x in mkts if name_key(x["player"]) == m["keys"][1])
        joined.append((m, a, b))
    return joined
