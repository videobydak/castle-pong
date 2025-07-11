import pygame, random, math
import numpy as np  # for simple pitch-shift resampling
from config import *
from utils import make_checker, make_bricks, make_round_bricks, make_garden
from ball import Ball
from perimeter import build_tracks  # new helper
from perimeter import is_enclosed_tile
from rail import build_rails
from cg import BlockType  # Add this import
from castle_update import update_castle
from cannon import Cannon
# Add import for staged build animation
from castle_build_anim import staged_castle_build
from config import WIDTH, HEIGHT, BLOCK_SIZE, SCALE
from crack_demo import create_crack_animator

REPAIR_DELAY = 3000   # wait before repair starts (ms)
REPAIR_TIME  = 15000  # duration of rebuild animation (ms)
DAMAGE_ATTRACT_TIME = 4000  # ms – cannons flock toward recent breaches
CANNON_RESPAWN_DELAY = 3000  # wait before cannon can respawn (ms)

# Maximum number of persistent debris pieces allowed before oldest ones begin fading out
MAX_DEBRIS_COUNT = 1000  # tuned to keep performance reasonable

MAX_CANNONS = 8  # updated overall upper-limit of simultaneously active cannons
# Reduce slide speed so cannons don't race around the perimeter. Roughly 50 % of the previous value.
CANNON_SLIDE_SPEED = 0.18  # px / ms – tuned for readable but still threatening movement

# small easing factor for position interpolation when close to target (for smoother stop)
CANNON_EASE_DISTANCE = 4.0  # pixels – begin ease-in when within this many pixels of waypoint

# Minimum fraction of slide speed so easing never fully stops mid-segment
_EASE_MIN = 0.25

# Chance that a cannon deliberately targets the player wall even when a paddle is available
# WALL_SHOT_PROB now handled dynamically in castle_update.py

# --------------------------------------------------
# Audio – cannon shot SFX with subtle pitch variants
# --------------------------------------------------
# The mixer may not be initialised yet when this module is imported
# (main.py imports Castle *before* it runs pygame.mixer.init()).  We
# therefore defer loading until the first time a cannon actually fires.

_SHOT_SOUNDS = None  # will be populated lazily


def _prepare_shot_sounds():
    """Initialise _SHOT_SOUNDS dict the first time it is required."""
    global _SHOT_SOUNDS
    if _SHOT_SOUNDS is not None:  # already attempted
        return

    if not pygame.mixer.get_init():
        # Mixer still not ready – skip for now; we'll try again later.
        return

    try:
        base = pygame.mixer.Sound("Artlist Original - 8 Bits and Pieces - Noise Fire Shot.wav")
        # Volume will be set by options menu

        def _pitch_shift(sound: pygame.mixer.Sound, factor: float) -> pygame.mixer.Sound:
            arr = pygame.sndarray.array(sound)
            orig_len = arr.shape[0]
            idx = np.linspace(0, orig_len - 1, int(orig_len / factor)).astype(np.int32)
            shifted = arr[idx]
            snd = pygame.sndarray.make_sound(shifted.copy())
            # Volume will be set by options menu
            return snd

        _SHOT_SOUNDS = {
            'normal': base,
            '0.1': _pitch_shift(base, 0.1),   # extremely low pitch
            '0.5': _pitch_shift(base, 0.5),   # low pitch
            '0.85': _pitch_shift(base, 0.85),   # high pitch (now 0.85)
            '1.9': _pitch_shift(base, 1.9),   # very high pitch
        }
        print('[Audio] Cannon shot sounds loaded')
        
        # Update volumes based on current settings
        _update_cannon_sound_volumes()
    except pygame.error as e:
        print('[Audio] Failed to load cannon shot sound:', e)
        _SHOT_SOUNDS = {}
    except Exception as e:
        # Handle numpy or resampling errors gracefully
        print('[Audio] Pitch-shift preparation failed:', e)
        _SHOT_SOUNDS = {'normal': None}


def _update_cannon_sound_volumes():
    """Update cannon sound volumes based on current settings."""
    global _SHOT_SOUNDS
    if not _SHOT_SOUNDS:
        return
    
    try:
        import sys
        if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'options_menu'):
            options_menu = sys.modules['__main__'].options_menu
            if hasattr(options_menu, 'settings'):
                if options_menu.settings.get('sfx_muted', False):
                    for sound in _SHOT_SOUNDS.values():
                        if sound:
                            sound.set_volume(0)
                else:
                    sfx_vol = options_menu.settings.get('sfx_volume', 0.75)
                    for sound in _SHOT_SOUNDS.values():
                        if sound:
                            sound.set_volume(sfx_vol)
    except Exception as e:
        print(f"[Castle] Failed to update cannon sound volumes: {e}")

class Castle:
    TILE_SUBDIVS = (4,5)  # columns, rows -> 20 tiles
    POP_DURATION = 400     # ms

    # How many cannonballs have been fired so far (across all cannons).  Used
    # to gradually ramp up the aggressiveness of the AI regardless of player
    # score.
    total_shots: int = 0

    # --------------------------------------------------
    # Helper – return max simultaneous cannons for a wave
    # --------------------------------------------------
    @staticmethod
    def _max_cannons_for_wave(level: int) -> int:
        """Return the allowed cannon count for the given *level* / wave."""
        if level <= 2:
            return 3  # Waves 1-2
        elif level <= 4:
            return 4  # Waves 3-4
        elif level <= 6:
            return 5  # Waves 5-6
        elif level <= 8:
            return 6  # Waves 7-8
        elif level == 9:
            return 7  # Wave 9
        else:
            return 8  # Wave 10 and beyond

    def __init__(self, level=1, max_dim=None):
        self.level = level
        self.blocks = []
        self.cannon_blocks = {}
        self.block_health = {}
        self.block_colors = {}
        self.block_shapes = {}  # key -> shape string
        self.destroyed_blocks = {} # rect_tuple -> destroy_time
        self.pop_anims = []  # list of (rect, start_time)
        
        # Buffers and state flags that need to exist before cannons are created
        self.smoke_particles = []
        self._new_balls = []
        self.shooting_enabled = True
        # Flags to coordinate ammo availability across cannons
        self.fireball_reserved = False  # Only one active (waves <10)
        self.potion_reserved   = False  # Only one potion charging at a time

        size = BLOCK_SIZE  # Use global block size
        self.block_size = size

        # ----------------- overall footprint size -----------------
        # The castle generator uses a square grid that extends from
        # -density .. +density ( inclusive ) which yields a footprint of
        # (2*density + 1) blocks in width/height.  For example, density=2
        # -> 5×5, density=3 -> 7×7, etc.

        # Original behaviour: pick a base density of 3-5 at random.  We now
        # want external callers (main game loop) to be able to clamp the
        # maximum size so early waves can start small (e.g. 5×5) and then
        # grow each wave.  We therefore honour an optional *max_dim*
        # argument which, if supplied, caps the final footprint so the
        # width / height never exceed that dimension.

        base_density       = 3  # minimum half-width of the keep in blocks
        density_variation  = random.randint(0, 2)
        density            = base_density + density_variation  # default choice

        if max_dim is not None:
            # (max_dim-1)//2 gives the maximum allowed density so that the
            # resulting footprint is ≤ max_dim.
            density_limit = max(1, (max_dim - 1) // 2)
            density       = min(density, density_limit)

        self.block_textures = {}  # color_tuple -> texture
        self.block_tiers = {}
        self.original_block_tiers = {}  # Track the original tier of each block
        self.block_rebuild_count = {}  # Track how many times each block has been rebuilt

        # Candidate edge blocks for random cannon placement (populated below)
        top_candidates = []
        bottom_candidates = []
        left_candidates = []
        right_candidates = []

        # Select an overall outline shape for the castle: square, diamond or circle
        outline_type = random.choice(['square', 'diamond', 'circle'])

        # Pre-compute required positions that must exist so cannons have a home.
        required_coords = {(0, -density), (0, density), (-density, 0), (density, 0)}

        # ----------------- PATH & COURTYARD DESIGN -----------------
        walkway_coords = set()
        # Primary cross-shaped corridor from each wall toward the centre
        for dstep in range(1, density):
            walkway_coords.update({(0, -dstep), (0, dstep), (-dstep, 0), (dstep, 0)})

        # Random secondary corridor perpendicular to main one (adds variety)
        if random.random() < 0.6:
            axis = random.choice(['h', 'v'])
            if axis == 'h':
                sel_row = random.randint(-density + 1, density - 1)
                for dx in range(-density + 1, density):
                    walkway_coords.add((dx, sel_row))
            else:
                sel_col = random.randint(-density + 1, density - 1)
                for dy in range(-density + 1, density):
                    walkway_coords.add((sel_col, dy))

        # Generate clustered garden courtyards (2x2) – 1-3 of them
        garden_coords = set()
        num_gardens = random.randint(1, 3)
        attempts = 0
        while len(garden_coords) < num_gardens * 4 and attempts < 50:
            attempts += 1
            gx = random.randint(-density + 1, density - 2)
            gy = random.randint(-density + 1, density - 2)
            cluster = {(gx, gy), (gx + 1, gy), (gx, gy + 1), (gx + 1, gy + 1)}
            if cluster & walkway_coords:
                continue  # don't overlap walkways
            garden_coords.update(cluster)

        # ------------------------------------------------------------------

        for i in range(-density, density + 1):
            for j in range(-density, density + 1):
                # Skip far corners so the outline feels less boxy – we will build
                # rounded-ish towers later instead of hard square points.
                if abs(i) == density and abs(j) == density:
                    continue

                # Determine whether the current coordinate sits on the chosen
                # outer wall.
                if outline_type == 'square':
                    outer = max(abs(i), abs(j)) == density
                elif outline_type == 'diamond':
                    outer = (abs(i) + abs(j)) == density
                else:  # circle (approximated)
                    dist = math.hypot(i, j)
                    outer = density - 0.5 <= dist < density + 0.5

                # Outer ring is always present; interior blocks are random to
                # create halls and chambers.
                if outer:
                    place = True
                else:
                    place = random.random() < 0.6  # 60 % chance for inner blocks

                # Ensure important coordinates always filled
                if (i, j) in required_coords or (i, j) in walkway_coords or (i, j) in garden_coords:
                    place = True

                if not place:
                    continue

                r = pygame.Rect(
                    WIDTH // 2 + i * size - size // 2,
                    HEIGHT // 2 + j * size - size // 2,
                    size,
                    size,
                )

                key = (r.x, r.y)

                # Decide shape / type based on design sets first
                if (i, j) in garden_coords:
                    self.block_colors[key] = BLOCK_COLOR_GARDEN
                    self.block_shapes[key] = 'garden'
                elif (i, j) in walkway_coords:
                    self.block_colors[key] = BLOCK_COLOR_WALKWAY
                    self.block_shapes[key] = 'walkway'
                elif not outer:
                    # interior walls/floors – occasionally leave empty space to form rooms
                    if random.random() < 0.25:
                        continue  # skip – creates hollow chamber
                    self.block_colors[key] = BLOCK_COLOR_DEFAULT
                    self.block_shapes[key] = 'wall'
                else:
                    self.block_colors[key] = BLOCK_COLOR_DEFAULT
                    self.block_shapes[key] = 'wall'

                print(f"[DEBUG] Adding block to castle.blocks (init): key={key}")
                self.blocks.append(r)

                # Set default tier for blocks created in constructor (tier 1 = value 2)
                self.block_tiers[key] = 2
                self.original_block_tiers[key] = 2

                if self.level > 1:
                    self.block_health[key] = 2

                # collect outer-edge blocks for potential cannon spots
                if outer:
                    if j == -density:
                        top_candidates.append((r, 'top'))
                    if j == density:
                        bottom_candidates.append((r, 'bottom'))
                    if i == -density:
                        left_candidates.append((r, 'left'))
                    if i == density:
                        right_candidates.append((r, 'right'))

        # --------------------------------------------------------------
        #  Cannon spawn selection – obey per-wave limit
        # --------------------------------------------------------------
        max_cannons_wave = Castle._max_cannons_for_wave(self.level)

        all_blocks = self.blocks[:]
        random.shuffle(all_blocks)
        selected_blocks = all_blocks[:max_cannons_wave]

        selected = []  # list of (rect, side)
        for rect in selected_blocks:
            side = self._get_block_side(rect)
            selected.append((rect, side))
            # store representative block per side (for potential rebuilds)
            if side not in self.cannon_blocks:
                self.cannon_blocks[side] = rect

        # --- Build cannon objects ---
        # Hard-cap the selection to the global MAX_CANNONS constant
        if len(selected) > max_cannons_wave:
            # Keep first entries – they are already reasonably shuffled
            selected = selected[:max_cannons_wave]

        # Build the perimeter track first
        self._build_perimeter_track()

        self.cannons = []
        for rect, side in selected:
            if len(self.cannons) >= max_cannons_wave:
                break

            pos = pygame.Vector2(rect.centerx, rect.centery)
            # Pass castle-bound references to the cannon
            new_cannon = Cannon(
                block=rect,
                side=side,
                pos=pos,
                rail_info=self.rail_info,
                total_shots_ref=lambda: Castle.total_shots,
                shooting_enabled_ref=lambda: self.shooting_enabled,
                smoke_particles_ref=self.smoke_particles,
                level=self.level
            )
            # Stagger sprout delays
            delay_ms = 200 + len(self.cannons) * 300 + random.randint(0, 300)
            new_cannon.sprout_delay = delay_ms
            # The cannon now handles its own idle timer setup based on its delay.
            # new_cannon.idle_timer = delay_ms + random.randint(300, 600)
            self.cannons.append(new_cannon)

        # The large block that configured cannon dictionaries is now removed,
        # as this logic is handled within the Cannon class constructor.
        # We just need to override specific initial states if necessary.
        for c in self.cannons:
            # We want cannons to start in a random state, not always 'idle'.
            # The Cannon class now handles this randomization internally.
            # We can remove the state override loop.
            # Let's ensure the initial decision logic is consistent.
            c.initial_decision_pending = False

        # keep the attribute so external code doesn't break but disable timer –
        # cannons now drive their own decisions.
        self.shoot_event = pygame.USEREVENT+1
        pygame.time.set_timer(self.shoot_event, 0)
        
        # Initialize destroyed cannons tracking system
        self.destroyed_cannons = []  # List of destroyed cannon info with respawn timing

        # ball preview cycling order
        # Make power-ups spawn far less frequently by weighting the
        # preview sequence heavily toward standard shots.
        # Approx. 10 % of cannon volleys will now be power-ups instead of 33 %.
        self._preview_types = [
            'white', 'red',
            'white', 'white', 'red',
            'white', 'white', 'red', 'white',  # 9 normal shots
            'power'                            # 1 power-up
        ]

        # persistent debris pieces from shattered blocks
        self.debris = []  # list of {pos:Vector2, vel:Vector2, color:(r,g,b), size:int}

        # --- score-based difficulty ramp ---
        self._score_offsets = {
            'think': 100,     # don't start speeding up until 100 pts
            'preview': 200,   # after 200 pts
            'charge': 300,    # after 300 pts
            'prob': 400       # after 400 pts
        }

        # Add rounded corners for square outer wall, if selected and space permits
        if outline_type == 'square' and random.random() < 0.7:
            corners = [(-density, -density, 'tl'), (density, -density, 'tr'),
                       (-density, density, 'bl'), (density, density, 'br')]
            for cx, cy, corner_tag in corners:
                # ensure both adjacent neighbours inside grid are empty so curved sides face out
                nx1, ny1 = (cx + (1 if cx < 0 else -1), cy)
                nx2, ny2 = (cx, cy + (1 if cy < 0 else -1))
                if (nx1, ny1) in self.block_shapes or (nx2, ny2) in self.block_shapes:
                    continue  # neighbour occupied – skip rounded corner here

                # Create rounded corner tile
                r = pygame.Rect(
                    WIDTH // 2 + cx * size - size // 2,
                    HEIGHT // 2 + cy * size - size // 2,
                    size,
                    size,
                )
                key = (r.x, r.y)
                print(f"[DEBUG] Adding rounded corner block to castle.blocks: key={key}")
                self.blocks.append(r)
                self.block_shapes[key] = f'round_{corner_tag}'
                self.block_colors[key] = BLOCK_COLOR_DEFAULT
                # Set default tier for rounded corner blocks (tier 1 = value 2)
                self.block_tiers[key] = 2
                self.original_block_tiers[key] = 2
                if self.level > 1:
                    self.block_health[key] = 2

        # Initialize perimeter track system
        self.perimeter_track = []
        self.block_to_track_index = {}

        # recent block damage events (timestamped)
        self.damage_events = []  # list of {'rail_id':int,'idx':int,'time':int}

        # Initialise cannon's first aim toward a random scan angle
        base = random.uniform(-90,90)
        if self.cannons:
            self.cannons[-1].pending_target_angle = base
            self.cannons[-1].aim_transition = True
            self.cannons[-1].scan_target_angle = base

        self.block_cracks = {}  # key -> CrackAnimator

    def get_block_texture(self, block):
        key = (block.x, block.y)
        
        # Safeguard: warn if this block is not in our blocks list (indicates stale reference)
        if block not in self.blocks:
            print(f"[DEBUG] WARNING: Getting texture for block not in castle.blocks at {key} - possible stale reference")
        
        # Ensure key exists to avoid runtime errors on stale rects
        if key not in self.block_shapes:
            self.block_shapes[key] = 'wall'

        # Safeguard: ensure a colour entry exists for this block.
        # This prevents occasional KeyError crashes if a rect gets
        # added to self.blocks without an accompanying colour –
        # for instance, during the very last frame of a rebuild when a
        # ball is overlapping the tile.  We fall back to the default
        # tier-1 colour so the game can continue uninterrupted.
        if key not in self.block_colors:
            print(f"[DEBUG] WARNING: Block {key} has no color, using default: {BLOCK_COLOR_DEFAULT}")
            self.block_colors[key] = BLOCK_COLOR_DEFAULT

        color = self.block_colors[key]
        shape = self.block_shapes.get(key, 'wall')

        tex_key = (color, shape)
        if tex_key not in self.block_textures:
            print(f"[DEBUG]   Generating new texture for key={key} color={color} shape={shape}")
            if shape.startswith('round_'):
                corner = shape.split('_')[1]  # extract tl/tr/bl/br
                self.block_textures[tex_key] = make_round_bricks(self.block_size, *color, corner=corner)
            elif shape == 'garden':
                # garden tiles ignore color tuple
                self.block_textures[tex_key] = make_garden(self.block_size)
            else:  # default wall / walkway bricks
                # walkway bricks use lighter colour already passed in color tuple
                self.block_textures[tex_key] = make_bricks(self.block_size, *color)
        return self.block_textures[tex_key]

    def _apply_rebuild_setback(self):
        """Shared helper – setback all in-progress rebuilds and spawn debris bursts."""
        now = pygame.time.get_ticks()
        stagger = 0
        for pos, rec in self.destroyed_blocks.items():
            elapsed = now - rec['time']

            if elapsed < REPAIR_DELAY:
                # Still waiting to start rebuild – push start further to keep staggering effect
                rec['time'] = now + stagger
                stagger += 250
                rec['shake'] = rec.get('shake', 0) + random.randint(4, 8)
                continue

            # Setback blocks already rebuilding
            repair_speed_mult = getattr(self, '_repair_speed_mult', 1.0)
            repair_time = REPAIR_TIME / repair_speed_mult
            progress = (elapsed - REPAIR_DELAY) / repair_time
            if progress <= 0 or progress >= 1.0:
                continue

            reduction_factor = random.uniform(0.5, 0.8)
            lost_progress = progress * reduction_factor
            new_progress = progress - lost_progress

            # Rewind timer
            new_elapsed = REPAIR_DELAY + new_progress * repair_time
            rec['time'] = now - new_elapsed
            rec['shake'] = rec.get('shake', 0) + random.randint(4, 8)

            # Debris burst scaled to lost progress
            # DEBRIS FIX: Don't create debris during paddle intro animations
            if not getattr(self, '_pause_rebuild', False):
                block_rect = pygame.Rect(pos[0], pos[1], self.block_size, self.block_size)
                origin = pygame.Vector2(block_rect.centerx, block_rect.centery)
                debris_count = max(2, int(30 * lost_progress))
                col_pair = self.block_colors.get(pos, ((110, 110, 110), (90, 90, 90)))
                for _ in range(debris_count):
                    ang = random.uniform(0, 360)
                    speed = random.uniform(2, 6) * (0.5 + lost_progress)
                    vel = pygame.Vector2(speed, 0).rotate(ang)
                    deb = {'pos': origin.copy(), 'vel': vel, 'color': random.choice(col_pair),
                           'size': random.randint(2, 4), 'friction': random.uniform(0.94, 0.985)}
                    if random.random() < 0.3:
                        deb['dig_delay'] = random.randint(0, int(15 * SCALE))
                        deb['dig_frames'] = random.randint(int(15 * SCALE), int(90 * SCALE))
                    self.debris.append(deb)

    def hit_block(self, block, impact_point=None, impact_angle=None):
        key = (block.x, block.y)
        
        # Check if this block is currently being rebuilt
        if key in self.destroyed_blocks:
            # Block is being rebuilt - reset to tier 1 and restart rebuild
            destroyed_info = self.destroyed_blocks[key]
            original_tier = destroyed_info.get('original_tier', 2)
            
            # Remove the block from the blocks list (it's being rebuilt)
            if block in self.blocks:
                print(f"[DEBUG] Removing block from castle.blocks (rebuild hit): key={key}")
                self.blocks.remove(block)
            
            # Clean up any existing data for this block
            if key in self.block_health:
                del self.block_health[key]
            if key in self.block_colors:
                del self.block_colors[key]
            if key in self.block_shapes:
                del self.block_shapes[key]
            if key in self.block_cracks:
                del self.block_cracks[key]
            if key in self.block_tiers:
                del self.block_tiers[key]
            if key in self.original_block_tiers:
                del self.original_block_tiers[key]
            if key in getattr(self, 'block_rebuild_count', {}):
                del self.block_rebuild_count[key]
            
            # Reset rebuild state to tier 1
            order = list(range(Castle.TILE_SUBDIVS[0]*Castle.TILE_SUBDIVS[1]))
            random.shuffle(order)
            
            # Check if any cannon was mounted on this block so we can rebuild it later
            attached_cannons = [c for c in self.cannons if c.block == block]
            for c in attached_cannons:
                self.cannons.remove(c)
                # Add cannon to destroyed cannons pool with respawn timing
                self.destroyed_cannons.append({
                    'side': c.side,
                    'preview_idx': c.preview_idx,
                    'destroyed_time': pygame.time.get_ticks(),
                    'level': self.level
                })
            
            # For tier 3+ blocks (value 3+), implement tiered rebuilding
            # Tier 1 blocks (value 2) rebuild normally as tier 1
            if original_tier >= 3:
                # Start rebuilding at tier 1 (lowest tier)
                rebuild_tier = 1
                self.destroyed_blocks[key] = {
                    'time': pygame.time.get_ticks(),
                    'order': order,
                    'original_tier': original_tier,
                    'current_rebuild_tier': rebuild_tier,
                    'tiered_rebuild': True
                }
            else:
                # Tier 1 blocks (value 2) rebuild normally as tier 1
                self.destroyed_blocks[key] = {
                    'time': pygame.time.get_ticks(),
                    'order': order
                }
            
            # Recompute perimeter tracks as the layout changed
            self._build_perimeter_track()
            
            # Apply rebuild setbacks & debris for in-progress blocks
            self._apply_rebuild_setback()
            
            return  # Block reset and rebuild restarted
        
        # Normal block hit logic (block is not being rebuilt)
        if key in self.block_health:
            prev_health = self.block_health[key]
            # Reduce health first
            self.block_health[key] -= 1

            # Update color to match new health
            tier = getattr(self, 'block_tiers', {}).get(key, 2)
            h = self.block_health[key]
            if tier == 4:  # Layer-3: 3→2→1→destroy
                if h == 3:
                    self.set_block_color_by_strength(key, 4)
                elif h == 2:
                    self.set_block_color_by_strength(key, 3)
                elif h == 1:
                    self.set_block_color_by_strength(key, 2)
            elif tier == 3:  # Layer-2: 2→1→destroy
                if h == 2:
                    self.set_block_color_by_strength(key, 3)
                elif h == 1:
                    self.set_block_color_by_strength(key, 2)
            # Layer-1 stays dark

            # --- Crack logic ---
            if impact_point is not None and impact_angle is not None:
                if prev_health == 3 and self.block_health[key] == 2:
                    # Layer 3 -> 2: create animator and add first crack
                    if key not in self.block_cracks:
                        self.block_cracks[key] = create_crack_animator(block)
                    self.block_cracks[key].add_crack(impact_point, impact_angle, debug=False)
                elif prev_health == 2 and self.block_health[key] == 1:
                    # Layer 2 -> 1: add second crack, keep previous
                    if key not in self.block_cracks:
                        self.block_cracks[key] = create_crack_animator(block)
                    self.block_cracks[key].add_crack(impact_point, impact_angle, debug=False)

            if self.block_health[key] > 0:
                return  # Not destroyed yet

            # ----------------------------------------------
            #  Heart drop on final destruction (hit_block)
            # ----------------------------------------------
            try:
                from heart import maybe_spawn_hearts
                # print("[HEART] Attempting spawn on block destroy (hit_block)")
                maybe_spawn_hearts(block)
                # print("[HEART] Spawn call completed (hit_block)")
            except Exception as e:
                # print("[HEART] Spawn error:", e)
                pass

            # ----------------------------------------------
            #  Coin drop on final destruction (hit_block)
            # ----------------------------------------------
            try:
                from coin import maybe_spawn_coins
                maybe_spawn_coins(block)
            except Exception as e:
                print("[COIN] Spawn error:", e)

        # Remove cracks if block is destroyed
        if key in self.block_cracks:
            del self.block_cracks[key]

        print(f"[DEBUG] Removing block from castle.blocks: key={key}")
        self.blocks.remove(block)
        if key in self.block_health:
            del self.block_health[key]
        if key in self.block_colors:
            del self.block_colors[key]
        if key in self.block_shapes:
            del self.block_shapes[key]
        # Clean up rebuild count and original tier tracking when block is permanently destroyed
        if key in getattr(self, 'block_rebuild_count', {}):
            del self.block_rebuild_count[key]
        if key in getattr(self, 'original_block_tiers', {}):
            del self.original_block_tiers[key]

        order = list(range(Castle.TILE_SUBDIVS[0]*Castle.TILE_SUBDIVS[1]))
        random.shuffle(order)

        # Check if any cannon was mounted on this block so we can rebuild it later
        attached_cannons = [c for c in self.cannons if c.block == block]
        for c in attached_cannons:
            self.cannons.remove(c)
            # Add cannon to destroyed cannons pool with respawn timing
            self.destroyed_cannons.append({
                'side': c.side,
                'preview_idx': c.preview_idx,
                'destroyed_time': pygame.time.get_ticks(),
                'level': self.level
            })

        # Get the original tier of this block
        # Use original_block_tiers if available, otherwise fall back to current tier
        original_tier = getattr(self, 'original_block_tiers', {}).get(key, 
                    getattr(self, 'block_tiers', {}).get(key, 2))
        
        # Check if this block has already been rebuilt once
        rebuild_count = getattr(self, 'block_rebuild_count', {}).get(key, 0)
        
        # Only allow rebuilding if this is the first time being destroyed
        if rebuild_count == 0:
            # For tier 3+ blocks (value 3+), implement tiered rebuilding
            # Tier 1 blocks (value 2) rebuild normally as tier 1
            if original_tier >= 3:
                # Start rebuilding at tier 1 (lowest tier)
                rebuild_tier = 1
                self.destroyed_blocks[key] = {
                    'time': pygame.time.get_ticks(),
                    'order': order,
                    'original_tier': original_tier,
                    'current_rebuild_tier': rebuild_tier,
                    'tiered_rebuild': True
                }
            else:
                # Tier 1 blocks (value 2) rebuild normally as tier 1
                self.destroyed_blocks[key] = {
                    'time': pygame.time.get_ticks(),
                    'order': order
                }
        else:
            # Block has already been rebuilt once, don't rebuild again
            print(f"Block at {key} has already been rebuilt {rebuild_count} times - not rebuilding again")

        # Recompute perimeter tracks as the layout changed
        self._build_perimeter_track()
    
        # record damage event for AI to react
        if hasattr(self, 'rail_info') and self.rail_info.rail_points:
            ridx = self.rail_info.block_to_rail.get(key)
            if ridx:
                r_id, r_idx = ridx
                self._record_damage_event(r_id, r_idx)

        # -------------------------------------------------------
        #  Spawn debris on final destruction (unless skipped)
        # -------------------------------------------------------
        if not getattr(self, '_skip_debris', False):
            # DEBRIS FIX: Don't create debris during paddle intro animations
            if not getattr(self, '_pause_rebuild', False):
                # Approximate incoming direction from impact_angle if provided; else upward
                if impact_angle is not None:
                    incoming_dir = pygame.Vector2(math.cos(impact_angle), math.sin(impact_angle))
                else:
                    incoming_dir = pygame.Vector2(0, -1)

                color_pair = self.block_colors.get(key, ((110, 110, 110), (90, 90, 90)))
                debris_count = 30
                base_dir = (-incoming_dir.normalize()) if incoming_dir.length_squared() != 0 else pygame.Vector2(0, -1)
                for _ in range(debris_count):
                    angle_variation = random.uniform(-40, 40)
                    speed = random.uniform(2, 6) * SCALE
                    vel = base_dir.rotate(angle_variation) * speed
                    size = int(random.randint(2, 4) * SCALE)
                    deb = {'pos': pygame.Vector2(block.centerx, block.centery), 'vel': vel,
                           'color': random.choice(color_pair), 'size': size,
                           'friction': random.uniform(0.94, 0.985)}
                    if random.random() < 0.3:
                        deb['dig_delay'] = random.randint(0, int(15 * SCALE))
                        deb['dig_frames'] = random.randint(int(15 * SCALE), int(90 * SCALE))
                    self.debris.append(deb)

                # Apply rebuild setbacks & debris for in-progress blocks
                self._apply_rebuild_setback()

        # Clear the temporary skip flag if it was set by shatter_block
        if hasattr(self, '_skip_debris'):
            delattr(self, '_skip_debris')

    def update(self, dt_ms, player_score=0, paddles=None, player_wall=None, balls=None):
        # Update cracks
        for crack in self.block_cracks.values():
            crack.update()
        return update_castle(self, dt_ms, player_score, paddles, player_wall, balls)

    def draw(self, screen):
        # Draw each block's brick texture first (no thick outline)
        for b in self.blocks:
            tex = self.get_block_texture(b)
            screen.blit(tex, b.topleft)
            # Draw cracks if present
            key = (b.x, b.y)
            if key in self.block_cracks:
                self.block_cracks[key].draw(screen, show_debug=False)

        # After all tiles are blitted, draw a thicker outline only on sides
        # that are exposed (i.e. do not have a neighbouring castle tile).
        occupied = {(blk.x, blk.y) for blk in self.blocks}
        bs = self.block_size
        border_col = (0, 0, 0)
        thick = 2
        for b in self.blocks:
            x, y = b.x, b.y
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

        # current time for animations
        now = pygame.time.get_ticks()
        
        # --- rebuilding animation ---
        for pos, destroyed_at in self.destroyed_blocks.items():
            elapsed = now - destroyed_at['time']
            if elapsed < REPAIR_DELAY:
                continue  # delay: nothing drawn yet
            progress = (elapsed - REPAIR_DELAY) / REPAIR_TIME
            if progress >= 1.0:
                continue  # will be handled in update soon

            block_rect = pygame.Rect(pos[0], pos[1], self.block_size, self.block_size)
            # apply shake offset if flag present
            shake = destroyed_at.get('shake',0)
            if shake>0:
                offset = pygame.Vector2(random.randint(-shake, shake), random.randint(-shake, shake))
                block_rect = block_rect.move(offset)

            cols, rows = Castle.TILE_SUBDIVS
            tile_w = self.block_size // cols
            tile_h = self.block_size // rows
            total_tiles = cols * rows
            tiles_completed = int(progress * total_tiles)
            fractional = (progress * total_tiles) - tiles_completed

            order = destroyed_at['order']
            # draw completed tiles according to random order
            for idx in order[:tiles_completed]:
                cx = idx % cols
                cy = idx // cols
                sub_rect = pygame.Rect(block_rect.x + cx*tile_w,
                                       block_rect.y + cy*tile_h,
                                       tile_w, tile_h)
                color_pair = ((110,110,110), (90,90,90))
                color = color_pair[(cx+cy)%2]
                pygame.draw.rect(screen, color, sub_rect)

            # animate current tile
            if tiles_completed < total_tiles:
                idx_next = order[tiles_completed]
                cx = idx_next % cols
                cy = idx_next // cols
                target = pygame.Vector2(block_rect.x + cx*tile_w + tile_w/2,
                                        block_rect.y + cy*tile_h + tile_h/2)
                start_pos = pygame.Vector2(WIDTH/2, HEIGHT/2)
                tile_center = start_pos.lerp(target, fractional)
                sub_rect = pygame.Rect(0,0,tile_w,tile_h)
                sub_rect.center = (tile_center.x, tile_center.y)
                color_pair = ((110,110,110), (90,90,90))
                color = color_pair[(cx+cy)%2]
                pygame.draw.rect(screen, color, sub_rect)

        # --- pop animations after rebuild ---
        for p in self.pop_anims:
            age = now - p['start']
            t = age / Castle.POP_DURATION
            rect = p['rect']
            scale = 1 + 0.3 * math.sin(math.pi * t)
            scaled_size = int(self.block_size * scale)
            surf = self.get_block_texture(rect)
            surf = pygame.transform.scale(surf, (scaled_size, scaled_size))
            draw_rect = surf.get_rect(center=rect.center)
            screen.blit(surf, draw_rect)

            # shockwave ring for pop animation
            shockwave_progress = t  # t goes from 0 to 1 over POP_DURATION
            max_radius = self.block_size * 2
            rad = int(max_radius * shockwave_progress)
            if 2 < rad < max_radius:
                pygame.draw.circle(screen, (255,255,255), rect.center, rad, 2)

        # --- draw debris pieces ---
        # Always draw debris, even during paddle intro animations
        for d in self.debris:
            # Skip if shrunk away completely
            if d.get('size', 0) <= 0:
                continue
            x, y = int(d['pos'].x), int(d['pos'].y)
            size = int(max(1, d['size']))  # ensure at least 1 pixel for visibility
            pygame.draw.rect(screen, d['color'], (x, y, size, size))

        # ------------------------------------------------------------------
        # CANNON DRAW PASS – cannons now positioned on castle blocks
        # ------------------------------------------------------------------
        preview_col_map = {'white': (220,220,220), 'red': (255,60,60), 'power': (255,255,80)}
        for c in self.cannons:
            # Delegate drawing to the cannon object itself.
            c.draw(screen, now, self._preview_types, preview_col_map)

        # draw smoke particles
        for s in self.smoke_particles:
            pygame.draw.circle(screen, (30,30,30), (int(s['pos'].x), int(s['pos'].y)), 2)

    def _spawn_ball(self, cannon, shot_type):
        """Create and return a Ball fired from the specified cannon."""
        # Sound preparation is a castle-level responsibility.
        _prepare_shot_sounds()

        # Delegate ball creation to the cannon object itself.
        ball = cannon.spawn_ball(shot_type, _prepare_shot_sounds, _SHOT_SOUNDS)

        if ball:
            Castle.total_shots += 1
            # ----------------------------------------------------
            # Wave–dependent accuracy & speed adjustments
            # ----------------------------------------------------
            wave_lvl = getattr(self, 'level', 1)
            # Increase base speed by 5 % per wave beyond the first
            speed_boost = 1.0 + 0.05 * max(0, wave_lvl - 1)
            ball.vel *= speed_boost
            # Degrade accuracy (more precise at higher waves)
            # Make early waves notably less accurate (harder to aim accurately)
            # Start at ±25° spread on wave 1 and tighten by 3° every subsequent wave.
            max_noise_deg = max(0.0, 25.0 - 3.0 * (wave_lvl - 1))
            if max_noise_deg > 0:
                ball.vel = ball.vel.rotate(random.uniform(-max_noise_deg, max_noise_deg))
            # ----------------------------------------------------
            # Keep the reservation active until the potion projectile is fully
            # registered in the main balls list.  This prevents another cannon
            # from beginning a potion charge in the very same frame and firing
            # two potions simultaneously.
            # (Reset now handled automatically at the start of update_castle
            #  when no active power-up projectiles are detected.)
            if shot_type == 'power':
                pass  # reservation remains True until the projectile exits play
        
        return ball

    def shatter_block(self, block, incoming_dir):
        """Destroy a block with visual debris based on incoming ball direction."""
        key = (block.x, block.y)
        color_pair = self.block_colors.get(key, ((110,110,110),(90,90,90)))

        # ----------------------------------------------------------
        #  Debris logic depends on reinforcement tier and destruction
        # ----------------------------------------------------------
        tier = getattr(self, 'block_tiers', {}).get(key, 2)
        cur_hp = self.block_health.get(key, 1) if key in self.block_health else 1
        will_destroy = (cur_hp - 1) <= 0  # health after this hit

        # --------------------------------------------------------------
        #  Heart drop – 10 % chance (1 % for triple hearts) on destruction
        # --------------------------------------------------------------
        if will_destroy:
            try:
                from heart import maybe_spawn_hearts
                # print("[HEART] Attempting spawn on block destroy")
                maybe_spawn_hearts(block)
                # print("[HEART] Spawn call completed")
            except Exception as e:
                # print("[HEART] Spawn error:", e)
                pass

            # --------------------------------------------------------------
            #  Coin drop on block destruction
            # --------------------------------------------------------------
            try:
                from coin import maybe_spawn_coins
                maybe_spawn_coins(block)
            except Exception as e:
                print("[COIN] Spawn error:", e)

        # Fewer chips for reinforced hits that don't destroy
        if tier > 2 and not will_destroy:
            debris_count = 8
            allow_dig    = False  # no dirt streaks – just small chips
        else:
            debris_count = 30
            # Only layer-1 destruction gets dirt streaks
            allow_dig    = (tier == 2 and will_destroy)

        # DEBRIS FIX: Don't create debris during paddle intro animations
        if not getattr(self, '_pause_rebuild', False):
            base_dir = (-incoming_dir.normalize()) if incoming_dir.length_squared()!=0 else pygame.Vector2(0, -1)
            for _ in range(debris_count):
                angle_variation = random.uniform(-40, 40)
                speed = random.uniform(2, 6) * SCALE
                vel = base_dir.rotate(angle_variation) * speed
                col = random.choice(color_pair)
                size = int(random.randint(2,4) * SCALE)
                pos = pygame.Vector2(block.centerx, block.centery)
                deb = {'pos': pos.copy(), 'vel': vel, 'color': col, 'size': size,
                       'friction': random.uniform(0.94, 0.985)}
                if allow_dig and random.random() < 0.3:
                    deb['dig_delay']  = random.randint(0, int(15 * SCALE))   # frames before it starts digging
                    deb['dig_frames'] = random.randint(int(15 * SCALE), int(90 * SCALE))  # how long it digs
                self.debris.append(deb)

        # Remove the block via existing logic
        self._skip_debris = True
        self.hit_block(block)

    def _scale(self, key, score):
        """Return 0-1 difficulty factor based on the player's score.
        The value ramps up once *score* exceeds the per-aspect offset and
        reaches 1.0 after roughly 40 points beyond that offset. (Historical
        comment referenced 1 000 points, but the logic now caps much sooner.)"""
        offset = self._score_offsets[key]
        return max(0.0, min(1.0, (score - offset) / 40.0)) 

    def _build_perimeter_track(self):
        """Recompute perimeter tracks and mapping via helper function."""
        # 1) CW ordered blocks
        self.perimeter_track, self.block_to_track_index = build_tracks(self.blocks, self.block_size)
        # 2) Pixel rails hugging outside faces
        self.rail_info = build_rails(self.blocks, self.block_size)

        # Refresh each cannon's rail pointers so they survive rebuilds
        for c in getattr(self, 'cannons', []):
            blk_key = (c.block.x, c.block.y)
            # Ensure the cannon's rail info is updated correctly
            if self.rail_info:
                c.rail_id, c.rail_idx = self.rail_info.nearest_node(blk_key)
            c.path_queue = []  # clear any in-flight path – will be recomputed on next AI tick

    def _get_cannon_track_pos(self, cannon):
        """Return (track_id, index_in_track) for the cannon's current block."""
        block_key = (cannon.block.x, cannon.block.y)
        return self.block_to_track_index.get(block_key, (0,0))

    def _get_block_side(self, block):
        """Return an *exposed* side ('top','bottom','left','right') of the block.

        We prefer a side that has NO neighbouring castle tile – that guarantees
        the cannon will sit outside the wall.  If multiple sides are exposed we
        choose the one furthest from the castle centre so cannons always face
        outward even on concave layouts.
        """
        bs = self.block_size
        existing = {(b.x, b.y) for b in self.blocks}

        exposures = []  # list of (side, distance_sq)
        center_x, center_y = WIDTH // 2, HEIGHT // 2

        # Top
        if (block.x, block.y - bs) not in existing:
            top_pos = (block.x, block.y - bs)
            if not is_enclosed_tile(top_pos, existing, bs):
                dy = block.centery - center_y
                exposures.append(('top', dy*dy))
        # Bottom
        if (block.x, block.y + bs) not in existing:
            bottom_pos = (block.x, block.y + bs)
            if not is_enclosed_tile(bottom_pos, existing, bs):
                dy = block.centery - center_y
                exposures.append(('bottom', dy*dy))
        # Left
        if (block.x - bs, block.y) not in existing:
            left_pos = (block.x - bs, block.y)
            if not is_enclosed_tile(left_pos, existing, bs):
                dx = block.centerx - center_x
                exposures.append(('left', dx*dx))
        # Right
        if (block.x + bs, block.y) not in existing:
            right_pos = (block.x + bs, block.y)
            if not is_enclosed_tile(right_pos, existing, bs):
                dx = block.centerx - center_x
                exposures.append(('right', dx*dx))

        if not exposures:
            # Fallback (shouldn't happen) – default by position
            dx = block.centerx - center_x
            dy = block.centery - center_y
            return 'right' if abs(dx) > abs(dy) and dx>0 else (
                   'left'  if abs(dx) > abs(dy) else (
                   'bottom' if dy>0 else 'top'))

        # Choose the side with the **largest** distance so cannon is outside
        exposures.sort(key=lambda t: -t[1])
        return exposures[0][0]
    
    def _get_edge_pos(self, block, side):
        """Get cannon position for a block and side."""
        if side == 'top':
            return pygame.Vector2(block.centerx, block.top - CANNON_GAP)
        elif side == 'bottom':
            return pygame.Vector2(block.centerx, block.bottom + CANNON_GAP)
        elif side == 'left':
            return pygame.Vector2(block.left - CANNON_GAP, block.centery)
        else:  # right
            return pygame.Vector2(block.right + CANNON_GAP, block.centery)

    def _assign_new_target(self, cannon, paddle_sides, dest_idx=None, player_wall=None):
        """Move cannon to a strategic position anywhere in the castle like a chess piece.
        Cannons can now move to any valid castle block, not just perimeter.
        """
        # -------------------------------------------------------------------
        #  Build a set of blocks already occupied or reserved by *other* cannons
        # -------------------------------------------------------------------
        taken = set()
        for other in self.cannons:
            if other is cannon:
                continue
            blk = other.block
            if blk:
                taken.add((blk.x, blk.y))
            dest_blk = other.dest_block
            if dest_blk:
                taken.add((dest_blk.x, dest_blk.y))

        # Get all valid castle blocks as potential positions
        valid_positions = []
        
        for block in self.blocks:
            # Skip the block the cannon is currently on
            if block == cannon.block:
                continue
                
            # Check if this block would give the cannon a good firing position
            block_center = pygame.Vector2(block.centerx, block.centery)
            
            # Calculate if cannon can hit paddles from this position
            can_hit_paddle = False
            if paddle_sides:
                for side in paddle_sides:
                    # Estimate paddle position based on side
                    if side == 'bottom':
                        paddle_pos = pygame.Vector2(WIDTH//2, HEIGHT - 50)
                    elif side == 'top':
                        paddle_pos = pygame.Vector2(WIDTH//2, 50)
                    elif side == 'left':
                        paddle_pos = pygame.Vector2(50, HEIGHT//2)
                    elif side == 'right':
                        paddle_pos = pygame.Vector2(WIDTH - 50, HEIGHT//2)
                    else:
                        continue
                    
                    # Check if there's a clear line of sight
                    distance = block_center.distance_to(paddle_pos)
                    if distance < 300:  # Within reasonable range
                        can_hit_paddle = True
                        break
            
            # Calculate if cannon can hit player wall from this position
            can_hit_wall = False
            if player_wall and player_wall.blocks:
                wall_center = pygame.Vector2(player_wall.blocks[0].centerx, player_wall.blocks[0].centery)
                distance = block_center.distance_to(wall_center)
                if distance < 400:  # Within range of player wall
                    can_hit_wall = True
            
            # Add position if it can target something **and** is not taken
            if (can_hit_paddle or can_hit_wall) and (block.x, block.y) not in taken:
                # Calculate priority based on strategic value
                priority = 0
                if can_hit_paddle:
                    priority += 10
                if can_hit_wall:
                    priority += 5
                
                # Prefer positions closer to center for better coverage
                center_distance = block_center.distance_to(pygame.Vector2(WIDTH//2, HEIGHT//2))
                priority += max(0, 100 - center_distance/5)  # Closer to center = higher priority
                
                valid_positions.append((block, priority))
        
        if not valid_positions:
            # Fallback: move to any random castle block
            if len(self.blocks) > 1:
                available_blocks = [b for b in self.blocks if b != cannon.block and (b.x, b.y) not in taken]
                if available_blocks:
                    target_block = random.choice(available_blocks)
                    valid_positions = [(target_block, 1)]
        
        if valid_positions:
            # Sort by priority and pick one of the top candidates
            valid_positions.sort(key=lambda x: x[1], reverse=True)
            top_candidates = valid_positions[:min(3, len(valid_positions))]  # Top 3 positions
            target_block, _ = random.choice(top_candidates)
            
            # ---------------- Schedule smooth slide -------------------
            dest_side = self._get_block_side(target_block)
            dest_pos  = self._get_edge_pos(target_block, dest_side)

            # Record destination so the update() loop can interpolate
            cannon.dest_block = target_block
            cannon.dest_side  = dest_side
            cannon.dest_pos   = dest_pos

            # Reset aiming flags – they'll be recalculated on arrival
            cannon.aim_at_wall = None
            if hasattr(cannon, 'target_block'):
                delattr(cannon, 'target_block')

    def _record_damage_event(self, rail_id, idx):
        """Record a damage event for the specified rail and index."""
        self.damage_events.append({'rail_id': rail_id, 'idx': idx, 'time': pygame.time.get_ticks()})

    # --------------------------------------------------------------
    #  Aggression helper – returns 0..1 ramping by 1/30 per shot (cap at 30 shots).
    # --------------------------------------------------------------
    def _shot_scale(self):
        """Aggression helper – returns 0..1 ramping by 1/30 per shot (cap at 30 shots)."""
        return min(1.0, Castle.total_shots * (1/30))

    @classmethod
    def from_mask(cls, mask, block_size=None, level=1, staged_build=False, build_callback=None):
        """Build a Castle from a mask (2D numpy array, 0=empty, 1=grass, 2=wall, 3=floor).
        If staged_build is True, use the staged build animation system instead of instant build.
        build_callback is called after each brick or turret is built (for sound, etc).
        """
        import numpy as np
        import pygame
        height, width = mask.shape
        size = block_size if block_size is not None else BLOCK_SIZE
        self = cls(level=level)
        self.block_size = size
        self.blocks = []
        self.block_colors = {}
        self.block_shapes = {}
        self.block_health = {}
        self.cannon_blocks = {}
        self.destroyed_blocks = {}
        self.pop_anims = []
        self.block_textures = {}
        self.block_tiers = {}
        wall_count = 0
        if staged_build:
            # Use the new staged build animation system
            staged_castle_build(self, mask, size, level, build_callback)
            return self
        # Place blocks according to mask
        print("[DEBUG] New wave mask:")
        for row in mask:
            print("[DEBUG]", ' '.join(str(int(v)) for v in row))
        print("[DEBUG] Block colors and healths:")
        for y in range(height):
            for x in range(width):
                if mask[y, x] >= BlockType.WALL.value:  # Any wall layer (2,3,4)
                    wall_count += 1
                    px = WIDTH // 2 + (x - width // 2) * size
                    py = HEIGHT // 2 + (y - height // 2) * size
                    rect = pygame.Rect(px, py, size, size)
                    key = (rect.x, rect.y)
                    # Set both health and tier together
                    val = mask[y, x]
                    extra = 0 if val == 2 else (1 if val == 3 else 2)
                    self.block_health[key] = 1 + extra
                    self.block_tiers[key] = val
                    # Track the original tier for this block
                    self.original_block_tiers[key] = val
                    self.set_block_color_by_strength(key, val)
                    self.block_shapes[key] = 'wall'
                    print(f"[DEBUG]   ({x},{y}) tier={val} color={self.block_colors[key]} health={self.block_health.get(key, 2)}")
        print(f"[DEBUG] from_mask: mask wall tiles={wall_count}, blocks created={len(self.blocks)}")
        # Optionally handle floor/grass for future expansion
        # elif mask[y, x] == 3: ...
        # elif mask[y, x] == 1: ...
        # Build cannons, perimeter, etc. as in __init__
        self._build_perimeter_track()
        self.cannons = []
        max_cannons_wave = Castle._max_cannons_for_wave(level)
        all_blocks = self.blocks[:]
        random.shuffle(all_blocks)
        selected_blocks = all_blocks[:max_cannons_wave]
        selected = []
        for rect in selected_blocks:
            side = self._get_block_side(rect)
            selected.append((rect, side))
            if side not in self.cannon_blocks:
                self.cannon_blocks[side] = rect
        if len(selected) > max_cannons_wave:
            selected = selected[:max_cannons_wave]
        for rect, side in selected:
            if len(self.cannons) >= max_cannons_wave:
                break
            
            pos = self._get_edge_pos(rect, side)
            new_cannon = Cannon(
                block=rect,
                side=side,
                pos=pos,
                rail_info=self.rail_info,
                total_shots_ref=lambda: Castle.total_shots,
                shooting_enabled_ref=lambda: self.shooting_enabled,
                smoke_particles_ref=self.smoke_particles,
                level=self.level
            )
            new_cannon.sprout_delay = 0 # Sprout immediately
            new_cannon.idle_timer = random.randint(600, 1200)
            new_cannon.initial_decision_pending = True # Needs to make a decision
            self.cannons.append(new_cannon)

        self.smoke_particles = []
        self._new_balls = []
        self.debris = []
        self._score_offsets = {
            'think': 100,
            'preview': 200,
            'charge': 300,
            'prob': 400
        }
        self.perimeter_track = []
        self.block_to_track_index = {}
        self.damage_events = []
        return self

    def set_block_color_by_strength(self, key, tier):
        """Assign the correct color for a block based on its reinforcement tier (2, 3, 4)."""
        print(f"[DEBUG] set_block_color_by_strength: key={key}, tier={tier}")
        if tier == 2:
            self.block_colors[key] = BLOCK_COLOR_L1
            print(f"[DEBUG] Set color to BLOCK_COLOR_L1: {BLOCK_COLOR_L1}")
        elif tier == 3:
            self.block_colors[key] = BLOCK_COLOR_L2
            print(f"[DEBUG] Set color to BLOCK_COLOR_L2: {BLOCK_COLOR_L2}")
        elif tier == 4:
            self.block_colors[key] = BLOCK_COLOR_L3
            print(f"[DEBUG] Set color to BLOCK_COLOR_L3: {BLOCK_COLOR_L3}")
        else:
            self.block_colors[key] = BLOCK_COLOR_DEFAULT  # fallback
            print(f"[DEBUG] Set color to BLOCK_COLOR_DEFAULT: {BLOCK_COLOR_DEFAULT}")