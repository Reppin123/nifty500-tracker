# Nifty 500 Tracker

Two-phase pipeline that builds a 2-year daily OHLCV workbook for all Nifty
500 NSE symbols, pulled from Yahoo Finance.

## For Abhishek (Windows): just use the data

`NSE_Nifty500_2Y_Tracker.xlsx` in this repo root already has 2 years of
daily OHLCV for every Nifty 500 symbol, one sheet per ticker. Download it
and open it in Excel — no script needed.

If you want to *refresh* the data yourself: `scripts/nse-history-fetch` is
**macOS-only** (it drives Safari via AppleScript to dodge Yahoo's bot-wall,
which only works on a Mac). You won't be able to run that half on Windows.
But `scripts/nse-sheets-build` (the part that turns raw JSON into the
formatted Excel sheets) is plain Python + openpyxl and runs fine on
Windows — useful if someone else fetches fresh JSON and hands it to you.

## Phase 1 — scripts/nse-history-fetch
Pulls raw OHLCV JSON per symbol from Yahoo Finance's chart API via a live
Safari tab (macOS only, avoids the 429/bot-wall raw requests hit).

## Phase 2 — scripts/nse-sheets-build
Takes that raw JSON and bulk-writes one formatted sheet per symbol
(navy header, ₹ currency format, frozen panes, banded table) into the
target workbook, via openpyxl. Cross-platform.

See each script's own `workflow.md` for exact usage.
