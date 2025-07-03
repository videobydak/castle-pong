"""reinforced_blocks.py

Utility helpers for multi-layer castle wall generation and wave planning.

This module is intentionally independent from the existing cg/Castle code so
that the reinforcement logic can evolve without touching the heavy gameplay
modules.  It exposes three public helpers:

    • get_layer_probabilities(difficulty):  Given a difficulty percentage
      (0-100) returns a (p1, p2, p3) probability triple for wall layers 1,2,3.

    • apply_reinforcement_layers(mask, difficulty):  Takes a 2-D numpy mask
      produced by cg.CastleGenerator and _in-place_ converts some layer-1 walls
      (value 2) to layer-2 (value 3) or layer-3 (value 4) according to the
      probability triple.  The algorithm favours blocks that are closer to the
      centre of the keep and enforces four-axis symmetry so the visual layout
      remains harmonious.

    • plan_waves(mask, num_waves):  Organises blocks into progressive build
      waves so that early waves only use layer-1 bricks (optionally capped) and
      later waves introduce tougher layers.  The return value is a list where
      index 0 is wave 1, each entry containing an ordered list of (y,x)
      coordinates.

All functions are *pure* – no external imports beyond numpy and the existing
cg.BlockType enum.  This makes unit-testing trivial.
"""

from __future__ import annotations

from typing import List, Tuple
import numpy as np
import random
import math

try:
    # Local import (avoids circularity when cg imports us back)
    from cg import BlockType
except ImportError:
    # Stand-alone usage (unit tests) — caller must monkey-patch BlockType.
    BlockType = None  # type: ignore

# ---------------------------------------------------------------------------
#  Difficulty → probability mapping
# ---------------------------------------------------------------------------

_LOW_THRESHOLD  = 20   # ≤ 20 %: only layer-1 bricks
_MID_REFERENCE  = 50   # example mid-range difficulty
_HIGH_THRESHOLD = 80   # ≥ 80 %: only layer-3 bricks

# Example ratio for 50 % difficulty given in the spec
_REF_RATIO = (0.3, 0.5, 0.2)  # (layer1, layer2, layer3)


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation helper."""
    return a + (b - a) * t


def get_layer_probabilities(difficulty: int | float) -> Tuple[float, float, float]:
    """Return a probability triple (layer1, layer2, layer3) based on *difficulty*.

    Uses granular, piecewise linear interpolation based on user-specified anchor points.
    """
    d = float(max(0, min(100, difficulty)))

    # Define anchor points as (difficulty, (p1, p2, p3))
    anchors = [
        (5,   (1.0, 0.0, 0.0)),   # Wave 1
        (10,  (0.67, 0.33, 0.0)),   # Wave 2
        (15,  (0.6, 0.4, 0.0)),  # Wave 3 – 5 % layer-2 only
        (20,  (0.65, 0.35, 0.0)),  # Wave 4 – 15 % layer-2, still no layer-3
        (25,  (0.70, 0.20, 0.1)), # Wave 5 – first small batch of layer-3
        (50,  (0.3, 0.5, 0.2)),   # Reference
        (60,  (0.18, 0.52, 0.3)), # More gradual
        (65,  (0.12, 0.48, 0.4)), # More gradual
        (70,  (0.06, 0.36, 0.58)),# More gradual
        (75,  (0.0, 0.2, 0.8)),   # Near max
        (80,  (0.0, 0.0, 1.0)),   # Max (all layer 3)
    ]

    # If below first anchor, return first
    if d <= anchors[0][0]:
        return anchors[0][1]
    # If above last anchor, return last
    if d >= anchors[-1][0]:
        return anchors[-1][1]

    # Find which two anchors d is between
    for i in range(1, len(anchors)):
        d0, p0 = anchors[i-1]
        d1, p1 = anchors[i]
        if d0 <= d <= d1:
            t = (d - d0) / (d1 - d0)
            l1 = p0[0] + (p1[0] - p0[0]) * t
            l2 = p0[1] + (p1[1] - p0[1]) * t
            l3 = p0[2] + (p1[2] - p0[2]) * t
            return l1, l2, l3
    # Fallback (should not reach here)
    return anchors[-1][1]

# ---------------------------------------------------------------------------
#  Reinforcement layer application
# ---------------------------------------------------------------------------

def _symmetry_group(h: int, w: int, y: int, x: int):
    """Yield coordinates symmetric to (y,x) across the four main axes."""
    coords = set([
        (y, x),
        (y, w - 1 - x),
        (h - 1 - y, x),
        (h - 1 - y, w - 1 - x),
        (x, y),
        (x, h - 1 - y),
        (w - 1 - x, y),
        (w - 1 - x, h - 1 - y),
    ])
    for cy, cx in coords:
        if 0 <= cy < h and 0 <= cx < w:
            yield cy, cx


def apply_reinforcement_layers(mask: np.ndarray, difficulty: int | float, *, rng: random.Random | None = None) -> np.ndarray:
    """Upgrade layer-1 bricks in *mask* to layer-2 or layer-3 according to difficulty.

    The operation is performed *in-place* and the same array is returned for
    convenience.  Symmetry is preserved by always treating sets of symmetric
    coordinates as a unit.
    """
    if rng is None:
        rng = random

    if mask is None:
        raise ValueError("mask cannot be None")

    h, w = mask.shape
    centre = (h / 2.0, w / 2.0)
    max_dist = math.hypot(centre[0], centre[1]) or 1.0

    p1, p2, p3 = get_layer_probabilities(difficulty)

    # Fast-path extremes
    if p1 == 1.0:
        return mask  # nothing changes
    if p3 == 1.0:
        mask[mask == 2] = 4
        return mask

    # Build symmetry groups starting from centre outwards
    visited = np.zeros_like(mask, dtype=bool)
    groups: list[tuple[float, list[tuple[int, int]]]] = []

    for y in range(h):
        for x in range(w):
            if mask[y, x] != 2 or visited[y, x]:
                continue
            coords = list(_symmetry_group(h, w, y, x))
            for cy, cx in coords:
                visited[cy, cx] = True
            dist = math.hypot(y - centre[0], x - centre[1])
            groups.append((dist, coords))

    groups.sort(key=lambda t: t[0])  # near-centre first

    total_walls = sum(len(c) for _, c in groups)
    target_l2 = int(round(total_walls * p2))
    target_l3 = int(round(total_walls * p3))
    placed_l2 = placed_l3 = 0

    for dist, coords in groups:
        # Determine eligible layers based on remaining quota
        choices: list[int] = []  # values: 3 or 4
        weights: list[float] = []
        near_factor = 1.0 - (dist / max_dist)

        if placed_l3 < target_l3:
            choices.append(4)
            # Strong preference for central groups when placing layer-3 bricks
            weights.append(max(0.05, near_factor) * (target_l3 - placed_l3))
        if placed_l2 < target_l2:
            choices.append(3)
            # layer-2 bricks distributed a bit more evenly
            weights.append(max(0.05, 0.5 + (near_factor - 0.5)) * (target_l2 - placed_l2))

        if not choices:
            continue

        sel = rng.choices(choices, weights=weights, k=1)[0]
        for cy, cx in coords:
            if mask[cy, cx] == 2:
                mask[cy, cx] = sel
        if sel == 4:
            placed_l3 += len(coords)
        else:
            placed_l2 += len(coords)
        if placed_l2 >= target_l2 and placed_l3 >= target_l3:
            break

    return mask

# ---------------------------------------------------------------------------
#  Wave planning helper
# ---------------------------------------------------------------------------

def plan_waves(mask: np.ndarray, num_waves: int = 10, *, max_first_wave: int = 4, min_second_wave: int = 5) -> List[List[Tuple[int, int]]]:
    """Return a list of block coordinate lists for each wave.

    Guarantees:
    • Wave-1: only layer-1 bricks (value 2), capped at *max_first_wave*.
    • Wave-2: ≥ *min_second_wave* bricks.
    • Wave-10 (or final): prioritises layer-3 bricks.
    """
    h, w = mask.shape
    layers: dict[int, list[tuple[int, int]]] = {2: [], 3: [], 4: []}
    centre = (h / 2.0, w / 2.0)

    for y in range(h):
        for x in range(w):
            val = mask[y, x]
            if val in layers:
                layers[val].append((y, x))

    # sort by centrality (closer first)
    for key in layers:
        layers[key].sort(key=lambda p: math.hypot(p[0] - centre[0], p[1] - centre[1]))

    waves: List[List[Tuple[int, int]]] = [[] for _ in range(num_waves)]

    # Wave 1
    waves[0] = layers[2][:max_first_wave]
    layers[2] = layers[2][max_first_wave:]

    # Wave 2
    need = max(0, min_second_wave - len(waves[1]))
    take_l1 = min(len(layers[2]), need)
    waves[1].extend(layers[2][:take_l1])
    layers[2] = layers[2][take_l1:]
    need -= take_l1
    if need > 0:
        take_l2 = min(len(layers[3]), need)
        waves[1].extend(layers[3][:take_l2])
        layers[3] = layers[3][take_l2:]

    # Middle waves (3 .. num_waves-2)
    remaining_waves = max(0, num_waves - 3)
    all_mid = layers[2] + layers[3]
    per_wave = math.ceil(len(all_mid) / max(1, remaining_waves)) if remaining_waves else 0
    idx = 0
    for wv in range(2, num_waves - 1):
        waves[wv].extend(all_mid[idx: idx + per_wave])
        idx += per_wave

    # Final wave – dump everything left, prioritising layer-3 bricks
    waves[-1].extend(layers[4] + layers[3] + layers[2])

    return waves 