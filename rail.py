import pygame, math
from typing import List, Tuple, Dict
from config import WIDTH, HEIGHT, CANNON_GAP
from perimeter import build_tracks

# A *rail* is an ordered list of pixel positions that hug the exposed face of
# each perimeter block.  Moving along consecutive points keeps an object firmly
# on the outer wall no matter how concave the outline is.

Vector2 = pygame.Vector2
Rect     = pygame.Rect

__all__ = ["build_rails", "RailInfo"]

class RailInfo:
    """Convenience container bundling rail data for fast look-ups."""
    def __init__(self,
                 rail_points: List[List[Vector2]],
                 block_to_rail: Dict[Tuple[int,int], Tuple[int,int]]):
        self.rail_points      = rail_points          # [track_id][idx] -> Vector2
        self.block_to_rail    = block_to_rail        # (x,y) -> (track_id, idx)

    def nearest_node(self, block_key: Tuple[int,int]):
        return self.block_to_rail.get(block_key, (0,0))

# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_rails(blocks: List[Rect], block_size: int) -> RailInfo:
    """Return RailInfo for current *blocks* layout.

    Steps:
        1.  Use perimeter.build_tracks() to get perimeter blocks in CW order.
        2.  For each perimeter block choose its *outward* side (facing away
            from castle centre) and compute a pixel position on that side.
        3.  Produce one ordered list of positions per track.
    """
    tracks, block_index = build_tracks(blocks, block_size)
    if not tracks:
        return RailInfo([], {})

    rail_points: List[List[Vector2]] = []
    block_to_rail: Dict[Tuple[int,int], Tuple[int,int]] = {}

    bs = block_size
    cx, cy = WIDTH//2, HEIGHT//2

    for tid, track in enumerate(tracks):
        pts: List[Vector2] = []
        for idx, b in enumerate(track):
            # Determine outward side (same heuristic as perimeter.build_tracks)
            dx = b.centerx - cx
            dy = b.centery - cy
            if abs(dx) > abs(dy):
                side = 'right' if dx > 0 else 'left'
            else:
                side = 'bottom' if dy > 0 else 'top'

            offset = CANNON_GAP + 3  # extra clearance for diagonal corner cuts
            if side == 'top':
                pos = Vector2(b.centerx, b.top - offset)
            elif side == 'bottom':
                pos = Vector2(b.centerx, b.bottom + offset)
            elif side == 'left':
                pos = Vector2(b.left - offset, b.centery)
            else:  # right
                pos = Vector2(b.right + offset, b.centery)

            pts.append(pos)
            block_to_rail[(b.x, b.y)] = (tid, idx)
        rail_points.append(pts)

    return RailInfo(rail_points, block_to_rail) 