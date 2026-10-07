from __future__ import annotations

import json
import math
import re
import statistics as st
import sys
import time
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
from app.core.scoring import (
    score_debt,
    score_profitability,
    score_quality,
    score_valuation,
)

TICKERS = [
    "ACES", "ADMR", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ARTO", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BMRI", "BRIS", "BRPT", "CPIN", "CTRA", "ESSA", "EXCL",
    "GOTO", "ICBP", "INCO", "INDF", "INKP", "INTP", "ISAT", "ITMG", "JPFA", "JSMR",
    "KLBF", "MAPA", "MAPI", "MBMA", "MDKA", "MEDC", "PGAS", "PGEO", "PTBA", "SIDO",
    "SMGR", "TLKM", "TOWR", "UNTR", "UNVR",
]

CACHE = ROOT / "data" / "sectors_pages"
CRAWL_DELAY = 3.0
UA = "MARKET.EXE research backtest (hackathon project; one fetch per page, cached)"


def fetch_page(sym: str, client: httpx.Client) -> str | None:
    path = CACHE / f"{sym}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    for attempt in range(3):
        r = client.get(f"https://sectors.app/idx/{sym.lower()}")
        if r.status_code == 200:
            path.write_text(r.text, encoding="utf-8")
            time.sleep(CRAWL_DELAY)
            return r.text
        if r.status_code == 429:
            time.sleep(30 * (attempt + 1))
            continue
        print(f"  {sym}: HTTP {r.status_code}")
        time.sleep(CRAWL_DELAY)
        return None
    return None


def flight_text(html: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def find_json(s: str, key: str):
    i = s.find('"' + key + '":')
    if i < 0:
        return None
    j = i + len(key) + 3
    opener = s[j]
    closer = {"[": "]", "{": "}"}.get(opener)
    if closer is None:
        return None
    depth = 0
    for k in range(j, len(s)):
        if s[k] == opener:
            depth += 1
        elif s[k] == closer:
            depth -= 1
            if depth == 0:
                return json.loads(s[j:k + 1])
    return None


def num(v) -> float | None:
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def parse_company(sym: str, html: str) -> dict | None:
    s = flight_text(html)
    ratios = find_json(s, "historical_financial_ratio") or []
    fins = find_json(s, "historical_financials") or []
    vals = find_json(s, "historical_valuation") or []
    divs = find_json(s, "historical_dividends") or {}
    splits = find_json(s, "stock_split") or []
    m_price = re.search(r'"last_close_price":([\d.]+)', s)
    m_date = re.search(r'"latest_close_date":"(\d{4}-\d{2}-\d{2})"', s)
    m_sector = re.search(r'"sector":"([^"]+)"', s)
    if not ratios or not fins:
        return None

    fin = {int(r["year"]): r for r in fins if r.get("year") is not None}
    ratio = {int(r["year"]): r for r in ratios if str(r.get("year", "")).isdigit()}

    def eps(y):
        f = fin.get(y) or {}
        e, sh = num(f.get("earnings")), num(f.get("outstanding_shares"))
        return e / sh if e is not None and sh else None

    def bvps(y):
        f = fin.get(y) or {}
        eq, sh = num(f.get("total_equity")), num(f.get("outstanding_shares"))
        return eq / sh if eq is not None and sh else None

    price: dict[int, float] = {}
    check: list[float] = []
    for v in vals:
        y = int(v["year"])
        pe, pb = num(v.get("pe")), num(v.get("pb"))
        p_pe = pe * eps(y) if pe and pe > 0 and eps(y) and eps(y) > 0 else None
        p_pb = pb * bvps(y) if pb and pb > 0 and bvps(y) and bvps(y) > 0 else None
        if p_pe and p_pb:
            check.append(p_pe / p_pb)
        if p_pe or p_pb:
            price[y] = p_pe or p_pb

    last_price = num(m_price.group(1)) if m_price else None
    last_date = date.fromisoformat(m_date.group(1)) if m_date else None
    this_year = last_date.year if last_date else date.today().year
    price.pop(this_year, None)

    dividends = []
    for y, row in (divs or {}).items():
        for b in (row or {}).get("breakdown") or []:
            a = num(b.get("total"))
            if a and b.get("date"):
                dividends.append((date.fromisoformat(b["date"]), a))
    split_list = [(date.fromisoformat(x["date"]), num(x.get("split_ratio")) or 1.0)
                  for x in splits if x.get("date")]

    return {
        "symbol": sym,
        "sector": m_sector.group(1) if m_sector else None,
        "ratio": ratio,
        "eps": eps,
        "price": price,
        "last_price": last_price,
        "last_date": last_date,
        "dividends": dividends,
        "splits": split_list,
        "pe_pb_check": check,
    }


def total_return(c: dict, start: date, end: date, p0: float, p1: float) -> float:
    split = 1.0
    for d, ratio in c["splits"]:
        if start < d <= end:
            split *= ratio
    divs = sum(a for d, a in c["dividends"] if start < d <= end)
    return (p1 * split + divs) / p0 - 1.0


def build_rows(companies: list[dict]) -> list[dict]:
    rows = []
    for c in companies:
        for t in sorted(c["price"]):
            fy = t - 1
            r = c["ratio"].get(fy)
            e = c["eps"](fy)
            p0 = c["price"][t]
            if r is None:
                continue
            if t + 1 in c["price"]:
                end, p1 = date(t + 1, 12, 31), c["price"][t + 1]
            elif c["last_date"] and c["last_date"].year == t + 1 and c["last_price"]:
                end, p1 = c["last_date"], c["last_price"]
            else:
                continue
            prof, lev = r.get("profitability") or {}, r.get("leverage") or {}
            feats = {
                "pe_ttm": p0 / e if e and e > 0 else None,
                "roe_ttm": num(prof.get("roe")),
                "roa_ttm": num(prof.get("roa")),
                "der_mrq": num(lev.get("debt_to_equity_ratio")),
            }
            parts = {
                "valuation": score_valuation(feats),
                "debt": score_debt(feats),
                "quality": score_quality(feats),
                "profitability": score_profitability(feats),
            }
            known = sum(cf for _, cf in parts.values())
            if known < 3:
                continue
            prev = c["price"].get(t - 1)
            rows.append({
                "symbol": c["symbol"],
                "sector": c["sector"],
                "year": t,
                "score": sum(s for s, _ in parts.values()) * 100 / 80,
                **{k: s for k, (s, _) in parts.items()},
                "trend_1y": (p0 / prev - 1) if prev else None,
                "ret": total_return(c, date(t, 12, 31), end, p0, p1),
                "partial": end.year == t + 1 and end.month < 12,
            })
    return rows


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 5:
        return None
    ra, rb = rank(a), rank(b)
    return st.correlation(ra, rb)


def evaluate(rows: list[dict], key: str) -> dict:
    years = sorted({r["year"] for r in rows})
    per_year = {}
    spreads = []
    for y in years:
        g = [r for r in rows if r["year"] == y and r[key] is not None]
        if len(g) < 9:
            continue
        ic = spearman([r[key] for r in g], [r["ret"] for r in g])
        g.sort(key=lambda r: r[key])
        n3 = len(g) // 3
        lo = st.mean(r["ret"] for r in g[:n3])
        hi = st.mean(r["ret"] for r in g[-n3:])
        per_year[y] = {"n": len(g), "ic": ic, "top_third": hi, "bottom_third": lo}
        spreads.append(hi - lo)
    ics = [v["ic"] for v in per_year.values() if v["ic"] is not None]
    mean_ic = st.mean(ics) if ics else None
    t_ic = (mean_ic / (st.stdev(ics) / math.sqrt(len(ics)))
            if len(ics) > 1 and st.stdev(ics) > 0 else None)
    return {
        "per_year": per_year,
        "mean_ic": mean_ic,
        "t_ic": t_ic,
        "years_positive": sum(1 for x in ics if x > 0),
        "years": len(ics),
        "mean_spread": st.mean(spreads) if spreads else None,
    }


def permutation_p(rows: list[dict], key: str, n: int = 5000, seed: int = 7) -> float:
    import random
    rnd = random.Random(seed)
    observed = evaluate(rows, key)["mean_ic"]
    by_year = {}
    for r in rows:
        if r[key] is not None:
            by_year.setdefault(r["year"], []).append(r)
    hits = 0
    for _ in range(n):
        ics = []
        for g in by_year.values():
            if len(g) < 9:
                continue
            s = [r[key] for r in g]
            rnd.shuffle(s)
            ics.append(spearman(s, [r["ret"] for r in g]))
        if st.mean(ics) >= observed:
            hits += 1
    return (hits + 1) / (n + 1)


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    companies = []
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as client:
        for i, sym in enumerate(TICKERS, 1):
            html = fetch_page(sym, client)
            c = parse_company(sym, html) if html else None
            print(f"[{i:2}/{len(TICKERS)}] {sym}: "
                  + (f"{len(c['ratio'])} yrs ratios, prices {sorted(c['price'])}" if c else "no data"),
                  flush=True)
            if c:
                companies.append(c)

    checks = [x for c in companies for x in c["pe_pb_check"]]
    rows = build_rows(companies)
    print(f"\n{len(companies)} companies, {len(rows)} company-years "
          f"(P/E-vs-P/B price agreement: median ratio {st.median(checks):.3f})\n")

    keys = ["score", "valuation", "debt", "quality", "profitability", "trend_1y"]
    results = {k: evaluate(rows, k) for k in keys}
    results["score"]["perm_p"] = permutation_p(rows, "score")

    print(f"{'signal':<14}{'mean IC':>9}{'t':>7}{'yrs+':>7}{'top-bottom third':>18}")
    for k in keys:
        r = results[k]
        fmt = lambda v, f: (f.format(v) if v is not None else "  -")
        print(f"{k:<14}{fmt(r['mean_ic'], '{:9.3f}')}{fmt(r['t_ic'], '{:7.2f}')}"
              f"{r['years_positive']:>4}/{r['years']}{fmt(r['mean_spread'], '{:17.1%}')}")
    print(f"\nscore permutation p-value: {results['score']['perm_p']:.3f}")
    print("\nper year (score):")
    for y, v in results["score"]["per_year"].items():
        print(f"  formed end-{y}: n={v['n']}, IC={v['ic']:+.3f}, "
              f"top third {v['top_third']:+.1%}, bottom third {v['bottom_third']:+.1%}")

    bands = [("70+", 70, 101), ("50-69", 50, 70), ("30-49", 30, 50), ("<30", 0, 30)]
    print("\nby score band (all years pooled):")
    regimes = {}
    for name, lo, hi in bands:
        g = [r["ret"] for r in rows if lo <= r["score"] < hi]
        if g:
            regimes[name] = {"n": len(g), "mean": st.mean(g), "median": st.median(g)}
            print(f"  {name:>6}: n={len(g):3}, mean {st.mean(g):+.1%}, median {st.median(g):+.1%}")

    out = {
        "source": "sectors.app public company pages (no API key, no Yahoo)",
        "companies": len(companies),
        "company_years": len(rows),
        "signals": results,
        "bands": regimes,
    }
    (ROOT / "results_health.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote backtest/results_health.json")


if __name__ == "__main__":
    main()
