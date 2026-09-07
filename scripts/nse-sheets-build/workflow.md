# nse-sheets-build

**What it does:** Bulk-writes per-symbol Yahoo chart JSON (produced by
`nse-history-fetch`) into one formatted Excel sheet per symbol, via
openpyxl on a CLOSED workbook file. Sheet name is set to the exact ticker
symbol so a Pushpender-style tracker tab's
`=IF(ISREF(INDIRECT("'"&Symbol&"'!A1")),HYPERLINK(...),"— no data sheet
yet")` auto-detect formula lights up the instant a sheet lands — no manual
linking needed. Applies: bold white-on-navy header, date format on Date,
₹ currency format on OHLC + Adj Close, comma format on Volume, frozen
header row, a banded Excel Table.

**Platform: cross-platform.** Pure Python + openpyxl — runs fine on
Windows, Linux, or macOS.

**When to use:** After running `nse-history-fetch` (or anytime you have a
folder of Yahoo chart-API JSON files keyed `<SYMBOL>.json`) and want them
materialized as sheets in a tracker workbook.

**CRITICAL:** the target workbook MUST be closed in Excel before running
this — openpyxl writing underneath an open Excel process can corrupt the
save or hang.

**How to run:**
```
uv run --script run.py \
  --workbook <path/to/workbook.xlsx> \
  --raw-dir <path/to/raw_json_dir> \
  [--skip-existing]
```
`--skip-existing` skips symbols that already have a matching sheet name —
useful for incremental/resumed runs so you don't blow away sheets that are
already correct.

**Deps:** openpyxl==3.1.5 (pinned in the script's uv header).
