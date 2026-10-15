import math
import os
import struct
import zlib

import numpy as np


def write_png_rgb(path: str, pixels: np.ndarray) -> None:
    """Write an 8-bit RGB PNG with no third-party imaging dependency."""
    height, width, _channels = pixels.shape
    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter type 0
        raw.extend(pixels[row].tobytes())

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        handle.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        handle.write(chunk(b"IEND", b""))


def value_noise(size: int, cells: int, seed: int) -> np.ndarray:
    """Cheap tileable-ish value noise, bilinearly upsampled."""
    rng = np.random.default_rng(seed)
    grid = rng.random((cells + 1, cells + 1)).astype(np.float32)

    ys = np.linspace(0, cells, size, endpoint=False)
    xs = np.linspace(0, cells, size, endpoint=False)
    x0 = xs.astype(np.int32)
    y0 = ys.astype(np.int32)
    fx = (xs - x0)[None, :]
    fy = (ys - y0)[:, None]

    v00 = grid[np.ix_(y0, x0)]
    v10 = grid[np.ix_(y0, x0 + 1)]
    v01 = grid[np.ix_(y0 + 1, x0)]
    v11 = grid[np.ix_(y0 + 1, x0 + 1)]

    top = v00 + (v10 - v00) * fx
    bottom = v01 + (v11 - v01) * fx
    return top + (bottom - top) * fy


def make_grass_texture(size: int = 512) -> np.ndarray:
    """
    A neutral, mid-tone grass-ish texture.

    Deliberately low contrast and mid brightness: the v1 terrain shader multiplies this over the
    whole terrain, and `diffuseSize` sets how many metres one tile covers, so a busy texture
    would look like noise from a car.  Mid-tone also means the macro/detail overlays have room
    to move in both directions.
    """
    coarse = value_noise(size, 8, 1)
    medium = value_noise(size, 32, 2)
    fine = value_noise(size, 96, 3)

    blend = 0.55 * coarse + 0.30 * medium + 0.15 * fine
    blend = (blend - blend.min()) / max(blend.max() - blend.min(), 1e-6)

    # Base grass green, with brightness following the noise.
    base = np.array([0.36, 0.46, 0.24], dtype=np.float32)
    variation = (blend - 0.5)[:, :, None] * 0.30
    rgb = np.clip(base[None, None, :] + variation, 0.0, 1.0)

    # A touch of fine speckle so close-up terrain is not flat.
    speckle = (value_noise(size, 256, 4) - 0.5)[:, :, None] * 0.06
    rgb = np.clip(rgb + speckle, 0.0, 1.0)

    return (rgb * 255.0 + 0.5).astype(np.uint8)


if __name__ == "__main__":
    out = os.path.join(
        r"D:\Developer\open source projects\cities-skylines-to-beamng-map", "build", "grass_preview.png"
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_png_rgb(out, make_grass_texture())
    print("wrote", out, os.path.getsize(out), "bytes")
