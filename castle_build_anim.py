"""
castle_build_anim.py

Handles staged castle build animation for new waves.

Usage:
- Call staged_castle_build(castle, mask, size, level, build_callback) instead of instant build.
- Call update_castle_build_anim(castle, dt) each frame during build.
- Call draw_castle_build_anim(castle, screen) to draw the build animation.
- When build is complete, castle._build_anim_state['done'] becomes True.

The build_callback is called every second brick (for sound effects).
"""
import pygame
import random
from cg import BlockType
from cannon import Cannon
from config import WIDTH, HEIGHT, BLOCK_COLOR_L1, BLOCK_COLOR_L2, BLOCK_COLOR_L3, BLOCK_COLOR_DEFAULT
import math

# ----------------------------------------------------------
# Tunable timing constants (milliseconds)
# ----------------------------------------------------------
BUILD_BRICK_DELAY   = 60     # delay between *spawns* of bricks
TURRET_SPROUT_DELAY = 200    # delay between turret spawns after last brick
TURRET_SPROUT_TIME  = 200    # duration of turret pop-up animation

# Animation timing
BRICK_ANIM_TIME   = 220      # time for a single brick to scale-in
BRICK_RING_TIME   = 0      # lifetime of completion ring around brick
TURRET_RING_TIME  = 0      # lifetime of completion ring around turret

# Visual tuning
BRICK_POP_OVERSHOOT = 1.65   # overshoot factor for brick pop ease

# ----------------------------------------------------------
# Small easing helpers
# ----------------------------------------------------------

def _ease_out_cubic(t: float) -> float:
    """Fast, snappy ease-out cubic (t 0-1)."""
    return 1 - pow(1 - t, 3)


def _ease_out_back(t: float, s: float = 1.70158) -> float:
    """Back ease-out with overshoot *s* (defaults to ~10 %)."""
    t -= 1
    return 1 + (s + 1) * t * t * t + s * t * t

# ----------------------------------------------------------
#  Build-animation entry-point
# ----------------------------------------------------------

def staged_castle_build(castle, mask, size, level, build_callback=None):
    """Initialise staged build animation state on *castle*.

    Rather than building the entire keep instantaneously this sets up state so
    bricks and turrets appear progressively with eye-catching tweening.
    """
    height, width = mask.shape

    # Use per-wave cannon count
    max_cannons = castle._max_cannons_for_wave(level)

    # One-time debug print for build anim path
    print("[DEBUG] New wave mask (build anim):")
    for row in mask:
        print("[DEBUG]", ' '.join(str(int(v)) for v in row))
    print("[DEBUG] Block colors and healths (build anim):")
    for y in range(height):
        for x in range(width):
            if mask[y, x] >= BlockType.WALL.value:
                val = mask[y, x]
                extra = 0 if val == 2 else (1 if val == 3 else 2)
                health = 2 + extra if level > 1 else 2
                # Use the same color logic as set_block_color_by_strength
                if val == 2:
                    color = BLOCK_COLOR_L1
                elif val == 3:
                    color = BLOCK_COLOR_L2
                elif val == 4:
                    color = BLOCK_COLOR_L3
                else:
                    color = BLOCK_COLOR_DEFAULT
                print(f"[DEBUG]   ({x},{y}) tier={val} color={color} health={health}")

    # --------------------------------------------------
    # Enumerate all wall bricks from the mask
    # --------------------------------------------------
    bricks = []
    for y in range(height):
        for x in range(width):
            if mask[y, x] >= BlockType.WALL.value:
                px = WIDTH // 2 + (x - width // 2) * size
                py = HEIGHT // 2 + (y - height // 2) * size
                bricks.append((px, py))
    random.shuffle(bricks)  # more organic build order

    # Build-animation state machine
    castle._build_anim_state = {
        # --- brick phase ---
        'bricks': bricks,
        'brick_idx': 0,
        'brick_timer': 0,
        'anim_blocks': [],         # bricks currently scaling in
        'completed_bricks': 0,     # bricks fully placed (for SFX cadence)
        # --- turret phase ---
        'turrets': [],
        'turret_idx': 0,
        'turret_timer': 0,
        # --- misc ---
        'phase': 'bricks',
        'done': False,
        'build_callback': build_callback,
        'built_blocks': [],
        'built_cannons': [],
        'start_time': pygame.time.get_ticks(),
        'mask': mask,
        'max_cannons': max_cannons,
    }

    # Wipe any pre-existing castle blocks – we will add them gradually
    castle.blocks = []
    castle.block_colors = {}
    castle.block_shapes = {}
    castle.block_health = {}
    castle.cannon_blocks = {}
    castle.cannons = []

    # Pre-compute turret positions by picking the farthest bricks from centre
    cx, cy = WIDTH // 2, HEIGHT // 2
    sorted_blocks = sorted(bricks, key=lambda p: -(p[0] - cx) ** 2 - (p[1] - cy) ** 2)
    castle._build_anim_state['turrets'] = sorted_blocks[:max_cannons]

# ----------------------------------------------------------
#  Per-frame update
# ----------------------------------------------------------

def update_castle_build_anim(castle, dt):
    s = castle._build_anim_state
    if s['done']:
        return

    now = pygame.time.get_ticks()

    # Retrieve max_cannons for this build
    max_cannons = s.get('max_cannons', 4)

    # Always process anim_blocks, even during turret phase
    finished = []
    for ab in s['anim_blocks']:
        prog = min(1.0, (now - ab['start']) / BRICK_ANIM_TIME)
        if prog >= 1.0:
            finished.append(ab)
    for ab in finished:
        s['anim_blocks'].remove(ab)
        rect = ab['rect']
        key = (rect.x, rect.y)
        # Permanently add brick to castle data structures
        castle.blocks.append(rect)
        # Use mask to determine tier
        mask = s['mask']
        size = castle.block_size
        width = mask.shape[1]
        height = mask.shape[0]
        # Reverse the px, py calculation from staged_castle_build
        x = (rect.x - (WIDTH // 2)) // size + (width // 2)
        y = (rect.y - (HEIGHT // 2)) // size + (height // 2)
        tier = mask[y, x] if 0 <= y < height and 0 <= x < width else 2
        # Set both health and tier together
        if castle.level > 1:
            extra = 0 if tier == 2 else (1 if tier == 3 else 2)
            castle.block_health[key] = 1 + extra
        castle.block_tiers[key] = tier
        # Track the original tier for this block
        castle.original_block_tiers[key] = tier
        castle.set_block_color_by_strength(key, tier)
        castle.block_shapes[key] = 'wall'
        s['built_blocks'].append(rect)

    # BRICK BUILD PHASE: spawn new bricks
    if s['phase'] == 'bricks':
        s['brick_timer'] += dt
        while s['brick_idx'] < len(s['bricks']) and s['brick_timer'] >= BUILD_BRICK_DELAY:
            s['brick_timer'] -= BUILD_BRICK_DELAY
            px, py = s['bricks'][s['brick_idx']]
            rect = pygame.Rect(px, py, castle.block_size, castle.block_size)
            # Determine tier for this brick now so colour is correct from the very first frame
            mask = s['mask']
            size_px = castle.block_size
            width = mask.shape[1]
            height = mask.shape[0]
            mx = (rect.x - (WIDTH // 2)) // size_px + (width // 2)
            my = (rect.y - (HEIGHT // 2)) // size_px + (height // 2)
            tier = mask[my, mx] if 0 <= my < height and 0 <= mx < width else 2
            key = (rect.x, rect.y)
            castle.block_tiers[key] = tier
            # Track the original tier for this block
            castle.original_block_tiers[key] = tier
            castle.set_block_color_by_strength(key, tier)
            # Pre-populate block_shape so get_block_texture works during anim
            castle.block_shapes[key] = 'wall'
            # Pre-populate health so durability is correct once placed
            extra = 0 if tier == 2 else (1 if tier == 3 else 2)
            castle.block_health[key] = 1 + extra

            s['anim_blocks'].append({'rect': rect, 'start': now})
            # Play sound every two bricks, right as they spawn
            if (s['brick_idx'] + 1) % 2 == 0 and s['build_callback']:
                s['build_callback']('brick', s['brick_idx'] + 1)
            s['brick_idx'] += 1
        # Transition to turrets as soon as the last brick is spawned (not after anim)
        if s['brick_idx'] >= len(s['bricks']):
            s['phase'] = 'turrets'
            s['turret_timer'] = 0

    # TURRET POP PHASE: spawn turrets, but keep animating any remaining bricks
    if s['phase'] == 'turrets':
        s['turret_timer'] += dt
        # Spawn turrets one by one
        while s['turret_idx'] < max_cannons and s['turret_timer'] >= TURRET_SPROUT_DELAY:
            s['turret_timer'] -= TURRET_SPROUT_DELAY
            px, py = s['turrets'][s['turret_idx']]
            rect = pygame.Rect(px, py, castle.block_size, castle.block_size)
            side = _guess_side(rect, castle)
            pos = pygame.Vector2(rect.centerx, rect.centery)
            cannon = Cannon(
                block=rect,
                side=side,
                pos=pos,
                rail_info=None,  # set after build completes
                total_shots_ref=lambda: castle.total_shots,
                shooting_enabled_ref=lambda: castle.shooting_enabled,
                smoke_particles_ref=castle.smoke_particles,
                level=castle.level,
            )
            cannon.sprout_delay = 0
            cannon.sprout_scale = 0.0
            cannon._sprout_start = now
            s['built_cannons'].append(cannon)
            castle.cannons.append(cannon)
            cannon.born = now  # ensure pop animation age starts now
            s['turret_idx'] += 1

        # Animate turrets popping up with back overshoot
        for i, cannon in enumerate(s['built_cannons']):
            t = min(1.0, (now - getattr(cannon, '_sprout_start', now)) / TURRET_SPROUT_TIME)
            cannon.sprout_scale = _ease_out_back(t)

            # Trigger optional callback once at completion
            if t >= 1.0 and not getattr(cannon, '_sprout_done', False):
                setattr(cannon, '_sprout_done', True)
                if s['build_callback']:
                    s['build_callback']('turret', i)

        # Finished when last turret fully sprouted
        if s['turret_idx'] >= max_cannons and all(c.sprout_scale >= 1.0 for c in s['built_cannons']) and not s['anim_blocks']:
            s['done'] = True
            # Finalise castle – build rails etc.
            castle._build_perimeter_track()
            for c in castle.cannons:
                if castle.rail_info:
                    c.rail_id, c.rail_idx = castle.rail_info.nearest_node((c.block.x, c.block.y))
            # Prevent duplicate spawning if this function is mistakenly re-entered
            s['phase'] = 'complete'
            # Disable shooting for a short grace period after build
            castle.shooting_enabled = False
            castle._shoot_enable_at = pygame.time.get_ticks() + 2000  # 2-second delay

# ----------------------------------------------------------
#  Drawing helper
# ----------------------------------------------------------

def draw_castle_build_anim(castle, screen):
    s = castle._build_anim_state
    now = pygame.time.get_ticks()

    # --- In-progress bricks scaling in ---
    for ab in s['anim_blocks']:
        prog = min(1.0, (now - ab['start']) / BRICK_ANIM_TIME)
        scale = _ease_out_back(prog, BRICK_POP_OVERSHOOT)
        rect = ab['rect']
        key = (rect.x, rect.y)
        # Determine tier for this block
        mask = s['mask']
        size_px = castle.block_size
        width = mask.shape[1]
        height = mask.shape[0]
        x = (rect.x - (WIDTH // 2)) // size_px + (width // 2)
        y = (rect.y - (HEIGHT // 2)) // size_px + (height // 2)
        tier = mask[y, x] if 0 <= y < height and 0 <= x < width else 2
        # Temporarily set color for this block
        old_color = castle.block_colors.get(key)
        castle.set_block_color_by_strength(key, tier)
        tex = castle.get_block_texture(rect)
        # Restore old color if it existed (so we don't pollute block_colors)
        if old_color is not None:
            castle.block_colors[key] = old_color
        else:
            del castle.block_colors[key]
        # (No need to clear cache – colour already correct)
        size = int(castle.block_size * scale)
        if size <= 0:
            continue
        surf = pygame.transform.scale(tex, (size, size))
        draw_rect = surf.get_rect(center=rect.center)
        screen.blit(surf, draw_rect)

    # --- Completed bricks ---
    for rect in s['built_blocks']:
        tex = castle.get_block_texture(rect)
        screen.blit(tex, rect.topleft)

    # --- Draw growing black outline around built/animating bricks ---
    # Use tuples for set elements to avoid unhashable Rect error
    visible_blocks = {(r.x, r.y, r.width, r.height) for r in s['built_blocks']}
    for ab in s['anim_blocks']:
        r = ab['rect']
        visible_blocks.add((r.x, r.y, r.width, r.height))
    bs = castle.block_size
    border_col = (0, 0, 0)
    thick = 2
    occupied = {(x, y) for (x, y, w, h) in visible_blocks}
    for x, y, w, h in visible_blocks:
        b = pygame.Rect(x, y, w, h)
        # Top
        if (x, y - bs) not in occupied:
            pygame.draw.line(screen, border_col, (b.left, b.top), (b.right - 1, b.top), thick)
        # Bottom
        if (x, y + bs) not in occupied:
            pygame.draw.line(screen, border_col, (b.left, b.bottom - 1), (b.right - 1, b.bottom - 1), thick)
        # Left
        if (x - bs, y) not in occupied:
            pygame.draw.line(screen, border_col, (b.left, b.top), (b.left, b.bottom - 1), thick)
        # Right
        if (x + bs, y) not in occupied:
            pygame.draw.line(screen, border_col, (b.right - 1, b.top), (b.right - 1, b.bottom - 1), thick)

    # --- Turrets sprouting ---
    for cannon in s['built_cannons']:
        preview_types = getattr(castle, '_preview_types', ['white','red','power'])
        preview_col_map = {'white': (220, 220, 220), 'red': (255, 60, 60), 'power': (255, 255, 80)}
        cannon.draw(screen, now, preview_types, preview_col_map)

    # (No completion rings for build anim)

# ----------------------------------------------------------
#  Helpers
# ----------------------------------------------------------

def _guess_side(rect, castle):
    """Heuristic to determine which wall side *rect* belongs to."""
    cx, cy = rect.centerx, rect.centery
    if abs(cy - HEIGHT // 2) > abs(cx - WIDTH // 2):
        return 'top' if cy < HEIGHT // 2 else 'bottom'
    else:
        return 'left' if cx < WIDTH // 2 else 'right'