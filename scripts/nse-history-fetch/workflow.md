# nse-history-fetch

**What it does:** Pulls N years of daily OHLCV data (default 2y, 1d bars)
from Yahoo Finance's chart API for a list of NSE-listed symbols, routed
through a live Safari tab via synchronous JS XHR instead of raw
curl/requests — this network's egress IP gets 429'd / bot-walled by Yahoo,
Stooq, NSE, and WSJ directly, but a real authenticated Safari session sails
through. Saves one raw JSON file per symbol to `--out-dir`.

**When to use:** Whenever you need bulk historical price data for a list of
NSE tickers (the Nifty 500 list, a custom watchlist, etc.) and direct
scraping is blocked. Resumable — safe to re-run after a partial failure,
it skips symbols that already have a saved file.

**Platform: macOS only.** This script shells out to `osascript` to drive
Safari via AppleScript. It will not run on Windows or Linux. If you're on
Windows, use the pre-built `NSE_Nifty500_2Y_Tracker.xlsx` in the repo root
instead of re-running this fetch — it already has 2 years of data for all
500 symbols.

**Requires:** Safari open with at least one tab on `finance.yahoo.com`
(any quote/history page works — same-origin XHR to
`query1.finance.yahoo.com` only succeeds from a page on that domain).

**How to run:**
```
uv run --script run.py \
  --symbols-csv <path/to/symbols.csv> --symbol-col 2 \
  --out-dir <path/to/raw_json_dir> \
  --range 2y --interval 1d
```
`--symbol-col` is the 0-indexed column in the CSV holding the ticker
(e.g. the Nifty 500 list from
`https://archives.nseindia.com/content/indices/ind_nifty500list.csv` has
Symbol in column index 2).

**Follow-up:** feed the output dir into `nse-sheets-build` to turn the raw
JSON into formatted Excel sheets.

**Deps:** stdlib only — no pinned packages needed.
