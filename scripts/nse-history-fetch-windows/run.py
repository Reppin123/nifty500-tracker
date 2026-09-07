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

FULLY SELF-DRIVING (built for an AI agent running this from a terminal, no
manual browser clicking required): pass --launch-edge and this script will
launch its own isolated Edge instance (fresh scratch profile, so it works
even if the user already has Edge open with a different flag set), wait for
its DevTools port to come up, auto-open a finance.yahoo.com tab via the CDP
HTTP API, and then fetch every symbol. One command, start to finish.

Requires (handled automatically by --launch-edge, or set up manually):
  1. Edge running with remote debugging enabled AND cross-origin websocket
     connections allowed (recent Chromium rejects the debugger websocket
     handshake from a non-browser origin unless you pass --remote-allow-origins):
       "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=<scratch dir>
  2. A tab open on finance.yahoo.com in that Edge instance — auto-opened by
     --launch-edge, or open one yourself: https://finance.yahoo.com/quote/RELIANCE.NS/history/

Usage (fully automatic, recommended for an AI agent):
  uv run --script run.py --symbols-csv <path> --symbol-col 2 --out-dir <dir> --launch-edge

Usage (manual — you already have Edge open with debugging on):
  uv run --script run.py --symbols-csv <path> --symbol-col 2 --out-dir <dir>

Resumable: skips any symbol that already has a non-trivial .json file in
--out-dir. Re-run the same command (with --launch-edge again if needed) to
pick up where it left off after a failure or interruption.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from websocket import create_connection

EDGE_PATHS_WINDOWS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_edge_path(override: str | None) -> str:
    if override:
        if not os.path.exists(override):
            raise RuntimeError(f"--edge-path {override} does not exist.")
        return override
    for p in EDGE_PATHS_WINDOWS:
        if os.path.exists(p):
            return p
    raise RuntimeError(
        "Could not find msedge.exe in the usual install locations. "
        "Pass --edge-path \"C:\\path\\to\\msedge.exe\" explicitly."
    )


def cdp_reachable(cdp_port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://localhost:{cdp_port}/json/version", timeout=2)
        return True
    except Exception:
        return False


def launch_edge(cdp_port: int, edge_path: str | None) -> None:
    """Start an isolated Edge instance with a fresh scratch profile so the
    debug-port flag is guaranteed to take effect regardless of any Edge
    windows the user already has open (Chromium ignores --remote-debugging
    -port when attaching to an already-running process on the same profile)."""
    if cdp_reachable(cdp_port):
        print(f"Edge already reachable on CDP port {cdp_port} — reusing it.", flush=True)
        return
    exe = find_edge_path(edge_path)
    profile_dir = os.path.join(tempfile.gettempdir(), f"nse_edge_profile_{cdp_port}")
    os.makedirs(profile_dir, exist_ok=True)
    print(f"Launching Edge (scratch profile, CDP port {cdp_port})...", flush=True)
    subprocess.Popen(
        [
            exe,
            f"--remote-debugging-port={cdp_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 25
    while time.time() < deadline:
        if cdp_reachable(cdp_port):
            print("Edge is up and reachable.", flush=True)
            return
        time.sleep(0.5)
    raise RuntimeError(f"Edge did not become reachable on CDP port {cdp_port} within 25s.")


def open_yahoo_tab(cdp_port: int) -> None:
    """Ask Chromium (via its HTTP debugger API) to open a new tab on Yahoo
    Finance. Newer Chromium only honors this on PUT; fall back to GET for
    older builds."""
    target = "https://finance.yahoo.com/quote/RELIANCE.NS/history/"
    url = f"http://localhost:{cdp_port}/json/new?{urllib.parse.quote(target, safe='')}"
    req = urllib.request.Request(url, method="PUT")
    try:
        urllib.request.urlopen(req, timeout=10)
        return
    except urllib.error.HTTPError:
        pass
    urllib.request.urlopen(url.replace(f"?{urllib.parse.quote(target, safe='')}", f"?{target}"), timeout=10)


def find_yahoo_tab(cdp_port: int, auto_open: bool = False) -> str:
    """Locate the debugger websocket URL of a tab whose URL is on
    finance.yahoo.com. Re-resolved every call since the tab could change —
    mirrors the Mac version's re-resolve-every-call behavior. If auto_open,
    opens one via CDP itself and polls until it's navigated there."""
    def _list_tabs():
        with urllib.request.urlopen(f"http://localhost:{cdp_port}/json/list", timeout=10) as resp:
            return json.loads(resp.read().decode())

    try:
        tabs = _list_tabs()
    except Exception as e:
        raise RuntimeError(
            f"Can't reach Edge's debugger port {cdp_port} — make sure Edge is running with "
            f"--remote-debugging-port={cdp_port} (or pass --launch-edge). ({e})"
        )
    for t in tabs:
        if t.get("type") == "page" and "finance.yahoo.com" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]

    if not auto_open:
        raise RuntimeError(
            "No Edge tab open on finance.yahoo.com — open one first "
            "(e.g. https://finance.yahoo.com/quote/RELIANCE.NS/history/), or pass --launch-edge."
        )

    print("No Yahoo Finance tab found — opening one via CDP...", flush=True)
    open_yahoo_tab(cdp_port)
    deadline = time.time() + 20
    while time.time() < deadline:
        for t in _list_tabs():
            if t.get("type") == "page" and "finance.yahoo.com" in t.get("url", ""):
                time.sleep(1.0)  # let the page finish its initial navigation
                return t["webSocketDebuggerUrl"]
        time.sleep(0.5)
    raise RuntimeError("Opened a tab but it never navigated to finance.yahoo.com in time.")


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
    ap.add_argument("--launch-edge", action="store_true",
                     help="Launch an isolated Edge instance and auto-open the Yahoo tab — no manual browser steps needed.")
    ap.add_argument("--edge-path", default=None, help="Override path to msedge.exe (or, for local testing, another Chromium binary)")
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

    if args.launch_edge:
        launch_edge(args.cdp_port, args.edge_path)

    ws_url = find_yahoo_tab(args.cdp_port, auto_open=args.launch_edge)
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
                ws_url = find_yahoo_tab(args.cdp_port, auto_open=args.launch_edge)
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
