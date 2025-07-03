import pygame, math
from typing import List, Dict, Tuple, Set
from config import WIDTH, HEIGHT

__all__ = ["build_tracks", "is_enclosed_tile"]

# --- Helper datatypes ---------------------------------------------------
Rect = pygame.Rect
Track = List[Rect]  # ordered list of perimeter blocks

# ------------------------------------------------------------------------
# Pocket detection helper
# ------------------------------------------------------------------------

def is_enclosed_tile(cell: Tuple[int, int], blocks_set: Set[Tuple[int, int]], block_size: int) -> bool:
    """Return True if *cell* is surrounded on all 4 cardinal sides by castle blocks.

    This helps us identify *pocket* cavities – single empty tiles completely
    boxed in by walls.  Cannons must avoid aiming into such spaces because it
    would cause them to shoot the castle interior.
    """
    x, y = cell
    # Offsets to the four neighbours (N, E, S, W)
    neighbours = ((0, -block_size), (block_size, 0), (0, block_size), (-block_size, 0))
    return all((x + dx, y + dy) in blocks_set for dx, dy in neighbours)

# ------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------

def build_tracks(blocks: List[Rect], block_size: int) -> Tuple[List[Track], Dict[Tuple[int,int], Tuple[int,int]]]:
    """Return a list of perimeter *tracks* for the supplied *blocks*.

    A *track* is an **ordered** list of perimeter blocks (pygame.Rect).

    The algorithm is intentionally simple:
        1.  First, find **perimeter blocks** – those that have at least one of the
            4-neighbour cells empty.
        2.  Build a 4-neighbour adjacency graph of those perimeter blocks.
        3.  Find connected components of that graph.  Each component corresponds
            to one *shape* (which might include concave outlines or holes – we
            only care about the outer ring).
        4.  Order the blocks in each component in **clockwise** order around the
            component centroid.  This is fast, stable and perfectly adequate for
            driving the cannons along the wall.  It also gracefully handles
            concave shapes because we only use the centroid-angle for *sorting* –
            it doesn't try to trace the outline one edge at a time.

    The function returns:
        tracks : list[list[Rect]]      – ordered perimeter blocks for each shape
        block_index_map : { (x,y) -> (track_id, index_in_track) }
    """
    if not blocks:
        return [], {}

    # ---------------------------------------------------
    # 1) Identify perimeter blocks
    # ---------------------------------------------------
    existing = {(b.x, b.y) for b in blocks}
    perims: List[Rect] = []
    bs = block_size
    for b in blocks:
        # check 4-neighbour cells (N,E,S,W)
        if any((b.x + dx, b.y + dy) not in existing for dx,dy in ((0,-bs),(bs,0),(0,bs),(-bs,0))):
            perims.append(b)

    if not perims:
        return [], {}

    # Filter perims to those whose *furthest* exposed side faces away from centre
    filtered = []
    for b in perims:
        dx = b.centerx - WIDTH//2
        dy = b.centery - HEIGHT//2
        # Determine cardinal direction outward
        if abs(dx) > abs(dy):
            outward_side = 'right' if dx > 0 else 'left'
        else:
            outward_side = 'bottom' if dy > 0 else 'top'
        # neighbour in outward direction
        if outward_side == 'top' and (b.x, b.y - bs) not in existing:
            filtered.append(b)
        elif outward_side == 'bottom' and (b.x, b.y + bs) not in existing:
            filtered.append(b)
        elif outward_side == 'left' and (b.x - bs, b.y) not in existing:
            filtered.append(b)
        elif outward_side == 'right' and (b.x + bs, b.y) not in existing:
            filtered.append(b)
    perims = filtered

    # ---------------------------------------------------
    # 2) Build adjacency among perimeter blocks (8-neighbour)
    # ---------------------------------------------------
    adj: Dict[Tuple[int,int], List[Tuple[int,int]]] = {}
    for a in perims:
        a_key = (a.x, a.y)
        adj[a_key] = []
        for b in perims:
            if a is b:
                continue
            # 8-neighbor adjacency: horizontal, vertical, and diagonal
            dx, dy = abs(a.x - b.x), abs(a.y - b.y)
            if (dx == bs and dy == 0) or (dy == bs and dx == 0) or (dx == bs and dy == bs):
                adj[a_key].append((b.x, b.y))

    # ---------------------------------------------------
    # 3) Connected components
    # ---------------------------------------------------
    comps: List[List[Rect]] = []
    visited = set()
    for p in perims:
        k = (p.x, p.y)
        if k in visited:
            continue
        stack = [k]
        comp_keys = []
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp_keys.append(cur)
            stack.extend(adj[cur])
        comps.append([next(b for b in perims if (b.x, b.y)==key) for key in comp_keys])

    # ---------------------------------------------------
    # 4) Order blocks clockwise per component
    # ---------------------------------------------------
    def _clockwise_trace(blocks: List[Rect], bs: int) -> List[Rect]:
        """Return perimeter blocks in true clockwise walk order."""
        if not blocks:
            return []

        key_to_rect = { (b.x, b.y): b for b in blocks }
        # neighbour offsets (N,E,S,W) as x,y deltas
        neigh = [(0,-bs),(bs,0),(0,bs),(-bs,0)]

        # start at the upper-most, then left-most block so walk is deterministic
        start = min(blocks, key=lambda r: (r.y, r.x))
        ordered = [start]
        visited = { (start.x, start.y) }

        cur = start
        while True:
            # gather neighbours that are perimeter blocks (max 2 in most cases)
            cand = []
            for dx,dy in neigh:
                k = (cur.x+dx, cur.y+dy)
                if k in key_to_rect and k not in visited:
                    cand.append(key_to_rect[k])

            if not cand:
                break  # dead-end – concave pocket; stop the walk

            # choose neighbour that gives smallest positive clockwise angle step
            cx, cy = WIDTH//2, HEIGHT//2
            ang_cur = math.atan2(cur.centery - cy, cur.centerx - cx)
            best_blk = None
            best_delta = 10.0
            for nb in cand:
                ang_nb = math.atan2(nb.centery - cy, nb.centerx - cx)
                delta = (ang_nb - ang_cur) % (2*math.pi)
                if 0 < delta < best_delta:
                    best_delta = delta
                    best_blk = nb
            if best_blk is None:
                best_blk = cand[0]

            ordered.append(best_blk)
            visited.add((best_blk.x, best_blk.y))
            cur = best_blk
            if cur is start:
                break
            if len(visited) == len(blocks):
                break
        return ordered

    tracks: List[Track] = []
    block_index_map: Dict[Tuple[int,int], Tuple[int,int]] = {}

    for comp_id, comp_blocks in enumerate(comps):
        ordered = _clockwise_trace(comp_blocks, bs)
        tracks.append(ordered)
        for idx, blk in enumerate(ordered):
            block_index_map[(blk.x, blk.y)] = (comp_id, idx)

    # Keep only blocks that face outward from the castle centre ----------------
    center_x, center_y = WIDTH//2, HEIGHT//2

    return tracks, block_index_map 