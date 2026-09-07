# nse-history-fetch-windows

**What it does:** Windows sibling of `nse-history-fetch`. Same idea, different
remote-control surface: instead of driving a live Safari tab via AppleScript
(macOS-only), this drives a live Microsoft Edge tab via the Chrome DevTools
Protocol (CDP) — Edge is Chromium, so it speaks CDP natively, no extra
install needed. Both approaches run the exact same synchronous XHR JS inside
a real, already-authenticated browser tab, riding its real cookies/session to
get past Yahoo's 429/bot-wall the same way raw `curl`/`requests` can't.

**When to use:** On a Windows machine, whenever you need bulk historical
OHLCV data for NSE tickers and want the macOS Safari-based script's exact
behavior (same output JSON schema, same resumable/paced fetching) without
AppleScript. Output drops straight into `nse-sheets-build` unchanged.

**Setup (one-time per session):**
1. Launch Edge with remote debugging enabled AND cross-origin websockets
   allowed. Recent Chromium rejects the debugger handshake from a
   non-browser origin (this script) unless `--remote-allow-origins` is set:
   ```
   "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --remote-allow-origins=*
   ```
2. In that Edge window, open any finance.yahoo.com page, e.g.
   `https://finance.yahoo.com/quote/RELIANCE.NS/history/`.

**How to run:**
```
uv run --script run.py \
  --symbols-csv <path/to/symbols.csv> --symbol-col 2 \
  --out-dir <path/to/raw_json_dir> \
  --range 2y --interval 1d
```
`--cdp-port` defaults to 9222 (matches the launch command above) — pass
`--cdp-port <N>` if you launched Edge on a different port.

**Follow-up:** feed the output dir into `nse-sheets-build` (cross-platform,
runs fine on Windows) to turn the raw JSON into formatted Excel sheets.

**Deps:** websocket-client==1.8.0 (pinned in the script's uv header).

**Last worked:** 2026-09-08 — validated the CDP mechanism end-to-end against
a scratch Chrome instance on macOS (same Chromium engine/protocol as Edge,
so it proves the approach): found the tab via `/json/list`, ran the
synchronous XHR via `Runtime.evaluate` over the debugger websocket, confirmed
real 200-status OHLCV data returned for RELIANCE and TCS and wrote correctly
schema'd JSON files. Discovered and fixed the `--remote-allow-origins`
requirement (recent Chromium blocks the websocket handshake without it) —
not yet run against a real Windows/Edge instance, but the protocol is
identical.
