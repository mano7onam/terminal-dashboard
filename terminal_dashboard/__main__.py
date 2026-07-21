"""python -m terminal_dashboard"""

from __future__ import annotations

import argparse
import sys

from .httpd import DEFAULT_PORT, run_server
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
        description=f"{APP_NAME} — live dashboard for every terminal on your Mac",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=DEFAULT_PORT,
        help=f"HTTP port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--version", "-V", action="version", version=f"{APP_NAME} {__version__}",
    )
    args = parser.parse_args(argv)
    run_server(port=args.port)


if __name__ == "__main__":
    main()
