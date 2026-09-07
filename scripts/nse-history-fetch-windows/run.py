# /// script
# requires-python = ">=3.9"
# dependencies = ["websocket-client==1.8.0"]
# ///
"""
nse-history-fetch-windows — Windows sibling of nse-history-fetch (macOS).

Identical idea, different OS mechanism: the Mac version drives a live Safari
tab via AppleScript to run a synchronous XHR in a real, already-authenticated
browser session (rides the browser's own cookies/session to dodge Yahoo's
429/bot-wall that raw requests/curl hit). Windows has no AppleScript, but
Edge (Chromium, ships with every Windows install) exposes the exact same
capability through the Chrome DevTools Protocol (CDP): connect to a live tab
and run JS inside its real JS engine, same session, same cookies. Same trick,
different remote control surface.

Requires:
  1. Edge launched with remote debugging enabled AND cross-origin websocket
     connections allowed (recent Chromium rejects the debugger websocket
     handshake from a non-browser origin like this script unless you pass
     --remote-allow-origins):
       "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222 --remote-allow-origins=*
  2. At least one tab open on finance.yahoo.com in that Edge instance
     (e.g. https://finance.yahoo.com/quote/RELIANCE.NS/history/).

Usage:
  uv run --script run.py --symbols-csv <path> --symbol-col 2 --out-dir <dir> [--range 2y] [--interval 1d]

Resumable: skips any symbol that already has a non-trivial .json file in
--out-dir. Re-run the same command to pick up where it left off after a
failure or interruption.
"""
import argparse
import csv
import json
import os
import time
import urllib.parse
import urllib.request

from websocket import create_connection


def find_yahoo_tab(cdp_port: int) -> str:
    """Locate the debugger websocket URL of a tab whose URL is on
    finance.yahoo.com. Re-resolved every call since the user could switch/
    close tabs — mirrors the Mac version's re-resolve-every-call behavior."""
    try:
        with urllib.request.urlopen(f"http://localhost:{cdp_port}/json/list", timeout=10) as resp:
            tabs = json.loads(resp.read().decode())
    except Exception as e:
        raise RuntimeError(
            f"Can't reach Edge's debugger port {cdp_port} — make sure Edge is running with "
            f"--remote-debugging-port={cdp_port}. ({e})"
        )
    for t in tabs:
        if t.get("type") == "page" and "finance.yahoo.com" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    raise RuntimeError(
        "No Edge tab open on finance.yahoo.com — open one first "
        "(e.g. https://finance.yahoo.com/quote/RELIANCE.NS/history/)."
    )


def fetch_symbol(symbol: str, suffix: str, range_: str, interval: str, ws_url: str) -> tuple[str, str]:
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
    ws = create_connection(ws_url, timeout=30)
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True, "awaitPromise": False},
        }))
        raw = ws.recv()
    finally:
        ws.close()
    reply = json.loads(raw)
    value = reply.get("result", {}).get("result", {}).get("value", "")
    status, _, body = value.partition("|")
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
    ap.add_argument("--cdp-port", type=int, default=9222, help="Edge --remote-debugging-port")
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
    ws_url = find_yahoo_tab(args.cdp_port)
    print(f"Using Edge tab (finance.yahoo.com) via CDP port {args.cdp_port}", flush=True)

    for i, sym in enumerate(symbols, 1):
        out_path = os.path.join(args.out_dir, f"{sym}.json")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
            skipped += 1
            done += 1
            continue
        try:
            status, body = fetch_symbol(sym, args.suffix, args.range, args.interval, ws_url)
            if status == "":
                # tab may have moved/closed — re-resolve once and retry
                ws_url = find_yahoo_tab(args.cdp_port)
                status, body = fetch_symbol(sym, args.suffix, args.range, args.interval, ws_url)
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
        except Exception:
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
