# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
nse-history-fetch — pull N years of daily OHLCV for a list of NSE symbols via
Yahoo Finance's chart API, routed through a live Safari tab (JS synchronous
XHR) so it rides the browser's own session instead of getting 429'd like raw
curl/requests does on this network.

Usage:
  uv run --script run.py --symbols-csv <path> --symbol-col 2 --out-dir <dir> [--range 2y] [--interval 1d]

Requires: Safari open with any finance.yahoo.com tab loaded (same-origin XHR
to query1.finance.yahoo.com only works from a page on that domain).

MAC ONLY: this script shells out to `osascript` to drive Safari via
AppleScript. It cannot run on Windows or Linux. See README for the
Windows-friendly alternative.

Resumable: skips any symbol that already has a non-trivial .json file in
--out-dir. Re-run the same command to pick up where it left off after a
failure or interruption.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.parse


def find_yahoo_tab() -> tuple[int, int]:
    """Locate the Safari window/tab index whose URL is on finance.yahoo.com.
    Front document can silently change (user switches tabs/windows), so we
    re-resolve this every call rather than trusting 'front document'."""
    script = '''
    tell application "Safari"
        repeat with w in windows
            set winIndex to index of w
            repeat with t in tabs of w
                if (URL of t) contains "finance.yahoo.com" then
                    return (winIndex as string) & ":" & (index of t as string)
                end if
            end repeat
        end repeat
        return "NONE"
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    out = result.stdout.strip()
    if out == "NONE" or not out:
        raise RuntimeError(
            "No Safari tab open on finance.yahoo.com — open one first "
            "(e.g. https://finance.yahoo.com/quote/RELIANCE.NS/history/)."
        )
    w, t = out.split(":")
    return int(w), int(t)


def fetch_symbol(symbol: str, suffix: str, range_: str, interval: str, win: int, tab: int) -> tuple[str, str]:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}{suffix}?range={range_}&interval={interval}"
    )
    js = (
        'var x=new XMLHttpRequest();'
        f'x.open("GET","{url}",false);'
        'x.send();'
        'x.status + "|" + x.responseText'
    )
    script = (
        f'tell application "Safari" to do JavaScript {json.dumps(js)} '
        f'in tab {tab} of window {win}'
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=30
    )
    out = result.stdout.strip()
    status, _, body = out.partition("|")
    return status.strip(), body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols-csv", required=True, help="CSV with a symbol column")
    ap.add_argument("--symbol-col", type=int, default=2, help="0-indexed column with the ticker symbol")
    ap.add_argument("--has-header", action="store_true", default=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--suffix", default=".NS", help="Exchange suffix appended to symbol, e.g. .NS")
    ap.add_argument("--range", default="2y")
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--pace", type=float, default=0.3, help="seconds to sleep between requests")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    with open(args.symbols_csv) as f:
        rows = list(csv.reader(f))
    if args.has_header:
        rows = rows[1:]
    symbols = [r[args.symbol_col] for r in rows if len(r) > args.symbol_col and r[args.symbol_col]]

    total = len(symbols)
    done = 0
    failed = []
    skipped = 0

    print(f"Starting fetch: {total} symbols, range={args.range}, interval={args.interval}", flush=True)
    win, tab = find_yahoo_tab()
    print(f"Using Safari tab {tab} of window {win} (finance.yahoo.com)", flush=True)

    for i, sym in enumerate(symbols, 1):
        out_path = os.path.join(args.out_dir, f"{sym}.json")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
            skipped += 1
            done += 1
            continue
        try:
            status, body = fetch_symbol(sym, args.suffix, args.range, args.interval, win, tab)
            if status == "" :
                # tab may have moved/closed — re-resolve once and retry
                win, tab = find_yahoo_tab()
                status, body = fetch_symbol(sym, args.suffix, args.range, args.interval, win, tab)
            if status == "200" and body:
                parsed = json.loads(body)
                if parsed.get("chart", {}).get("result"):
                    with open(out_path, "w") as f:
                        f.write(body)
                    done += 1
                else:
                    failed.append(sym)
            else:
                failed.append(sym)
        except Exception as e:
            failed.append(sym)
        if i % 20 == 0 or i == total:
            print(f"[{i}/{total}] fetched={done} (skipped={skipped}) failed={len(failed)}", flush=True)
        time.sleep(args.pace)

    print(f"DONE. fetched={done} failed={len(failed)} of {total}", flush=True)
    if failed:
        fail_path = os.path.join(args.out_dir, "_failed.txt")
        with open(fail_path, "w") as f:
            f.write("\n".join(failed))
        print(f"Failed symbols written to {fail_path}", flush=True)


if __name__ == "__main__":
    main()
