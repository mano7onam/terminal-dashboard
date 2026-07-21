"""JXA / AppleScript runners."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Optional


def jxa_escape(value) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def applescript_escape(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def run_jxa(script_content: str, timeout: float = 20.0) -> Optional[str]:
    with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as f:
        f.write(script_content.encode("utf-8"))
        temp_path = f.name
    try:
        output = subprocess.check_output(
            ["osascript", "-l", "JavaScript", temp_path],
            text=True,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return output.strip()
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip() or str(e)
        print(f"JXA error: {err}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"JXA error: {e}", file=sys.stderr)
        return None
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def run_applescript(script_content: str, timeout: float = 20.0) -> Optional[str]:
    with tempfile.NamedTemporaryFile(suffix=".applescript", delete=False) as f:
        f.write(script_content.encode("utf-8"))
        temp_path = f.name
    try:
        output = subprocess.check_output(
            ["osascript", temp_path],
            text=True,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return output.strip()
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip() or str(e)
        print(f"AppleScript error: {err}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"AppleScript error: {e}", file=sys.stderr)
        return None
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
