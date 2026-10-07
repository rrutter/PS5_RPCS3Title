#!/usr/bin/env python3
"""PS5 RPCS3 - the title's home-screen art, written into ps5/sce_sys/.

    title-art.py

- icon0.png: 512x512, from ps5/art/icon-source.webp.
- pic0.dds, pic1.dds: the background the home screen shows behind the title,
  3840x2160, from ps5/art/background-source.webp (scaled to cover, centred),
  as the console takes it (skills/ps5-homebrew/references/title-packaging.md):
  DDS with a DX10 header, BC7_UNORM, one level, straight alpha, flags 0xA1007.

Needs Pillow and etcpak (pip install etcpak). Run once; commit what it writes.
"""

import struct
from pathlib import Path

import etcpak
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "ps5" / "art"
SCE_SYS = ROOT / "ps5" / "sce_sys"

WIDTH, HEIGHT = 3840, 2160


def cover(image, width, height):
    """Scaled to fill width x height, the overflow cut evenly from both sides."""
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def dds_bc7(image):
    rgba = image.convert("RGBA")
    blocks = etcpak.compress_bc7(rgba.tobytes(), rgba.width, rgba.height)
    linear_size = (rgba.width // 4) * (rgba.height // 4) * 16
    assert len(blocks) == linear_size

    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000  # caps, height, width, pixel format, mip count, linear size
    header = struct.pack("<4sIIIIIII11I", b"DDS ", 124, flags, rgba.height, rgba.width, linear_size, 1, 1, *([0] * 11))
    pixel_format = struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    caps = struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)
    dx10 = struct.pack("<IIIII", 98, 3, 0, 1, 1)  # BC7_UNORM, 2D, no flags, one image, straight alpha
    return header + pixel_format + caps + dx10 + blocks


def main():
    icon = cover(Image.open(ART / "icon-source.webp").convert("RGB"), 512, 512)
    icon.save(SCE_SYS / "icon0.png", optimize=True)
    print("wrote ps5/sce_sys/icon0.png")

    background = cover(Image.open(ART / "background-source.webp").convert("RGB"), WIDTH, HEIGHT)
    data = dds_bc7(background)
    for name in ("pic0.dds", "pic1.dds"):
        (SCE_SYS / name).write_bytes(data)
        print(f"wrote ps5/sce_sys/{name} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
