"""python -m terminal_dashboard"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser

from .httpd import DEFAULT_PORT, create_server, run_server
from .version import APP_NAME, __version__


def main(argv: list[str] | None = None) -> None:
    if sys.platform != "darwin":
        print(
            f"{APP_NAME} currently supports macOS only "
            f"(detected platform: {sys.platform}).",
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="terminal-dashboard",
        description=(
            f"{APP_NAME} — live dashboard for every terminal on your Mac. "
            "Default: native app window (WKWebView). Optional: browser tab."
        ),
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"HTTP port (default: {DEFAULT_PORT})",
    )
    ui = parser.add_mutually_exclusive_group()
    ui.add_argument(
        "--app",
        action="store_true",
        default=None,
        help="Open native app window with WebView (default)",
    )
    ui.add_argument(
        "--browser",
        action="store_true",
        help="Open in browser tab instead of app window",
    )
    ui.add_argument(
        "--no-open",
        action="store_true",
        help="Start server only — do not open UI (used by .app host)",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"{APP_NAME} {__version__}",
    )
    args = parser.parse_args(argv)

    # Default UI mode: app window
    if args.no_open:
        open_mode = "none"
    elif args.browser:
        open_mode = "browser"
    else:
        open_mode = "app"

    if open_mode == "none":
        run_server(port=args.port)
        return

    # Server in background + open UI, then keep process alive
    httpd = create_server(port=args.port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    url = f"http://127.0.0.1:{args.port}"
    # Wait for health
    import urllib.request

    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=0.3) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.08)

    if open_mode == "browser":
        try:
            from .browser import open_dashboard

            open_dashboard(url, mode="reuse")
        except Exception:
            webbrowser.open(url)
        print(f"{APP_NAME} v{__version__}")
        print(f"Server  {url}")
        print("UI      browser tab  (use without --browser for app window)")
        print("Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            httpd.shutdown()
        return

    # App window (default)
    from .app_window import open_app_window

    result = open_app_window(url)
    if result.get("status") != "success":
        print(
            f"warn: native window failed ({result.get('message')}); "
            "falling back to browser",
            file=sys.stderr,
        )
        try:
            from .browser import open_dashboard

            open_dashboard(url, mode="reuse")
        except Exception:
            webbrowser.open(url)

    print(f"{APP_NAME} v{__version__}")
    print(f"Server  {url}")
    print("UI      native app window (WKWebView)")
    print("         --browser  → open as browser tab instead")
    print("         --no-open  → server only")
    print("Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
