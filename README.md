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

## Phase 1 (macOS) — scripts/nse-history-fetch
Pulls raw OHLCV JSON per symbol from Yahoo Finance's chart API via a live
Safari tab (macOS only, avoids the 429/bot-wall raw requests hit).

## Phase 1 (Windows) — scripts/nse-history-fetch-windows
Same idea as the macOS version, but drives a live Microsoft Edge tab via the
Chrome DevTools Protocol instead of AppleScript (Edge is Chromium, so it
speaks CDP natively). Same output schema, same resumable/paced fetching,
just a Windows-native remote-control surface instead of Safari — and it's
fully self-driving (`--launch-edge` launches its own Edge instance and
auto-opens the tab, no manual browser step). See its `workflow.md` for
details.

## Running this with your own AI agent (Abhishek, start here)
If you're handing this repo to an AI coding agent (Claude, ChatGPT with
terminal/computer-use access, etc.) and want it to run the whole pipeline
for you — fetch the data, build the workbook, verify the result — point it
at **`AGENTS.md`** in this repo root. It's a full step-by-step runbook
written for an agent to execute autonomously from a terminal, no manual
browser clicking required on your end.

## Phase 2 — scripts/nse-sheets-build
Takes that raw JSON and bulk-writes one formatted sheet per symbol
(navy header, ₹ currency format, frozen panes, banded table) into the
target workbook, via openpyxl. Cross-platform.

`nifty500_raw.csv` in this repo root is the full Nifty 500 symbol list
(Company Name, Industry, Symbol, Series, ISIN Code — `Symbol` is column
index 2) that both fetch scripts expect by default.

See each script's own `workflow.md` for exact usage.
