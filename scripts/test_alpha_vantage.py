#!/usr/bin/env python3
"""Quick test that the Alpha Vantage API key pulls GLOBAL_QUOTE data correctly."""

import urllib.request, json, os, sys

key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
if not key:
    print("ERROR: ALPHA_VANTAGE_API_KEY env var not set")
    sys.exit(1)

tickers = ["QQQ", "IXJ", "URTH", "IWM"]
base    = "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&apikey=" + key

all_ok = True
for ticker in tickers:
    url = base + "&symbol=" + ticker
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        quote = data.get("Global Quote", {})
        if not quote:
            print(f"FAIL  {ticker}: empty response — {data}")
            all_ok = False
            continue
        price = quote.get("05. price", "—")
        prev  = quote.get("08. previous close", "—")
        chg   = quote.get("10. change percent", "—")
        day   = quote.get("07. latest trading day", "—")
        print(f"OK    {ticker}: {price} (prev {prev}, {chg}) as of {day}")
    except Exception as e:
        print(f"FAIL  {ticker}: {e}")
        all_ok = False

sys.exit(0 if all_ok else 1)
