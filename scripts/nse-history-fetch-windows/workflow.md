# nse-history-fetch-windows

**What it does:** Windows sibling of `nse-history-fetch`. Same idea, different
remote-control surface: instead of driving a live Safari tab via AppleScript
(macOS-only), this drives a live Microsoft Edge tab via the Chrome DevTools
Protocol (CDP) — Edge is Chromium, so it speaks CDP natively, no extra
install needed. Both approaches run the exact same synchronous XHR JS inside
a real, already-authenticated browser tab, riding its real cookies/session to
get past Yahoo's 429/bot-wall the same way raw `curl`/`requests` can't.

Fully self-driving via `--launch-edge`: no manual browser step needed. The
script launches its own isolated Edge instance (fresh scratch profile, works
even if the user already has Edge open with different flags), waits for its
debug port to come up, auto-opens a finance.yahoo.com tab through the CDP
HTTP API, then fetches every symbol. Built this way specifically so an AI
agent running on Abhishek's machine can drive the whole thing from a
terminal with zero GUI interaction — see `AGENTS.md` at the repo root for
the exact end-to-end runbook (fetch → build workbook → verify → report).

**When to use:** On a Windows machine, whenever you need bulk historical
OHLCV data for NSE tickers and want the macOS Safari-based script's exact
behavior (same output JSON schema, same resumable/paced fetching) without
AppleScript. Output drops straight into `nse-sheets-build` unchanged.

**How to run (fully automatic, recommended):**
```
uv run --script run.py \
  --symbols-csv <path/to/symbols.csv> --symbol-col 2 \
  --out-dir <path/to/raw_json_dir> \
  --range 2y --interval 1d --launch-edge
```
If `msedge.exe` isn't at one of the standard install paths, add
`--edge-path "C:\full\path\to\msedge.exe"`.

**How to run (manual — you already have Edge open with debugging on):**
1. Launch Edge yourself with remote debugging AND cross-origin websockets
   allowed (recent Chromium rejects the debugger handshake from a
   non-browser origin unless `--remote-allow-origins` is set):
   ```
   "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --remote-allow-origins=*
   ```
2. Open any finance.yahoo.com page in it, e.g.
   `https://finance.yahoo.com/quote/RELIANCE.NS/history/`.
3. Run the same command as above, minus `--launch-edge`.

`--cdp-port` defaults to 9222 — pass `--cdp-port <N>` if using a different port.

**Follow-up:** feed the output dir into `nse-sheets-build` (cross-platform,
runs fine on Windows) to turn the raw JSON into formatted Excel sheets.

**Deps:** websocket-client==1.8.0 (pinned in the script's uv header).

**Last worked:** 2026-09-08 — validated both the manual-tab flow and the
fully self-driving `--launch-edge` flow end-to-end against a scratch Chrome
instance on macOS (same Chromium engine/protocol as Edge, so it proves the
approach): auto-launched an isolated browser process, auto-opened a Yahoo
Finance tab via the CDP HTTP API with zero pre-existing tab, ran the
synchronous XHR via `Runtime.evaluate` over the debugger websocket, and
confirmed real 200-status OHLCV data returned for RELIANCE, TCS, and INFY
with correctly schema'd JSON written to disk. Discovered and fixed the
`--remote-allow-origins` requirement (recent Chromium blocks the websocket
handshake without it). Not yet run against a real Windows/Edge instance,
but the protocol and CDP HTTP API are identical across Chromium builds.
