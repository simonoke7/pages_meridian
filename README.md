# Meridian · Setup Guide

Fetch historical fund prices from Fidelity factsheets. No API key required.

---

## How it works

```
GitHub Actions (nightly, server-side)
  → Fidelity Factsheets (UK & global funds)
  → Parse __NEXT_DATA__ JSON from pages
  → Writes data/*.json to the repo
  → Commits & pushes automatically

GitHub Pages serves index.html + data/*.json
  → Dashboard reads data files directly ← zero config
```

---

## Setup

Fidelity hosts factsheets for thousands of UK unit trusts, OEICs, ETFs, and investment trusts. The fetcher parses the embedded Next.js data (`__NEXT_DATA__` script tag) to extract prices and historical data.

### GitHub Actions Setup

The fetcher automatically runs on GitHub Actions (no special setup needed beyond pushing this repo).

### Local Development

For local testing in Codespaces or your machine:

```bash
python scripts/fetch_prices.py
```

---

## Adding a fund

1. Add its ISIN to `isins.txt` (one per line)
2. Run the fetch script or trigger GitHub Actions
3. Add the fund in the dashboard's Fund Settings tab
4. Select it — data loads immediately

---

## isins.txt format

```
# ISINs of funds listed on Fidelity (most UK unit trusts, OEICs, ETFs)
GB0006063233                  ← Baillie Gifford Pacific B Acc
IE00B3X1NT05:VWRL.L          ← Vanguard Global Small Cap (explicit ticker optional)
IE00BYPLS672                  ← Legal & General UCITS ETF
```

**Supported funds:** Any fund available on [Fidelity UK factsheets](https://www.fidelity.co.uk/factsheet-data/factsheet/). If a fund is listed there, it will work with Meridian.

---

## Local Development in GitHub Codespaces

This repo includes a `.devcontainer` configuration for seamless development in Codespaces.

### Quick Start

1. **Open in Codespaces** → Click the green `<> Code` button on GitHub and open in Codespaces
2. **Wait for setup** → Container installs dependencies (~30 seconds)
3. **Fetch live data:**
   - `Ctrl+Shift+P` → "Run Task" → **Fetch prices**
   - This reads `isins.txt` and fetches data from Fidelity factsheets
4. **Start the server:**
   - `Ctrl+Shift+P` → "Run Task" → **Serve local dashboard (port 8000)**
5. **Open the dashboard at `http://localhost:8000/index.html`**

### Key Features

✓ **Uses Fidelity data** — Comprehensive UK fund coverage (OEICs, unit trusts, ETFs)  
✓ **No API key required** — Web scraping of public factsheet data  
✓ **Uses your root `isins.txt`** — Single source of truth for all environments  
✓ **Manual control** — Run tasks on demand, re-run after feature changes  
✓ **No waiting on startup** — Container is ready instantly for editing  
✓ **Port forwarding** — Dashboard (8000) automatically exposed  

### VS Code Tasks

| Task | Purpose |
|------|---------|
| **Fetch prices** | Fetch live Fidelity data (reads root `isins.txt`) |
| **Serve local dashboard** (default) | Start HTTP server on port 8000 |

**To run:** `Ctrl+Shift+P` → "Run Task" → select task

### Editing & Testing Workflow

1. Edit `index.html`, `isins.txt` (root), or `scripts/fetch_prices.py`
2. Add new ISINs to root `isins.txt`
3. **Run "Fetch prices"** to get live data
4. **Run "Serve local dashboard"** to start the server
5. Reload the dashboard in your browser to test changes

---

## Fidelity Data Fetching

The fetcher uses BeautifulSoup to parse Fidelity factsheet pages:
1. Fetches the factsheet HTML for each fund's ISIN
2. Extracts the Next.js `__NEXT_DATA__` script tag (embedded JSON)
3. Navigates to the fund's chart data structure
4. Parses price history with dates and values

### Data Extraction

- Fund name and current price
- Daily price change (calculated from latest data)
- Historical price series (typically 10+ years)
- Supports both growth charts (unit trusts) and price charts (ETFs)

### Rate Limiting

Fidelity's server is respectful of reasonable requests:
- 2 second delay between fund fetches
- Realistic User-Agent header
- Timeout: 15 seconds per request

### Troubleshooting

**Fund not found:**
- Verify the ISIN exists on [Fidelity factsheets](https://www.fidelity.co.uk/factsheet-data/factsheet/)
- Check spelling in `isins.txt`
- The fund must be publicly listed on Fidelity (institutional funds may not be)

**No historical data:**
- Very new funds may have minimal history
- The fetcher returns whatever data Fidelity provides
- Price tracking begins from first available data point

**Connection issues:**
- Codespaces generally has good internet access
- If blocked, GitHub Actions will still work (always has internet)
- Check your internet connection: `curl https://www.fidelity.co.uk`

This creates sample prices so you can test the UI locally.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| **"Data not yet available"** | Run "Fetch prices" task to populate `data/` |
| **429 Too Many Requests error** | Script retries automatically; wait a minute or try again later |
| **Port 8000 already in use** | Use port 8080: `python -m http.server 8080` |
| **"Module not found: requests"** | Run `pip install -r requirements.txt` manually |
| **Codespaces setup fails** | Check devcontainer logs; ensure internet access |
| **Cache issues** | Delete `data/` directory and re-run "Fetch prices" |
| GitHub Actions fails | Settings → Actions → General → **Read and write permissions** → Save |

---

## Contributing

Improvements welcome! The main areas:
- `scripts/fetch_prices.py` — Price fetching logic
- `index.html` — Dashboard UI and visualization
- `.github/workflows/fetch-prices.yml` — GitHub Actions workflow
