#!/usr/bin/env python3
"""
MyWallet - aggiornamento prezzi ETF + storico.

Gira come GitHub Action (vedi .github/workflows/prezzi.yml).
- Fonte primaria: justETF (endpoint quote per ISIN, prezzo gettex in EURO,
  lo stesso listino su cui opera Trade Republic -> i prezzi combaciano).
- Riserva: Yahoo Finance, se justETF non risponde.
- Da Python NON c'e' il problema CORS del browser.
- Mantiene uno storico giornaliero in storico.json; alla prima esecuzione fa
  un backfill di ~6 mesi (da Yahoo) cosi' il grafico e' subito pieno.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).parent
OUT_PREZZI = HERE / "prezzi.json"
OUT_STORICO = HERE / "storico.json"
MAX_DAYS = 800
BACKFILL_RANGE = "6mo"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

ETFS = [
    {"isin": "IE00B4L5Y983", "name": "iShares Core MSCI World",
     "syms": ["SWDA.MI", "SWDA.DE", "EUNL.DE"], "bounds": (60, 260)},
    {"isin": "IE00BMG6Z448", "name": "iShares MSCI EM ex-China",
     "syms": ["84X0.DE", "EXCH.MI", "EXCH.DE"], "bounds": (3, 16)},
    {"isin": "IE00BJ5JPG56", "name": "iShares MSCI China",
     "syms": ["ICGA.DE", "ICGA.F", "ICGA.MI"], "bounds": (2, 13)},
    {"isin": "IE00BDVPNG13", "name": "WisdomTree Artificial Intelligence",
     "syms": ["WTAI.MI", "WTI2.DE", "WTAI.DE"], "bounds": (40, 260)},
    {"isin": "IE000X59ZHE2", "name": "iShares AI Infrastructure",
     "syms": ["AINF.MI", "AINF.DE", "AINF.F"], "bounds": (3, 35)},
    {"isin": "IE000U58J0M1", "name": "iShares Global Clean Energy Transition",
     "syms": ["INRA.AS", "INRE.PA", "INRA.F"], "bounds": (12, 45)},
]


# ---------------------------------------------------------------- justETF
def justetf_price(isin, session):
    """Prezzo gettex in EUR da justETF, oppure None."""
    base = "https://www.justetf.com"
    url = f"{base}/api/etfs/{isin}/quote?locale=en&currency=EUR&isin={isin}"
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{base}/en/etf-profile.html?isin={isin}",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        r = session.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return None
        j = r.json()
        cur = (j.get("currency") or "EUR").upper()
        # la risposta puo' avere forme diverse: provo i campi piu' comuni
        cand = None
        candidates = [
            ("last",), ("latestQuote", "raw"), ("quote", "raw"),
            ("latestQuote",), ("mid",), ("bid",), ("price",),
        ]
        for path in candidates:
            v = j
            ok = True
            for k in path:
                if isinstance(v, dict) and k in v:
                    v = v[k]
                else:
                    ok = False
                    break
            if ok and isinstance(v, (int, float)):
                cand = float(v)
                break
            if ok and isinstance(v, str):
                try:
                    cand = float(v.replace(",", "."))
                    break
                except ValueError:
                    pass
        if cand is None:  # ultima spiaggia: regex sul testo
            m = re.search(r'"(?:last|raw|price|mid)"\s*:\s*"?([0-9]+[.,][0-9]+)"?', r.text)
            if m:
                cand = float(m.group(1).replace(",", "."))
        if cand and cur == "EUR":
            return round(cand, 4)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- Yahoo
def _chart(symbol, rng):
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/"
               f"{symbol}?interval=1d&range={rng}")
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
            if r.status_code != 200:
                continue
            return r.json()["chart"]["result"][0]
        except Exception:
            continue
    return None


def yahoo_last(symbol):
    res = _chart(symbol, "1d")
    if not res:
        return None
    meta = res.get("meta", {})
    p = meta.get("regularMarketPrice")
    cur = (meta.get("currency") or "").upper()
    if p and cur in ("EUR", ""):
        return float(p)
    return None


def yahoo_history(symbol):
    res = _chart(symbol, BACKFILL_RANGE)
    if not res:
        return None
    cur = (res.get("meta", {}).get("currency") or "").upper()
    if cur not in ("EUR", ""):
        return None
    ts = res.get("timestamp") or []
    closes = (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    out = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        d = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
        out.append((d, round(float(c), 4)))
    return out or None


# ---------------------------------------------------------------- utils
def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def backfill():
    print("Backfill storico ~6 mesi (Yahoo)...")
    maps, alldates = {}, set()
    for e in ETFS:
        lo, hi = e["bounds"]
        h = None
        for s in e["syms"]:
            h = yahoo_history(s)
            if h:
                break
            time.sleep(0.3)
        m = {d: c for d, c in (h or []) if lo <= c <= hi}
        maps[e["isin"]] = m
        alldates |= set(m.keys())
        print(f"   {e['name']:<40} {len(m)} giorni")
    history, last = [], {e["isin"]: None for e in ETFS}
    for d in sorted(alldates):
        for e in ETFS:
            if d in maps[e["isin"]]:
                last[e["isin"]] = maps[e["isin"]][d]
        if any(v is None for v in last.values()):
            continue
        history.append({"date": d, "prices": {k: last[k] for k in last}})
    return history


# ---------------------------------------------------------------- main
def main():
    prev = load_json(OUT_PREZZI, {"prices": {}, "source": {}})
    storico = load_json(OUT_STORICO, {"history": []})
    history = storico.get("history", [])

    # sessione justETF (un GET iniziale per i cookie)
    session = requests.Session()
    try:
        session.get("https://www.justetf.com/en/", headers={"User-Agent": UA}, timeout=12)
    except Exception:
        pass

    prices, source = {}, {}
    ok = kept = 0
    for e in ETFS:
        lo, hi = e["bounds"]
        got = None

        # 1) justETF (gettex, EUR)
        p = justetf_price(e["isin"], session)
        if p and lo <= p <= hi:
            got = (round(p, 4), "justETF")

        # 2) Yahoo come riserva
        if not got:
            for sym in e["syms"]:
                yp = yahoo_last(sym)
                if yp and lo <= yp <= hi:
                    got = (round(yp, 4), sym)
                    break
                time.sleep(0.3)

        if got:
            prices[e["isin"]], source[e["isin"]] = got
            ok += 1
            print(f"  OK  {e['name']:<40} {got[0]:>9} EUR ({got[1]})")
        else:
            old = prev.get("prices", {}).get(e["isin"])
            if old is not None:
                prices[e["isin"]] = old
                source[e["isin"]] = prev.get("source", {}).get(e["isin"], "")
                kept += 1
                print(f"  --  {e['name']:<40} {old:>9} EUR (precedente)")
            else:
                print(f"  XX  {e['name']:<40}   nessun prezzo")
        time.sleep(0.2)

    OUT_PREZZI.write_text(json.dumps(
        {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "currency": "EUR", "prices": prices, "source": source},
        ensure_ascii=False, indent=2), encoding="utf-8")

    if len(history) < 20:
        bf = backfill()
        if bf:
            history = bf

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = {"date": today, "prices": prices}
    if history and history[-1]["date"] == today:
        history[-1] = entry
    else:
        history.append(entry)
    history = history[-MAX_DAYS:]

    OUT_STORICO.write_text(json.dumps(
        {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "history": history}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nprezzi: {ok} ok, {kept} mantenuti · storico: {len(history)} giorni")
    return 0


if __name__ == "__main__":
    sys.exit(main())
