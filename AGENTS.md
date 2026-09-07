# Agent instructions — run this pipeline end-to-end on Windows

You are an AI coding agent with terminal access on a Windows machine. Follow
these steps in order and verify each one before moving to the next. Nothing
here needs the human to click anything in a browser — it's all terminal
commands.

## 0. Prerequisites

Check `uv` is installed:
```
uv --version
```
If it's missing, install it and restart your shell:
```
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Microsoft Edge ships with Windows by default, so nothing to install there —
the fetch script finds it automatically at the standard install path. If it
reports it can't find `msedge.exe`, pass its path explicitly with
`--edge-path "C:\path\to\msedge.exe"`.

## 1. Phase 1 — fetch raw OHLCV JSON

Run this from the repo root:
```
uv run --script scripts/nse-history-fetch-windows/run.py --symbols-csv nifty500_raw.csv --symbol-col 2 --out-dir raw_json --launch-edge
```
`nifty500_raw.csv` is already in this repo root (the full Nifty 500 symbol
list, `Symbol` is column index 2) — that exact command works as-is, no
substitution needed. Only swap it out if you want a different/custom ticker
list.

This single command is fully self-driving: it launches its own isolated Edge
window with a scratch profile (works even if the user already has Edge open
with something else), auto-opens a finance.yahoo.com tab through the
DevTools Protocol, and fetches every symbol through it. A browser window
will visibly pop up on screen — that's expected, don't close it, it closes
itself implicitly when done (or leave it, it's an isolated scratch profile).

**Verify before moving on:** `raw_json/` should contain one `<SYMBOL>.json`
file per row in the symbols CSV. If `raw_json/_failed.txt` exists, open it —
a handful of failures is normal (delisted/renamed tickers), but if most
symbols failed, just re-run the exact same command. It's resumable (skips
symbols it already fetched), and Yahoo occasionally just needs a retry.

## 2. Phase 2 — build the Excel workbook

Close the target workbook in Excel first if it happens to be open —
`openpyxl` writing underneath an open Excel process can corrupt the save.

Run:
```
uv run --script scripts/nse-sheets-build/run.py --workbook NSE_Nifty500_2Y_Tracker.xlsx --raw-dir raw_json --skip-existing
```

**Verify before reporting done:**
```
python -c "from openpyxl import load_workbook; wb=load_workbook('NSE_Nifty500_2Y_Tracker.xlsx', read_only=True); print(len(wb.sheetnames), 'sheets')"
```
The sheet count should roughly match the number of symbols fetched in
Phase 1 (one sheet per ticker).

## 3. Report back to the human

Tell them: how many symbols were fetched, how many failed (list the
tickers if any), and confirm the workbook is ready with its final sheet
count. If Phase 1 had a high failure rate even after a retry, say so
explicitly rather than silently shipping a partial workbook.

## Troubleshooting

- **"Could not find msedge.exe"** — pass `--edge-path "C:\full\path\to\msedge.exe"`.
- **Edge launches but the fetch script can't reach it** — a firewall/AV
  tool may be blocking localhost traffic on the CDP port; try a different
  `--cdp-port` value.
- **Everything in `_failed.txt`** — Yahoo occasionally rate-limits even
  browser-authenticated sessions if you fetch too fast; the script already
  paces requests (`--pace`, default 0.3s) — try raising it, e.g. `--pace 1.0`,
  and re-run (it resumes, won't refetch what already succeeded).
