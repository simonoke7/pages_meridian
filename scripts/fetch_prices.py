#!/usr/bin/env python3
"""
Meridian · Price Fetcher
Reads isins.txt, fetches fund data from Fidelity factsheets,
writes one JSON file per ISIN to data/{ISIN}.json

Handles both OEICs/unit trusts and ETFs transparently.

Data fetched:
- Fund name, currency, current price, daily change
- Chart data for all available periods: D5, M1, M3, M6, Y1, Y3, Y5, Y10
  - Funds: growth-of-1000 rebased values
  - ETFs:  actual share prices in GBX (daily close, last value per day)

Strategy:
1. Resolve slug via search API — try FUND then ETF
2. Fetch growth-chart page (fallback: price-chart) and parse __NEXT_DATA__
3. Extract all time periods from growthChart
"""

import json
import os
import time
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

DATA_DIR   = "docs/data"
ISINS_FILE = "isins.txt"

# Resolve paths relative to the repo root, regardless of where the script is invoked from
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(_REPO_ROOT, DATA_DIR)
ISINS_FILE = os.path.join(_REPO_ROOT, ISINS_FILE)

# Periods to extract — D1 (ETF intraday) intentionally excluded as too granular
PERIODS = ["D5", "M1", "M3", "M6", "Y1", "Y3", "Y5", "Y10"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}

session = requests.Session()
session.headers.update(HEADERS)


# ── Slug resolution ──────────────────────────────────────────────────────────

def resolve_slug(isin: str) -> tuple[str | None, bool]:
    """
    Resolve slug via Fidelity search API.
    Tries FUND first, then ETF.
    Returns (slug, is_etf).
    """
    url = "https://www.fidelity.co.uk/factsheet-data/search/v2/products"
    for product_type in ["FUND", "ETF"]:
        try:
            r = session.get(url, params={"searchTerm": isin, "productTypes": product_type}, timeout=10)
            r.raise_for_status()
            products = r.json().get("products", [])
            if products:
                slug = products[0].get("slug")
                if slug:
                    is_etf = product_type == "ETF"
                    print(f"    Slug ({product_type}): {slug}")
                    return slug, is_etf
        except Exception as e:
            print(f"    Search API error ({product_type}): {e}")
    return None, False


def resolve_slug_fallback(isin: str) -> tuple[str | None, bool]:
    """Follow redirect from bare ISIN URL to extract slug."""
    url = f"https://www.fidelity.co.uk/factsheet/{isin}"
    try:
        r = session.get(url, timeout=10, allow_redirects=True)
        part = r.url.split(f"{isin}-")[-1].split("/")[0]
        if part and part != r.url:
            is_etf = "price-chart" in r.url
            print(f"    Slug (fallback): {part} ({'ETF' if is_etf else 'FUND'})")
            return part, is_etf
    except Exception as e:
        print(f"    Redirect fallback error: {e}")
    return None, False


# ── Data fetching ────────────────────────────────────────────────────────────

def fetch_next_data(isin: str, slug: str, is_etf: bool) -> dict | None:
    """
    Fetch __NEXT_DATA__ from the Fidelity factsheet page.
    Tries growth-chart first for funds, price-chart first for ETFs,
    with fallback to the other in both cases.
    """
    pages = ["price-chart", "growth-chart"] if is_etf else ["growth-chart", "price-chart"]
    for page in pages:
        url = f"https://www.fidelity.co.uk/factsheet-data/factsheet/{isin}-{slug}/{page}"
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, "html.parser")
            script = soup.select_one('script[id="__NEXT_DATA__"]')
            if not script or not script.string:
                continue
            data = json.loads(script.string)
            fund = data["props"]["pageProps"]["initialState"]["fund"]
            if fund.get("growthChart"):
                print(f"    Page: {page}")
                return fund
        except requests.exceptions.HTTPError:
            continue
        except Exception as e:
            print(f"    Error on {page}: {e}")
    return None


def fetch_performance_m60(isin: str, slug: str) -> float | None:
    """
    Fetch M60 (5-year annualized) performance data from the performance page.
    Extracts from ["props"]["pageProps"]["initialState"]["fund"]["performance"]["timeFrameData"]
    timeFrameData is a list of dicts with keys: timeframe, trailingReturnsValue, trailingReturnsBenchmarkValue
    """
    url = f"https://www.fidelity.co.uk/factsheet-data/factsheet/{isin}-{slug}/performance"
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        script = soup.select_one('script[id="__NEXT_DATA__"]')
        if not script or not script.string:
            return None
        data = json.loads(script.string)
        timeframe_data = data["props"]["pageProps"]["initialState"]["fund"]["performance"]["timeFrameData"]
        
        # timeFrameData is a list of dicts with timeframe, trailingReturnsValue, etc.
        if isinstance(timeframe_data, list):
            for entry in timeframe_data:
                if isinstance(entry, dict) and entry.get("timeframe") == "M60":
                    m60_str = entry.get("trailingReturnsValue")
                    if m60_str:
                        try:
                            return float(m60_str)
                        except (ValueError, TypeError):
                            return None
        
    except requests.exceptions.HTTPError:
        pass
    except Exception as e:
        print(f"    Error fetching M60: {e}")
    return None


# ── Data extraction ──────────────────────────────────────────────────────────

def extract_periods(growth_chart: dict, is_etf: bool) -> dict:
    """
    Extract time periods from growthChart.

    For funds: values are growth-of-1000 rebased floats. endDate is YYYY-MM-DD.
    For ETFs:  values are actual share prices. endDate may be a datetime string
               (e.g. "2026-03-27T14:30:00") for short periods — these are
               deduplicated to one close per calendar day (last value wins).
    """
    result = {}
    for period in PERIODS:
        raw = growth_chart.get(period)
        if not raw or not isinstance(raw, list):
            continue

        if period == "D5":
            # Keep full datetime for D5 — preserve all intraday points
            points = []
            for entry in raw:
                end_date = entry.get("endDate", "")
                raw_val  = entry.get("value")
                if not end_date or raw_val is None:
                    continue
                try:
                    points.append({"date": end_date, "value": float(raw_val)})
                except (ValueError, TypeError):
                    continue
            if points:
                points = sorted(points, key=lambda p: p["date"])
                # Drop consecutive duplicate values — removes overnight/weekend
                # repeats where Fidelity holds the last traded price constant
                deduped = [points[0]]
                for pt in points[1:]:
                    if pt["value"] != deduped[-1]["value"]:
                        deduped.append(pt)
                result[period] = deduped
        else:
            seen: dict[str, float] = {}
            for entry in raw:
                end_date = entry.get("endDate", "")
                raw_val  = entry.get("value")
                if not end_date or raw_val is None:
                    continue
                # Normalise to YYYY-MM-DD — strip time component if present
                date_key = end_date[:10]
                try:
                    seen[date_key] = float(raw_val)
                except (ValueError, TypeError):
                    continue
            if seen:
                result[period] = [
                    {"date": d, "value": v}
                    for d, v in sorted(seen.items())
                ]

    return result


def detect_is_etf(fund: dict) -> bool:
    """
    Detect whether a fund is an ETF from its fundData.
    Fidelity uses type "22" for ETFs, "2" for OEICs/unit trusts.
    Also checks for the presence of a stock exchange symbol as a secondary signal.
    """
    fund_info = fund.get("fundData", {})
    fund_type = str(fund_info.get("type", ""))
    if fund_type == "22":
        return True
    if fund_info.get("symbol") and fund_info.get("stockExchange"):
        return True
    return False


def extract_price_details(fund: dict, is_etf: bool) -> dict:
    """
    Extract current price and daily change from priceDtls.

    Funds:  single lastBuySellPrice
    ETFs:   separate sellPrice / buyPrice — use mid-price
    """
    pd = fund.get("priceDtls") or fund.get("fundData", {}).get("priceDtls", {})

    def _float(val) -> float | None:
        try:
            f = float(val)
            return None if str(val).lower() in ("null", "none", "") else f
        except (TypeError, ValueError):
            return None

    if is_etf:
        sell  = _float(pd.get("sellPrice"))
        buy   = _float(pd.get("buyPrice"))
        price = round((sell + buy) / 2, 2) if sell is not None and buy is not None else (sell or buy)
    else:
        price = _float(pd.get("lastBuySellPrice"))
        sell  = None
        buy   = None

    return {
        "price":            price,
        "sell_price":       sell,
        "buy_price":        buy,
        "currency":         pd.get("currency", "GBX"),
        "daily_change":     _float(pd.get("changeAbsolute")),
        "daily_change_pct": _float(pd.get("changePercentage")),
        "price_updated":    pd.get("lastUpdated"),
    }


# ── Alpha Vantage benchmark fetch ────────────────────────────────────────────

def fetch_alphavantage_change(ticker: str, api_key: str) -> tuple[float | None, str | None]:
    """
    Fetch daily % change for a US-listed ticker via Alpha Vantage GLOBAL_QUOTE.
    Returns (change_pct, latest_trading_day) or (None, None) on failure.
    """
    url = (
        "https://www.alphavantage.co/query"
        f"?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
    )
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        quote = data.get("Global Quote", {})
        if not quote:
            print(f"    Alpha Vantage ({ticker}): empty response — {data}")
            return None, None
        chg_str = quote.get("10. change percent", "").strip().rstrip("%")
        day     = quote.get("07. latest trading day")
        chg     = round(float(chg_str), 4) if chg_str else None
        return chg, day
    except Exception as e:
        print(f"    Alpha Vantage error ({ticker}): {e}")
        return None, None


# ── Index generation ─────────────────────────────────────────────────────────

def generate_index(data_dir: str):
    """Regenerate data/index.json for dashboard auto-discovery."""
    funds = []
    for filename in sorted(os.listdir(data_dir)):
        if not filename.endswith(".json") or filename == "index.json":
            continue
        try:
            with open(os.path.join(data_dir, filename)) as f:
                d = json.load(f)
            funds.append({
                "isin":   d.get("isin", filename[:-5]),
                "name":   d.get("name", filename[:-5]),
                "ticker": d.get("ticker", filename[:-5]),
                "is_etf": d.get("is_etf", False),
            })
        except Exception as e:
            print(f"  Warning: could not read {filename}: {e}")

    index_path = os.path.join(data_dir, "index.json")
    with open(index_path, "w") as f:
        json.dump({"funds": funds}, f, indent=2)
    print(f"  ✓ index.json → {len(funds)} fund(s)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(ISINS_FILE):
        print(f"ERROR: {ISINS_FILE} not found. Create it with one ISIN per line.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(ISINS_FILE) as f:
        entries = [
            line.strip() for line in f
            if line.strip() and not line.startswith("#")
        ]

    if not entries:
        print("No ISINs found in isins.txt")
        return

    print(f"Fetching {len(entries)} fund(s) from Fidelity…\n")

    av_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")

    success, failed = 0, []
    MAX_RETRIES = 3

    for idx, entry in enumerate(entries, 1):
        benchmark_for = None

        # Alpha Vantage benchmark entry
        if entry.lower().startswith("alphavantage:"):
            parts         = entry.split(":")
            ticker        = parts[1].strip()
            if len(parts) > 2 and parts[2].startswith("benchmark="):
                benchmark_for = parts[2].split("=", 1)[1].strip().upper()
            print(f"[{idx}/{len(entries)}] Alpha Vantage: {ticker}")
            if not av_key:
                print("  ⚠ ALPHA_VANTAGE_API_KEY not set — skipping\n")
                continue
            chg, day = fetch_alphavantage_change(ticker, av_key)
            if chg is not None:
                print(f"    ✓ {ticker}: {chg:+.4f}% as of {day}")
            else:
                print(f"    ⚠ {ticker}: no data")
            if benchmark_for:
                target_path = os.path.join(DATA_DIR, f"{benchmark_for}.json")
                if os.path.exists(target_path):
                    with open(target_path) as f:
                        target = json.load(f)
                    target["benchmark_change_pct"]    = chg
                    target["benchmark_ticker"]        = ticker
                    target["benchmark_price_updated"] = day
                    with open(target_path, "w") as f:
                        json.dump(target, f, separators=(",", ":"))
                    print(f"  ✓ Written to {benchmark_for}.json\n")
                else:
                    print(f"  ⚠ Target {benchmark_for}.json not found — run full fetch first\n")
            success += 1
            if idx < len(entries):
                time.sleep(1.2)  # Alpha Vantage free tier: 1 req/sec
            continue

        if ":" in entry:
            parts = entry.split(":")
            isin           = parts[0].strip().upper()
            explicit_ticker = parts[1].strip().upper()
            if len(parts) > 2 and parts[2].startswith("benchmark="):
                benchmark_for = parts[2].split("=", 1)[1].strip().upper()
        else:
            isin, explicit_ticker = entry.strip().upper(), None

        print(f"[{idx}/{len(entries)}] {isin}")

        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                wait = 2 ** (attempt - 1)
                print(f"  Retry {attempt}/{MAX_RETRIES} in {wait}s…")
                time.sleep(wait)

            # 1. Resolve slug and type
            slug, is_etf = resolve_slug(isin)
            if not slug:
                slug, is_etf = resolve_slug_fallback(isin)
            if not slug:
                print(f"  Attempt {attempt} — could not resolve Fidelity slug")
                continue

            # 2. Fetch __NEXT_DATA__
            fund = fetch_next_data(isin, slug, is_etf)
            if not fund:
                print(f"  Attempt {attempt} — no data returned")
                continue

            break  # success — proceed to processing below
        else:
            print(f"  SKIPPED after {MAX_RETRIES} attempts\n")
            failed.append(isin)
            continue

        # 3a. Benchmark-only path — price fetch + periods, write to target fund JSON, skip full processing
        if benchmark_for:
            is_etf       = detect_is_etf(fund)
            price_info   = extract_price_details(fund, is_etf)
            chg          = price_info["daily_change_pct"]
            growth_chart = fund.get("growthChart", {})
            bmk_periods  = extract_periods(growth_chart, is_etf)
            print(f"    ✓ Benchmark ({explicit_ticker or isin}): {chg:+.2f}%" if chg is not None else f"    ✓ Benchmark ({explicit_ticker or isin}): n/a")
            for p, pts in bmk_periods.items():
                print(f"    ✓ Bmk {p}: {len(pts)} points  ({pts[0]['date']} → {pts[-1]['date']})")
            target_path = os.path.join(DATA_DIR, f"{benchmark_for}.json")
            if os.path.exists(target_path):
                with open(target_path) as f:
                    target = json.load(f)
                target["benchmark_change_pct"]    = chg
                target["benchmark_ticker"]        = explicit_ticker or isin
                target["benchmark_price_updated"] = price_info["price_updated"]
                target["benchmark_periods"]       = bmk_periods
                with open(target_path, "w") as f:
                    json.dump(target, f, separators=(",", ":"))
                print(f"  ✓ Written to {benchmark_for}.json\n")
            else:
                print(f"  ⚠ Target {benchmark_for}.json not found — run full fetch first\n")
            success += 1
            if idx < len(entries):
                time.sleep(2)
            continue

        # 3b. Extract metadata — detect ETF from fund data, not search API
        is_etf     = detect_is_etf(fund)  # authoritative detection from fundData.type
        fund_info  = fund.get("fundData", {})
        fund_name  = fund_info.get("name", isin)
        price_info = extract_price_details(fund, is_etf)
        ticker     = explicit_ticker or fund_info.get("symbol") or fund_info.get("fundCodeValue") or isin

        print(f"    ✓ {fund_name} ({'ETF' if is_etf else 'Fund'})")
        if price_info['daily_change_pct'] is not None:
            print(f"    ✓ Price: {price_info['price']} {price_info['currency']}  "
                  f"({price_info['daily_change_pct']:+.2f}%)")
        else:
            print(f"    ✓ Price: {price_info['price']} {price_info['currency']}")

        # 4. Extract periods
        growth_chart = fund.get("growthChart", {})
        periods = extract_periods(growth_chart, is_etf)

        for p, pts in periods.items():
            print(f"    ✓ {p}: {len(pts)} points  ({pts[0]['date']} → {pts[-1]['date']})")

        if not periods:
            print(f"    ⚠ No chart data found")

        # 5. Fetch M60 (5-year annualized) performance data
        time.sleep(1)  # Rate limiting: space out additional API calls
        m60_annualized = fetch_performance_m60(isin, slug)
        if m60_annualized is not None:
            print(f"    ✓ M60 (5Y annualized): {m60_annualized}%")

        # 6. Save JSON
        payload = {
            "isin":             isin,
            "name":             fund_name,
            "ticker":           ticker,
            "is_etf":           is_etf,
            "currency":         price_info["currency"],
            "price":            price_info["price"],
            "sell_price":       price_info.get("sell_price"),
            "buy_price":        price_info.get("buy_price"),
            "daily_change":     price_info["daily_change"],
            "daily_change_pct": price_info["daily_change_pct"],
            "price_updated":    price_info["price_updated"],
            "m60_annualized":   m60_annualized,
            "periods":          periods,
            "fetched":          datetime.now(timezone.utc).isoformat(),
        }

        out_path = os.path.join(DATA_DIR, f"{isin}.json")
        with open(out_path, "w") as f:
            json.dump(payload, f, separators=(",", ":"))
        print(f"  ✓ Saved → {out_path}\n")
        success += 1

        if idx < len(entries):
            time.sleep(2)

    print("─" * 50)
    print(f"Done: {success}/{len(entries)} fetched successfully")
    if failed:
        print(f"Failed: {', '.join(failed)}")

    print("\nRegenerating index…")
    generate_index(DATA_DIR)


if __name__ == "__main__":
    main()