#!/usr/bin/env python3
"""Create a simple monochrome menu-bar template PNG (18@2x = 36px)."""
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "MenuBarIcon.png"

# 36x36 transparent, white ">" and "_" for template rendering
W = H = 36


def png_rgba(w, h, pixels):
    """pixels: list of (r,g,b,a) length w*h"""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw.extend(pixels[y * w + x])

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def main():
    # transparent canvas
    px = [(0, 0, 0, 0)] * (W * H)

    def set_pixel(x, y, a=255):
        if 0 <= x < W and 0 <= y < H:
            # white RGB — template image (macOS tints it)
            px[y * W + x] = (255, 255, 255, a)

    def thick_line(x0, y0, x1, y1, t=2):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i // steps
            y = y0 + (y1 - y0) * i // steps
            for dx in range(-t // 2, t // 2 + 1):
                for dy in range(-t // 2, t // 2 + 1):
                    set_pixel(x + dx, y + dy)

    # Draw ">_"
    # >
    thick_line(8, 10, 16, 18, 2)
    thick_line(16, 18, 8, 26, 2)
    # _
    thick_line(18, 26, 28, 26, 2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(png_rgba(W, H, px))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
