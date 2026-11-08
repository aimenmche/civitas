"""Deterministic value noise used for procedural world generation."""
from __future__ import annotations

import math


def _hash2(ix: int, iy: int, seed: int) -> float:
    h = (ix * 374761393 + iy * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFFFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFFFF) / 0xFFFFFF


def smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def value_noise(x: float, y: float, seed: int) -> float:
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = smooth(x - x0), smooth(y - y0)
    v00 = _hash2(x0, y0, seed)
    v10 = _hash2(x0 + 1, y0, seed)
    v01 = _hash2(x0, y0 + 1, seed)
    v11 = _hash2(x0 + 1, y0 + 1, seed)
    return lerp(lerp(v00, v10, fx), lerp(v01, v11, fx), fy)


def fbm(
    x: float,
    y: float,
    seed: int,
    octaves: int = 5,
    lacunarity: float = 2.0,
    gain: float = 0.5,
) -> float:
    amplitude = 1.0
    frequency = 1.0
    total = 0.0
    norm = 0.0
    for _ in range(octaves):
        total += value_noise(x * frequency, y * frequency, seed) * amplitude
        norm += amplitude
        amplitude *= gain
        frequency *= lacunarity
    return total / norm if norm else 0.0


def ridge_noise(x: float, y: float, seed: int, octaves: int = 4) -> float:
    total = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        n = value_noise(x * freq, y * freq, seed)
        n = 1.0 - abs(n * 2.0 - 1.0)
        total += n * amp
        norm += amp
        amp *= 0.5
        freq *= 2.1
    return total / norm if norm else 0.0


def hash_float(*parts: int) -> float:
    return _hash2(int(parts[0]), int(parts[-1]), int(sum(parts) * 17 + 3))
