import pygame, sys, random, math, os
from config import *
from utils import generate_grass, Particle
from paddle import Paddle
from ball import Ball
from castle import Castle
# --- new module for player health wall ---
from player_wall import PlayerWall
from tutorial import TutorialOverlay  # start-game control helper
from cg import generate_mask_for_difficulty  # Add this import
from paddle_intro import PaddleIntro
from game_over import run_game_over
from castle_build_anim import update_castle_build_anim, draw_castle_build_anim
# Heart collectible
from heart import update_hearts, draw_hearts
# Coin collectible and store system
from coin import update_coins, draw_coins, get_coin_count, clear_coins
from store import get_store
from upgrade_effects import apply_upgrade_effects, reset_upgrade_states
from pause_menu import PauseMenu  # <--- new import for in-game pause menu
from options_menu import OptionsMenu  # <--- new import for options menu

# --- helper ---
def reflect(ball, rect):
    """Robust circle-rectangle reflection with rounded-corner behaviour.

    1. Compute the closest point on the rect to the ball centre.
    2. The collision normal is from that point toward the centre.
    3. If the centre is inside the rect (rare), fall back to axis-based normal.
    4. Reflect the velocity about the normal and push the ball outside.
    """
    orig_speed = ball.vel.length()

    # Step 1: closest point on rect to circle centre
    closest_x = max(rect.left, min(ball.pos.x, rect.right))
    closest_y = max(rect.top,  min(ball.pos.y, rect.bottom))
    closest = pygame.Vector2(closest_x, closest_y)

    # Step 2: normal vector
    normal = ball.pos - closest
    if normal.length_squared() == 0:
        # Ball centre is exactly on an edge or inside rect – use axis overlap
        overlap_left   = ball.pos.x - rect.left
        overlap_right  = rect.right - ball.pos.x
        overlap_top    = ball.pos.y - rect.top
        overlap_bottom = rect.bottom - ball.pos.y
        min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
        if min_overlap in (overlap_left, overlap_right):
            normal = pygame.Vector2(-1 if overlap_left < overlap_right else 1, 0)
        else:
            normal = pygame.Vector2(0, -1 if overlap_top < overlap_bottom else 1)
    else:
        normal = normal.normalize()

    # Step 3: reflect velocity and reposition circle just outside rect
    ball.vel = ball.vel.reflect(normal)
    ball.pos = closest + normal * (BALL_RADIUS + 0.1)

    if orig_speed != 0:
        ball.vel = ball.vel.normalize() * orig_speed

    # Any bounce converts a friendly cannonball into hostile – it can now
    # damage the enemy castle on subsequent collisions.
    if hasattr(ball, 'friendly'):
        ball.friendly = False

# --- true concave paddle reflection ------------------------------------
# Computes a custom normal based on the hit position along the paddle so
# that the outgoing angle naturally curves toward the castle without
# artificially altering physics post-bounce.

CURVE_ANGLE = 0  # paddles are straight now

def curved_paddle_reflect(ball, paddle):
    """Reflect the ball off a paddle with a slight concave curvature."""
    # Determine base normal and offset ratio along the paddle length
    if paddle.side == 'top':
        base_normal = pygame.Vector2(0, 1)  # facing down
        ratio = (ball.pos.x - paddle.rect.centerx) / (paddle.rect.width / 2)
        angle = -ratio * CURVE_ANGLE
    elif paddle.side == 'bottom':
        base_normal = pygame.Vector2(0, -1)  # facing up
        ratio = (ball.pos.x - paddle.rect.centerx) / (paddle.rect.width / 2)
        angle = ratio * CURVE_ANGLE
    elif paddle.side == 'left':
        base_normal = pygame.Vector2(1, 0)   # facing right
        ratio = (ball.pos.y - paddle.rect.centery) / (paddle.rect.height / 2)
        angle = ratio * CURVE_ANGLE
    else:  # right
        base_normal = pygame.Vector2(-1, 0)  # facing left
        ratio = (ball.pos.y - paddle.rect.centery) / (paddle.rect.height / 2)
        angle = -ratio * CURVE_ANGLE

    # Clamp ratio within [-1,1] just in case
    angle = max(-CURVE_ANGLE, min(CURVE_ANGLE, angle))
    normal = base_normal.rotate(angle).normalize()

    orig_speed = ball.vel.length()
    ball.vel = ball.vel.reflect(normal)
    if orig_speed:
        ball.vel = ball.vel.normalize() * orig_speed

    # Re-position ball just outside paddle to avoid sticking
    ball.pos += normal * (BALL_RADIUS + 0.1)

    # Ball has bounced – it can now damage the castle
    ball.friendly = False

    # --------------------------------------------------
    #  Spin transfer – paddles impart angular velocity
    # --------------------------------------------------
    # Horizontal paddles: rightward motion (positive vel) gives clockwise spin (positive value)
    # Vertical paddles: upward motion (negative vel) should yield clockwise spin, hence sign inversion.
    try:
        from config import SPIN_TRANSFER
    except ImportError:
        SPIN_TRANSFER = 1

    if paddle.side in ('top', 'bottom'):
        ball.spin += paddle.vel * SPIN_TRANSFER
    else:
        # For vertical paddles, invert sign so upward motion imparts expected spin direction
        ball.spin -= paddle.vel * SPIN_TRANSFER

def paddle_ball_collision_2d(ball, paddle):
    """Apply 2D elastic collision between ball and paddle using both paddle velocities."""
    # Construct paddle's full 2D velocity vector
    if paddle.side in ('top', 'bottom'):
        # For top/bottom: x is side-to-side, y is inward
        if paddle.side == 'bottom':
            paddle_vel = pygame.Vector2(paddle.vel, -paddle.inward_vel)  # inward is up (negative y)
        else:  # top
            paddle_vel = pygame.Vector2(paddle.vel, paddle.inward_vel)   # inward is down (positive y)
    else:
        # For left/right: y is side-to-side, x is inward
        if paddle.side == 'left':
            paddle_vel = pygame.Vector2(paddle.inward_vel, paddle.vel)   # inward is right (positive x)
        else:  # right
            paddle_vel = pygame.Vector2(-paddle.inward_vel, paddle.vel)  # inward is left (negative x)
    
    # Compute collision normal (from paddle center to ball center)
    paddle_center = pygame.Vector2(paddle.rect.centerx, paddle.rect.centery)
    normal = (ball.pos - paddle_center).normalize()
    
    # Project velocities onto the collision normal
    v_ball_n = ball.vel.dot(normal)
    v_paddle_n = paddle_vel.dot(normal)
    
    # Only proceed if they're moving toward each other
    if v_ball_n - v_paddle_n < 0:
        # 1D elastic collision along the normal
        m_ball, m_paddle = 1, 2  # paddle is heavier
        v_ball_n_new = ((m_ball - m_paddle) * v_ball_n + 2 * m_paddle * v_paddle_n) / (m_ball + m_paddle)
        
        # Update ball velocity: replace normal component
        ball.vel += (v_ball_n_new - v_ball_n) * normal

pygame.init()
pygame.mixer.init()
MUSIC_PATH = "Untitled.mp3"  # background soundtrack in project root
try:
    pygame.mixer.music.load(MUSIC_PATH)
    pygame.mixer.music.set_volume(0.6)
    # Playback will start in the title screen overlay

    # print('[Audio] Sound effects loaded successfully')
    print('[Audio] Title music preloaded')
except pygame.error as e:
    print(f"[Audio] Failed to load '{MUSIC_PATH}':", e)

# --- music control flags ---
TUT_LOOP_MS = 3600000  # 1 hour
TUT_SILENCE_MS = 190        # extra silent gap between loops
tutorial_looping  = True    # while the tutorial overlay is active
last_tut_restart  = pygame.time.get_ticks()
# track if we are in the silence interval
_tut_pause_until = 0

# --- Scan for available wave music files (Untitled3.mp3 to Untitled10.mp3) ---
WAVE_MUSIC_FILES = []
for i in range(3, 11):
    fname = f"Untitled{i}.mp3"
    if os.path.isfile(fname):
        WAVE_MUSIC_FILES.append(fname)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock  = pygame.time.Clock()
font       = pygame.font.SysFont(None, 36)
# small pixel font
small_font = pygame.font.SysFont(None, 18)

# Generate a background grass texture once
BACKGROUND = generate_grass(WIDTH, HEIGHT)  # Full opacity to match menu
WHITE_BG = pygame.Surface((WIDTH, HEIGHT))
WHITE_BG.fill(WHITE)

# off-screen scene surface for screen shake
scene_surf = pygame.Surface((WIDTH, HEIGHT))

# --- Game setup ---
# Waves & castle size control -------------------------------------------
wave          = 1               # current wave index (starts at 1)
castle_dim_x  = 5               # starting footprint width  (blocks)
castle_dim_y  = 5               # starting footprint height (blocks)

# --- Wave transition state ---
wave_transition = {
    'active': False,
    'state': 'idle',      # idle → approach → pre_store_delay → fade_to_store → store_fade_in → focus → store_fade_out → resume_fade_in → resume
    'timer': 0,
    'block_pos': None,
    # --- tunables ---
    'min_scale': 0.25,
    'zoom_target': 1,
    'duration_approach': 800,  # ms – zoom in & slow down
    'duration_focus': 0,       # ms – stay at max zoom/slomo (no extra hold)
    'duration_resume': 2000,   # ms – zoom out & speed up (2 s)
    'duration_pre_store_delay': 1500, # ms – slow-mo after last block
    'duration_fade_to_store': 700,    # ms – fade to black before store
    'duration_store_fade_in': 700,    # ms – fade in store
    'duration_store_fade_out': 700,   # ms – fade out store
    'duration_resume_fade_in': 700,   # ms – fade in after store
    'next_wave_ready': False,
    'closeness': 0.0,    # smoothed proximity ratio during approach
    'no_close': 0,       # ms accumulated with no nearby balls
    'fade_alpha': 0,     # for fade transitions
    'store_opened': False,  # Track if store has been opened for this transition
}

def get_wave_difficulty(wave):
    return min(5 + (wave - 1) * 5, 75)

def get_wave_mask_size(wave):
    """Return (width, height) for the mask for a given wave. Wave 1: 10x8, grows to 20x15 by wave 10+."""
    min_w, min_h = 10, 8
    max_w, max_h = 20, 15
    # Clamp wave between 1 and 10
    wv = max(1, min(wave, 10))
    width = min_w + (max_w - min_w) * (wv - 1) // 9
    height = min_h + (max_h - min_h) * (wv - 1) // 9
    return width, height

def create_castle_for_wave(wave):
    mask_w, mask_h = get_wave_mask_size(wave)
    # --- Dynamic cannon scaling by wave ---
    # Use unified logic from Castle to avoid duplication.
    max_cannons = Castle._max_cannons_for_wave(wave)
    # Apply to the Castle class so subsequent construction uses the wave limit
    Castle.MAX_CANNONS = max_cannons
    # Also update the module-level constant so internal castle logic uses it
    import castle as _castle_module
    _castle_module.MAX_CANNONS = max_cannons
    # ----------------------------------------------------
    min_blocks = 4 if wave == 1 else 6
    mask = generate_mask_for_difficulty(mask_w, mask_h, get_wave_difficulty(wave), min_wall_blocks=min_blocks)
    print(f"[DEBUG] mask for wave {wave} (unique values): {set(mask.flatten())}")
    if DEBUG:
        print(mask)
    castle = Castle.from_mask(
        mask,
        block_size=BLOCK_SIZE,
        level=wave,
        staged_build=True,
        build_callback=lambda typ, idx: (
            sounds['castle_build_whoosh'].play() if typ=='brick' and idx%2==0 and 'castle_build_whoosh' in sounds else None
            or sounds['paddle_hit'].play() if typ=='turret' and 'paddle_hit' in sounds else None
        )
    )
    # Reset the global shot counter baseline for the new wave. Wave 1 starts
    # at 0 shots; every subsequent wave raises the baseline by 5 shots (≈5 %).
    # This baseline influences AI aggression via Castle._shot_scale().
    Castle.total_shots = int(max(0, (wave - 1) * 5))
    castle.shooting_enabled = False
    print(f"[DEBUG] Wave {wave}: castle has {len(castle.blocks)} blocks")
    return castle, mask

# Create the very first castle using the mask system
castle, mask = create_castle_for_wave(wave)
castle_building = False  # Don't start building until after tutorial
castle_built_once = False  # Track if first build animation has run

# Bottom-edge health wall (persists across waves)
player_wall   = PlayerWall()

# Paddle roster – begin with the bottom paddle only.  Remaining paddles are
# unlocked at score milestones.
paddles = {
    'bottom': Paddle('bottom')
}

# Active game objects -----------------------------------------------------
balls        = []
score        = 0
particles = []
# Tutorial overlay (displayed for the first few seconds)
tutorial_overlay = TutorialOverlay()
# Pause menu overlay
pause_menu = PauseMenu()
# Options menu overlay
options_menu = OptionsMenu()
# Apply saved settings on startup
options_menu._apply_settings()
# Store interface
store = get_store()
# Set game state references for upgrade effects
store.set_game_state(paddles, player_wall, castle)
# Disable cannon fire until tutorial is dismissed (restart)
castle.shooting_enabled = False

# --- Wave banner particle effects ---
wave_banner_sparks = []
wave_banner_smoke = []

# screen shake control
shake_frames = 0
shake_intensity = 0

# screen flash control
flash_color = None
flash_timer = 0
FLASH_DURATION = 400  # ms
POWER_DURATION = 10000  # ms (power-up active time)

power_timers = {}  # side -> (type, expiry_time)

# Global barrier power timer
barrier_timer = 0
# Scheduled time (ms) when cannon shooting should be re-enabled after tutorial
shoot_enable_time = 0

# --- Wave announcement text ---------------------------------------------
wave_font      = pygame.font.SysFont(None, 72, italic=True)
wave_text      = ""
wave_text_time = 0  # ms remaining

# --- Paddle unlock animation -------------------------------------------
intro_font = pygame.font.SysFont(None, 48, italic=True)

# Holds active intro animations (created when a new paddle unlocks)
intros = []

# --- Castle build speed multiplier (ramps up when no balls) ---
castle_build_speed_mult = 1.0  # 1.0 = normal, 5.0 = max fast
CASTLE_BUILD_SPEED_MAX = 5.0
CASTLE_BUILD_SPEED_MIN = 1.0
CASTLE_BUILD_SPEED_SMOOTH_TC = 0.25  # seconds (smoothing time constant)

# --------------------------------------------------
# Screen-shake helper – call with intensity 1-20.
# --------------------------------------------------

def trigger_shake(intensity: int = 6):
    """Start a camera shake of *intensity* pixels (peak)."""
    global shake_frames, shake_intensity
    intensity = max(1, int(intensity))
    shake_intensity = intensity
    # Shake lasts slightly longer for larger hits
    shake_frames = max(6, intensity)

# --- Main loop ---
running = True
last_time = pygame.time.get_ticks()
# timer to restart music after fade-out between waves (0 means inactive)
music_restart_time = 0

# Flag so the slide-down SFX triggers only once
game_over_sfx_played = False

# ---------------------------------------------------------
#  Sound-effects loading (restored)
# ---------------------------------------------------------
sounds = {}
try:
    def _load_sound(base):
        for ext in ('.wav', '.aac'):
            fname = f"{base}{ext}"
            try:
                return pygame.mixer.Sound(fname)
            except pygame.error:
                continue
        raise pygame.error("Unrecognized audio format or file missing: " + base)

    sounds['powerup']       = _load_sound('Glitchedtones - User Interface - 8 Bit Arpeggio Bright')
    sounds['wall_break']    = _load_sound('Sound Response - 8 Bit Retro - Pixelated Explosion Direct Hit')
    sounds['paddle_damage'] = _load_sound('Sound Response - 8 Bit Retro - Arcade Blip')
    sounds['paddle_hit']    = _load_sound('Ni Sound - Interfacing - 8-Bit Hit Crushed Dull')
    # New SFX ----------------------------------------------
    sounds['game_over_slide'] = _load_sound('Sound Response - 8 Bit Retro - Slide Down Game Over')
    # Add castle build whoosh sound
    sounds['castle_build_whoosh'] = _load_sound('Alberto Sueri - 8 Bit Fun - Quick Whoosh Gritty ')

    # Set volumes
    for snd in sounds.values():
        snd.set_volume(0.4)

    # print('[Audio] Sound effects loaded successfully')
except pygame.error as e:
    print(f'[Audio] Failed to load sound effects: {e}')
    sounds = {}

# --- Track last played wave music to avoid repeats ---
last_wave_music = None

while running:
    ms = clock.tick(FPS)

    # -----------------------------------------------------
    #  TIME-SCALE & STATE MACHINE FOR WAVE TRANSITION
    # -----------------------------------------------------
    time_scale = 1.0  # default (real-time)
    if wave_transition['state'] == 'approach':
        # --- distance-based slow-motion & zoom control ---
        bx, by = wave_transition['block_pos'] if wave_transition['block_pos'] else (WIDTH//2, HEIGHT//2)
        block_vec = pygame.Vector2(bx, by)
        max_dist = 30  # distance (px) at which slowdown/zoom start (was 200, now 40% of original)
        if balls:
            cur_dist = min((block_vec - b.pos).length() for b in balls)
        else:
            cur_dist = max_dist
        # closeness ratio 0.0 (far) → 1.0 (touching)
        target_close = max(0.0, min(1.0, 1.0 - cur_dist / max_dist))
        # --- very smooth easing toward target closeness ---
        prev_close = wave_transition.get('closeness', 0.0)
        # Exponential smoothing that is frame-rate independent (half-life ≈ 300 ms)
        SMOOTH_TC = 0.3  # seconds
        alpha = 1 - math.exp(-ms/1000 / SMOOTH_TC)
        closeness = prev_close + (target_close - prev_close) * alpha
        wave_transition['closeness'] = closeness  # store smoothed value
        time_scale = 1.0 - (1.0 - wave_transition['min_scale']) * closeness  # proportional slow-mo
    elif wave_transition['state'] == 'focus':
        time_scale = wave_transition['min_scale']
    elif wave_transition['state'] == 'resume':
        prog = min(1.0, wave_transition['timer'] / wave_transition['duration_resume'])
        time_scale = wave_transition['min_scale'] + (1.0 - wave_transition['min_scale']) * prog

    # Pause gameplay while an intro animation is active (unless in transition)
    intro_active = bool(intros)
    # Temporarily disable cannon shooting during paddle intro animations
    if intro_active:
        if not hasattr(castle, '_pre_intro_shoot'):  # save once
            castle._pre_intro_shoot = castle.shooting_enabled
        castle.shooting_enabled = False
    elif hasattr(castle, '_pre_intro_shoot'):
        castle.shooting_enabled = castle._pre_intro_shoot
        delattr(castle, '_pre_intro_shoot')

    # -------------------------------------------------------------
    # NEW: Temporarily disable cannon shooting while game is paused
    # -------------------------------------------------------------
    if pause_menu.active:
        if not hasattr(castle, '_pre_pause_shoot'):
            # Remember current state so we can restore later
            castle._pre_pause_shoot = castle.shooting_enabled
        castle.shooting_enabled = False
    elif hasattr(castle, '_pre_pause_shoot'):
        # Restore previous shooting state when unpaused
        castle.shooting_enabled = castle._pre_pause_shoot
        delattr(castle, '_pre_pause_shoot')

    # -------------------------------------------------------------
    # NEW: Temporarily disable cannon shooting while the store is open
    # -------------------------------------------------------------
    if store.active:
        if not hasattr(castle, '_pre_store_shoot'):
            castle._pre_store_shoot = castle.shooting_enabled
        castle.shooting_enabled = False
    elif hasattr(castle, '_pre_store_shoot'):
        castle.shooting_enabled = castle._pre_store_shoot
        delattr(castle, '_pre_store_shoot')

    # -------------------------------------------------------------
    # NEW: Temporarily disable cannon shooting while options menu is open
    # -------------------------------------------------------------
    if options_menu.active:
        if not hasattr(castle, '_pre_options_shoot'):
            castle._pre_options_shoot = castle.shooting_enabled
        castle.shooting_enabled = False
    elif hasattr(castle, '_pre_options_shoot'):
        castle.shooting_enabled = castle._pre_options_shoot
        delattr(castle, '_pre_options_shoot')

    # Inform castle update logic whether rebuild progress should be paused
    castle._pause_rebuild = intro_active
    paused = intro_active or tutorial_overlay.active or pause_menu.active or options_menu.active

    # Apply time scaling only to gameplay portion
    if wave_transition['state'] in ('approach', 'focus', 'resume'):
        ms_game = int(ms * time_scale)
    else:
        ms_game = 0 if intro_active else ms

    # Castle logic should still tick during tutorial overlay so cannons can
    # move/charge while shooting remains disabled.  During paddle intro we
    # freeze all castle logic (including cannons) to avoid stray shots.
    ms_castle = ms if tutorial_overlay.active else ms_game

    dt = ms_game / (1000/60)
    now = pygame.time.get_ticks()
    # Always increment timer for any active transition state except 'idle'
    if wave_transition['state'] != 'idle':
        wave_transition['timer'] += ms

    # --- Enable shooting after tutorial overlay is dismissed ---
    if not tutorial_overlay.active and not castle.shooting_enabled:
        # Schedule enable only once
        if shoot_enable_time == 0:
            shoot_enable_time = now + 1000  # 1-second grace period
    if shoot_enable_time and now >= shoot_enable_time:
        castle.shooting_enabled = True
        shoot_enable_time = 0

    # Update castle logic only when gameplay running
    if not wave_transition['active']:
        if castle_building and hasattr(castle, '_build_anim_state') and not intro_active:
            # Advance build animation timing (drawing occurs later in the render pass).
            update_castle_build_anim(castle, ms)
            if castle._build_anim_state['done']:
                castle_building = False
        # Continue with normal game loop (castle.update) unless intro animation is active
        if not intro_active:
            new_balls = castle.update(ms_castle, score, paddles, player_wall, balls)
            if new_balls:
                balls.extend(new_balls)

    barrier_active = (now < barrier_timer)

    # --- Debris digging effect: paint brown craters/trails on the grass ---
    for d in castle.debris:
        # Skip pieces that are not diggers
        if 'dig_frames' not in d:
            continue

        # Handle optional start delay
        if d.get('dig_delay', 0) > 0:
            d['dig_delay'] -= 1
            continue  # Not yet digging

        if d['dig_frames'] > 0:
            x, y = int(d['pos'].x), int(d['pos'].y)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                brown_shade = random.choice([(101,67,33), (120,80,40), (140,90,50)])
                # --- Bouncing streaks ---
                if 'dig_bounce' not in d:
                    # Assign at creation: 10-90% of streaks bounce
                    d['dig_bounce'] = random.random() < random.uniform(0.1, 0.9)
                    d['dig_bounce_freq'] = random.uniform(0.05, 0.25)  # how often to cut out
                    d['dig_bounce_phase'] = random.uniform(0, 1)
                # --- Fading streaks ---
                if 'dig_fade' not in d:
                    # Assign at creation: 10-90% of streaks fade
                    d['dig_fade'] = random.random() < random.uniform(0.1, 0.9)
                # Calculate fade alpha
                alpha = 255
                if d['dig_fade']:
                    fade_ratio = d['dig_frames'] / max(1, d.get('dig_frames_total', d['dig_frames']))
                    alpha = int(255 * fade_ratio)
                # Calculate bounce (skip drawing if in "air")
                bounce_draw = True
                if d['dig_bounce']:
                    t = d['dig_frames'] / max(1, d.get('dig_frames_total', d['dig_frames']))
                    # Use a sine wave to simulate bouncing
                    phase = d['dig_bounce_phase']
                    freq = d['dig_bounce_freq']
                    if (math.sin(2 * math.pi * (t * freq + phase)) > 0.3):
                        bounce_draw = False
                if bounce_draw:
                    surf = BACKGROUND
                    if alpha < 255:
                        # Draw with alpha
                        streak_surf = pygame.Surface((int(4*SCALE), int(4*SCALE)), pygame.SRCALPHA)
                        pygame.draw.circle(streak_surf, brown_shade + (alpha,), (int(2*SCALE), int(2*SCALE)), int(2*SCALE))
                        surf.blit(streak_surf, (x-int(2*SCALE), y-int(2*SCALE)))
                    else:
                        pygame.draw.circle(BACKGROUND, brown_shade, (x, y), int(2 * SCALE))
            # Store total for fade
            if 'dig_frames_total' not in d:
                d['dig_frames_total'] = d['dig_frames']
            d['dig_frames'] -= 1

    # — Event handling — (capture list so the overlay can see the same events)
    events = pygame.event.get()

    # --- Handle tutorial overlay loading state ---
    prev_tut_active = getattr(tutorial_overlay, '_prev_active', tutorial_overlay.active)
    prev_loading = getattr(tutorial_overlay, '_prev_loading', False)
    
    # feed events to options menu first - consume events if options menu is active
    options_consumed_events = options_menu.update(events)
    
    # feed events to store
    store_consumed_events = False
    for event in events:
        if store.handle_event(event):
            store_consumed_events = True
            break  # store consumed the event
    
    # Only feed events to other menus if options menu didn't consume them
    if not options_consumed_events and not store_consumed_events:
        # feed events to pause menu
        pause_menu.update(events)
        
        # feed events to tutorial overlay
        tutorial_overlay.update(events)
    
    # Check if loading just started
    if not prev_loading and tutorial_overlay.loading:
        print("[DEBUG] Loading started - generating map...")
        # Trigger map generation (this might take time)
        try:
            # Force regeneration of the first castle to ensure it's fresh
            print("[DEBUG] Creating castle for wave", wave)
            new_castle, new_mask = create_castle_for_wave(wave)
            print("[DEBUG] Castle created successfully")
            
            # Replace the existing castle
            castle = new_castle
            mask = new_mask
            castle_building = False  # Don't auto-start building yet
            castle_built_once = False  # Reset so building can start after loading
            
            print("[DEBUG] Map generation complete - completing loading...")
            # Complete the loading transition
            tutorial_overlay.complete_loading()
            print("[DEBUG] Loading completed")
            
        except Exception as e:
            print(f"[DEBUG] Map generation failed: {e}")
            import traceback
            traceback.print_exc()
            # Reset to menu state on failure
            tutorial_overlay.loading = False
    
    tutorial_overlay._prev_active = tutorial_overlay.active
    tutorial_overlay._prev_loading = tutorial_overlay.loading

    # -----------------------------------------------------
    #  Recalculate paused state now that overlays processed
    # -----------------------------------------------------
    paused = intro_active or tutorial_overlay.active or pause_menu.active or options_menu.active or store.active

    # Only process game events if no menu consumed them
    if not options_consumed_events and not store_consumed_events:
        for e in events:
            if e.type==pygame.QUIT:
                running=False
            # keypresses
            if e.type==pygame.KEYDOWN or e.type==pygame.KEYUP:
                down = (e.type==pygame.KEYDOWN)
                # handle Pause toggle
                if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE:
                    pause_menu.toggle()
                    continue  # don't process further for ESC
                # spacebar to release sticky balls or bump paddles
                if e.key==pygame.K_SPACE and down:
                    now = pygame.time.get_ticks()
                    for b in balls:
                        if b.stuck_to is not None:
                            dir_vec = pygame.Vector2(WIDTH//2 - b.pos.x, HEIGHT//2 - b.pos.y)
                            if dir_vec.length_squared()==0:
                                dir_vec = pygame.Vector2(0,-1)
                            min_speed = BALL_SPEED * 0.6
                            b.vel = dir_vec.normalize() * max(BALL_SPEED, min_speed)
                            # Set fireball immunity for the paddle for 500ms
                            b.stuck_to.fireball_immunity_until = now + 500
                            b.stuck_to = None
                            b.friendly = False
                            # Set sticky cooldown for 500ms
                            b.sticky_cooldown_until = now + 500
                    # --- NEW: bump paddles physically ---
                    for p in paddles.values():
                        p.bump()
    
    # ---------------- Hearts update ----------------
    update_hearts(dt, ms_game, balls, paddles)
    
    # ---------------- Store update ----------------
    store.update(ms)
    
    # ---------------- Apply upgrade effects ----------------
    apply_upgrade_effects(store, paddles, player_wall, castle, ms)

    # — Update paddles & balls —
    if not paused:
        for p in paddles.values():
            p.move()
            p.update()
    
    # --- Update paddle input based on current key state for snappy response ---
    keys = pygame.key.get_pressed()
    space_down = keys[pygame.K_SPACE]

    # Only update direction for paddles that are currently active
    if not paused and 'top' in paddles:
        paddles['top'].dir = (-1 if keys[pygame.K_a] else (1 if keys[pygame.K_d] else 0))
    if not paused and 'bottom' in paddles:
        paddles['bottom'].dir = (-1 if keys[pygame.K_LEFT] else (1 if keys[pygame.K_RIGHT] else 0))
    if not paused and 'left' in paddles:
        paddles['left'].dir = (-1 if keys[pygame.K_w] else (1 if keys[pygame.K_s] else 0))
    if not paused and 'right' in paddles:
        paddles['right'].dir = (-1 if keys[pygame.K_UP] else (1 if keys[pygame.K_DOWN] else 0))
    
    # inform paddles of bump button state
    if not paused:
        for p in paddles.values():
            p.set_bump_pressed(space_down)
    
    # ------------------------------------------------------------------
    # Unlock new paddles based on score milestones using intro animation
    # ------------------------------------------------------------------
    def _queue_intro(side):
        # Only allow paddle intros if tutorial overlay is not active
        if (not tutorial_overlay.active and
            side not in paddles and all(i.side != side for i in intros)):
            intros.append(PaddleIntro(side, sounds, _load_sound, intro_font))
            # quick white flash
            global flash_color, flash_timer
            flash_color = (255,255,255)
            flash_timer = 200

    if score >= 30:
        _queue_intro('top')
    if score >= 100:
        _queue_intro('left')
    if score >= 200:
        _queue_intro('right')
    
    for ball in (balls[:] if not paused else []):
        ball.update(dt)
        # spawn flame trail for red balls every frame
        if ball.color == RED and not ball.is_power:
            for _ in range(random.randint(1,2)):
                vel = pygame.Vector2(random.uniform(-0.5,0.5), random.uniform(-0.5,0.5))
                col = random.choice([(255,0,0), (255,120,0), (100,100,100)])
                particles.append(Particle(ball.pos.x, ball.pos.y, vel, col, life=30))

        # piercing trail (white & purple streaks)
        if (hasattr(ball, 'pierce') and ball.pierce) or (getattr(ball, 'is_power', False) and getattr(ball, 'power_type', None) == 'pierce'):
            for _ in range(2):
                vel = pygame.Vector2(random.uniform(-1,1), random.uniform(-1,1)) * 0.3
                col = random.choice([(255,255,255), (170,0,255)])
                particles.append(Particle(ball.pos.x, ball.pos.y, vel, col, life=40))

        r = ball.rect()

        # Skip collision/physics checks for balls currently attached to paddles
        if ball.stuck_to is not None:
            continue

        # Red fireball slow-speed explosion
        if (ball.color == RED and not ball.is_power and ball.vel.length() <= BALL_SHATTER_SPEED):
            # Remove the spent fire-ball
            balls.remove(ball)
            # Screen shake and intensity
            shake_frames = 12
            shake_intensity = 12
            # Radial paddle damage
            for pd in paddles.values():
                if pygame.Vector2(pd.rect.center).distance_to(ball.pos) < 150:
                    pd.shrink()
            # Explosion particles (more, and more red/orange)
            for _ in range(75):
                ang = random.uniform(0, 360)
                spd = random.uniform(1, 3)
                vel = pygame.Vector2(spd, 0).rotate(ang)
                clr = random.choice([(255, 0, 0), (255, 80, 0), (255, 120, 0), (255, 160, 0), (255, 200, 0)])
                particles.append(Particle(ball.pos.x,ball.pos.y,vel,clr,life=40))
            # Dirt-streak debris in direction of travel
            dir_vec = ball.pos - ball.prev
            if dir_vec.length_squared() == 0:
                dir_vec = pygame.Vector2(0, -1)
            else:
                dir_vec = dir_vec.normalize()
            for _ in range(25):
                angle_var = random.uniform(-30, 30)
                speed = random.uniform(3, 7) * SCALE
                vel = dir_vec.rotate(angle_var) * speed
                brown = random.choice([(101, 67, 33), (120, 80, 40), (140, 90, 50)])
                size = int(random.randint(2, 4) * SCALE)
                deb = {
                    'pos': ball.pos.copy(),
                    'vel': vel,
                    'color': brown,
                    'size': size,
                    'friction': random.uniform(0.94, 0.985),
                    'dig_frames': random.randint(int(15 * SCALE), int(90 * SCALE))
                }
                castle.debris.append(deb)
            continue

        # Generic slow-speed explosion for any other projectile (not red fireball)
        if (ball.vel.length() <= BALL_SHATTER_SPEED and not (ball.color == RED and not ball.is_power)):
            # Capture the direction of travel (fallback upward if undefined)
            dir_vec = ball.pos - ball.prev
            if dir_vec.length_squared() == 0:
                dir_vec = pygame.Vector2(0, -1)
            else:
                dir_vec = dir_vec.normalize()

            # Remove the projectile before spawning effects
            balls.remove(ball)

            # Spawn dirt-streak debris that digs into the ground
            debris_count = 25
            for _ in range(debris_count):
                angle_var = random.uniform(-30, 30)
                speed = random.uniform(3, 7) * SCALE
                vel = dir_vec.rotate(angle_var) * speed
                brown = random.choice([(101, 67, 33), (120, 80, 40), (140, 90, 50)])
                size = int(random.randint(2, 4) * SCALE)
                deb = {
                    'pos': ball.pos.copy(),
                    'vel': vel,
                    'color': brown,
                    'size': size,
                    'friction': random.uniform(0.94, 0.985),
                    'dig_frames': random.randint(int(15 * SCALE), int(90 * SCALE))
                }
                castle.debris.append(deb)

            # Small camera shake for visual feedback
            trigger_shake(6)
            continue

        # barrier edge bounce or removal when out of bounds
        if not screen.get_rect().colliderect(r):
            if barrier_active and ball.color != RED:
                # reflect off window edges
                if r.left < 0 or r.right > WIDTH:
                    ball.vel.x *= -1
                    ball.pos.x = BALL_RADIUS if r.left < 0 else WIDTH - BALL_RADIUS
                if r.top < 0 or r.bottom > HEIGHT:
                    ball.vel.y *= -1
                    ball.pos.y = BALL_RADIUS if r.top < 0 else HEIGHT - BALL_RADIUS
                # If the ball is friendly, bouncing off the edge should make it hostile
                if hasattr(ball, 'friendly') and ball.friendly:
                    ball.friendly = False
                # small screen shake
            else:
                balls.remove(ball)
                continue

        # check collision with paddles
        for side,p in paddles.items():
            if r.colliderect(p.rect):
                # Precompute direction of incoming ball for paddle shake effect
                impact_dir = pygame.Vector2(0,0)
                if ball.vel.length_squared() > 0:
                    impact_dir = ball.vel.normalize()

                # Sticky capture before anything else
                now = pygame.time.get_ticks()
                if (power_timers.get(side, [None,0])[0]=='sticky' and not ball.is_power
                    and now >= getattr(ball, 'sticky_cooldown_until', 0)):
                    ball.stuck_to = p
                    if p.side in ('top','bottom'):
                        ball.stuck_offset.x = ball.pos.x - p.rect.centerx
                        ball.stuck_offset.y = 0
                    else:
                        ball.stuck_offset.y = ball.pos.y - p.rect.centery
                        ball.stuck_offset.x = 0
                    # zero velocity while stuck
                    ball.vel.xy = (0,0)
                    # Do not continue to other collision handling
                    # apply small paddle shake
                    p.offset += impact_dir * 4
                    break
                if ball.is_power:
                    # apply powerup and consume the ball
                    if ball.power_type == 'barrier':
                        barrier_timer = now + POWER_DURATION
                    else:
                        # If a new potion is picked up, and the previous was widen, restore width
                        prev = power_timers.get(side, [None,0])[0]
                        if prev == 'widen' and ball.power_type != 'widen':
                            paddles[side].clear_widen()
                        power_timers[side] = [ball.power_type, now+POWER_DURATION]
                    ptype = ball.power_type
                    if ptype == 'widen':
                        paddles[side].enlarge()
                    # screen flash setup
                    flash_color = POTION_COLORS.get(ptype, (255,255,0))
                    flash_timer = FLASH_DURATION
                    # Play powerup pickup sound
                    if 'powerup' in sounds:
                        sounds['powerup'].play()
                    balls.remove(ball)
                elif ball.color == RED:
                    # Handle bounce (red or white non-power ball)
                    damage_paddle = (ball.color == RED)
                    if damage_paddle:
                        # Check for fireball immunity
                        if not hasattr(p, 'fireball_immunity_until') or now >= getattr(p, 'fireball_immunity_until', 0):
                            if power_timers.get(side, [None,0])[0] != 'widen':
                                old_width = p.width
                                p.shrink()
                                # Play paddle damage sound for fireball
                                if 'paddle_damage' in sounds:
                                    sounds['paddle_damage'].play()
                                # screen shake intensity based on remaining width
                                ratio = 1 - (p.width / p.base_len)
                                shake_intensity = int(2 + 8 * ratio)
                                shake_frames = 8
                                # wood debris particles at paddle ends
                                debris_color = (160,82,45)
                                ends = [p.rect.topleft, p.rect.topright, p.rect.bottomleft, p.rect.bottomright]
                                for ex,ey in ends:
                                    for _ in range(3):
                                        vel = pygame.Vector2(random.uniform(-1,1), random.uniform(-1,1))
                                        particles.append(Particle(ex, ey, vel, debris_color, life=20))
                    # Grow paddle if widen is active
                    if power_timers.get(side, [None,0])[0] == 'widen':
                        p.grow_on_hit()
                    # Reflect off paddle rectangle then add spin & curved redirection
                    curved_paddle_reflect(ball, p)
                    # Apply 2D collision physics
                    paddle_ball_collision_2d(ball, p)
                    # Play paddle hit sound (for red fireball)
                    if 'paddle_hit' in sounds:
                        sounds['paddle_hit'].play()
                    p.offset += impact_dir * 4

                    # Cap speed
                    speed = ball.vel.length()
                    if speed > BALL_SPEED:
                        ball.vel = ball.vel.normalize() * BALL_SPEED

                    # Slight nudge to avoid instant re-collision
                    ball.pos += ball.vel * 0.1

                    # If paddle has pierce power, convert this ball
                    if power_timers.get(side, [None,0])[0] == 'pierce':
                        ball.pierce = True
                        ball.color = (170,0,255)

                    # Check for shatter due to low speed
                    if ball.vel.length() <= BALL_SHATTER_SPEED:
                        balls.remove(ball)
                        if ball.color == RED:
                            # Enhanced explosion: more particles, plus dirt streaks
                            for _ in range(75):
                                ang = random.uniform(0, 360)
                                spd = random.uniform(2, 5)
                                vel = pygame.Vector2(spd, 0).rotate(ang)
                                color = random.choice([(255,0,0),(255,80,0),(255,120,0),(255,160,0),(255,200,0)])
                                particles.append(Particle(ball.pos.x,ball.pos.y,vel,color,30))
                            # Dirt-streak debris in direction of travel
                            dir_vec = ball.pos - ball.prev
                            if dir_vec.length_squared() == 0:
                                dir_vec = pygame.Vector2(0, -1)
                            else:
                                dir_vec = dir_vec.normalize()
                            for _ in range(25):
                                angle_var = random.uniform(-30, 30)
                                speed = random.uniform(3, 7) * SCALE
                                vel = dir_vec.rotate(angle_var) * speed
                                brown = random.choice([(101, 67, 33), (120, 80, 40), (140, 90, 50)])
                                size = int(random.randint(2, 4) * SCALE)
                                deb = {
                                    'pos': ball.pos.copy(),
                                    'vel': vel,
                                    'color': brown,
                                    'size': size,
                                    'friction': random.uniform(0.94, 0.985),
                                    'dig_frames': random.randint(int(15 * SCALE), int(90 * SCALE))
                                }
                                castle.debris.append(deb)
                            break
                else:
                    # Grow paddle if widen is active
                    if power_timers.get(side, [None,0])[0] == 'widen':
                        p.grow_on_hit()
                    # white ball bounce with reflect, spin and curved redirection
                    curved_paddle_reflect(ball, p)
                    # Apply 2D collision physics
                    paddle_ball_collision_2d(ball, p)
                    # Play paddle hit sound (for white cannonball, not potions)
                    if 'paddle_hit' in sounds and not ball.is_power:
                        sounds['paddle_hit'].play()
                    p.offset += impact_dir * 4

                    ball.pos += ball.vel * 0.1

                    # if paddle has through power, convert ball
                    if power_timers.get(side, [None,0])[0] == 'through':
                        # Randomize into potion or fireball
                        if random.random() < 0.35:
                            # Turn into a red fireball
                            ball.is_power = False
                            ball.color = RED
                        else:
                            ball.is_power = True
                            ball.power_type = random.choice(['widen','sticky','barrier'])
                            ball.color = YELLOW
                    elif power_timers.get(side, [None,0])[0] == 'pierce':
                        ball.pierce = True
                        ball.color = (170,0,255)
                    # (Removed friendly-fire guard – cannonballs always damage player castle)
                break
        else:
            # ---------------------------------------------------
            # No collision with paddles – check player wall
            # ---------------------------------------------------
            hit_wall = False
            for b in player_wall.blocks[:]:
                if not r.colliderect(b):
                    continue

                incoming_dir = ball.vel.normalize() if ball.vel.length_squared()!=0 else pygame.Vector2(0,-1)

                # Only pierce potion breaks through player wall
                if ball.is_power:
                    if ball.power_type == 'pierce':
                        player_wall.shatter_block(b, incoming_dir, castle.debris)
                        if 'wall_break' in sounds: sounds['wall_break'].play()
                        trigger_shake(8)
                        hit_wall = True
                        break
                    else:
                        balls.remove(ball)
                        # Get potion color for shatter effect
                        potion_col = POTION_COLORS.get(ball.power_type, (255,255,0))
                        # White glass particles
                        for _ in range(6):
                            ang=random.uniform(0,360); spd=random.uniform(1,3)
                            vel=pygame.Vector2(spd,0).rotate(ang)
                            particles.append(Particle(ball.pos.x,ball.pos.y,vel,(220,220,255),life=25))
                        # Potion color particles
                        for _ in range(3):
                            ang=random.uniform(0,360); spd=random.uniform(1,2.5)
                            vel=pygame.Vector2(spd,0).rotate(ang)
                            particles.append(Particle(ball.pos.x,ball.pos.y,vel,potion_col,life=25))
                        hit_wall = True
                        break

                # piercing projectiles
                if getattr(ball,'pierce',False):
                    player_wall.shatter_block(b, incoming_dir, castle.debris)
                    if 'wall_break' in sounds: sounds['wall_break'].play()
                    trigger_shake(8)
                    hit_wall = True
                    break

                # Standard white cannonball – shatter & bounce
                if ball.color == WHITE and not ball.is_power:
                    player_wall.shatter_block(b, incoming_dir, castle.debris)
                    if 'wall_break' in sounds: sounds['wall_break'].play()
                    trigger_shake(4)
                    # SHATTER: Remove the ball and spawn shatter particles instead of bouncing
                    balls.remove(ball)
                    for _ in range(12):
                        ang = random.uniform(0, 360)
                        spd = random.uniform(1, 2.5)
                        vel = pygame.Vector2(spd, 0).rotate(ang)
                        color = random.choice([(140,140,140), (220,220,220), (80,80,80)])
                        particles.append(Particle(ball.pos.x, ball.pos.y, vel, color, life=22))
                    hit_wall = True
                    break

                # Fireball
                if ball.color == RED:
                    player_wall.shatter_block(b, incoming_dir, castle.debris)
                    if 'wall_break' in sounds: sounds['wall_break'].play()
                    trigger_shake(8)
                    ball.blocks_hit += 1
                    if ball.blocks_hit >= 2:
                        balls.remove(ball)
                        # Enhanced explosion: more particles, plus dirt streaks
                        for _ in range(75):
                            ang = random.uniform(0, 360)
                            spd = random.uniform(2, 5)
                            vel = pygame.Vector2(spd, 0).rotate(ang)
                            color = random.choice([(255,0,0),(255,80,0),(255,120,0),(255,160,0),(255,200,0)])
                            particles.append(Particle(ball.pos.x,ball.pos.y,vel,color,30))
                        # Dirt-streak debris in direction of travel
                        dir_vec = ball.pos - ball.prev
                        if dir_vec.length_squared() == 0:
                            dir_vec = pygame.Vector2(0, -1)
                        else:
                            dir_vec = dir_vec.normalize()
                        for _ in range(25):
                            angle_var = random.uniform(-30, 30)
                            speed = random.uniform(3, 7) * SCALE
                            vel = dir_vec.rotate(angle_var) * speed
                            brown = random.choice([(101, 67, 33), (120, 80, 40), (140, 90, 50)])
                            size = int(random.randint(2, 4) * SCALE)
                            deb = {
                                'pos': ball.pos.copy(),
                                'vel': vel,
                                'color': brown,
                                'size': size,
                                'friction': random.uniform(0.94, 0.985),
                                'dig_frames': random.randint(int(15 * SCALE), int(90 * SCALE))
                            }
                            castle.debris.append(deb)
                        break
                    else:
                        ball.pos += ball.vel*0.1
                    hit_wall = True
                    break

                # Default bounce
                reflect(ball, b)
                ball.pos += ball.vel*0.1
                hit_wall = True
                break

            if hit_wall:
                continue  # handled, next ball

            # ---------------------------------------------------
            # No collision with player wall – continue with castle
            # ---------------------------------------------------
            for b in castle.blocks[:]:
                if not r.colliderect(b):
                    continue

                # Skip friendly balls – they pass through castle until first bounce
                if getattr(ball, 'friendly', False):
                    continue

                incoming_dir = ball.vel.normalize() if ball.vel.length_squared()!=0 else pygame.Vector2(0,-1)

                if ball.is_power and ball.power_type == 'through':
                    castle.shatter_block(b, incoming_dir)
                    score += 10
                    # Play wall break sound
                    if 'wall_break' in sounds:
                        sounds['wall_break'].play()
                    trigger_shake(4)
                    # ball continues without bouncing
                    break

                if hasattr(ball, 'pierce') and ball.pierce:
                    castle.shatter_block(b, incoming_dir)
                    score += 10
                    # Play wall break sound
                    if 'wall_break' in sounds:
                        sounds['wall_break'].play()
                    trigger_shake(8)
                    break

                # White cannonball – shatter and bounce
                if ball.color == WHITE and not ball.is_power:
                    # --- Crack impact calculation ---
                    # Impact point: closest point on block to ball center
                    impact_x = max(b.left, min(ball.pos.x, b.right))
                    impact_y = max(b.top, min(ball.pos.y, b.bottom))
                    impact_point = (int(impact_x), int(impact_y))
                    # Angle: angle of incoming velocity (radians)
                    impact_angle = math.atan2(incoming_dir.y, incoming_dir.x)
                    castle.hit_block(b, impact_point=impact_point, impact_angle=impact_angle)
                    score += 10
                    # Play wall break sound
                    if 'wall_break' in sounds:
                        sounds['wall_break'].play()
                    trigger_shake(4)
                    reflect(ball, b)
                    ball.pos += ball.vel * 0.1
                    # slight speed-up cap as per castle logic
                    if ball.vel.length() < BALL_SPEED * 1.5:
                        ball.vel *= 1.05
                    break

                # Red ball logic – break up to 2 blocks then explode
                if ball.color == RED:
                    castle.shatter_block(b, incoming_dir)
                    score += 10
                    # Play wall break sound
                    if 'wall_break' in sounds:
                        sounds['wall_break'].play()
                    trigger_shake(8)
                    ball.blocks_hit += 1
                    if ball.blocks_hit >= 2:
                        balls.remove(ball)
                        # Enhanced explosion: more particles, plus dirt streaks
                        for _ in range(75):
                            ang = random.uniform(0, 360)
                            spd = random.uniform(2, 5)
                            vel = pygame.Vector2(spd, 0).rotate(ang)
                            color = random.choice([(255,0,0),(255,80,0),(255,120,0),(255,160,0),(255,200,0)])
                            particles.append(Particle(ball.pos.x,ball.pos.y,vel,color,30))
                        # Dirt-streak debris in direction of travel
                        dir_vec = ball.pos - ball.prev
                        if dir_vec.length_squared() == 0:
                            dir_vec = pygame.Vector2(0, -1)
                        else:
                            dir_vec = dir_vec.normalize()
                        for _ in range(25):
                            angle_var = random.uniform(-30, 30)
                            speed = random.uniform(3, 7) * SCALE
                            vel = dir_vec.rotate(angle_var) * speed
                            brown = random.choice([(101, 67, 33), (120, 80, 40), (140, 90, 50)])
                            size = int(random.randint(2, 4) * SCALE)
                            deb = {
                                'pos': ball.pos.copy(),
                                'vel': vel,
                                'color': brown,
                                'size': size,
                                'friction': random.uniform(0.94, 0.985),
                                'dig_frames': random.randint(int(15 * SCALE), int(90 * SCALE))
                            }
                            castle.debris.append(deb)
                        break
                    else:
                        ball.pos += ball.vel * 0.1
                        break

                # Potions shatter harmlessly on the wall
                if ball.is_power:
                    balls.remove(ball)
                    # Get potion color for shatter effect
                    potion_col = POTION_COLORS.get(ball.power_type, (255,255,0))
                    # White glass particles
                    for _ in range(6):
                        ang = random.uniform(0, 360)
                        spd = random.uniform(1, 3)
                        vel = pygame.Vector2(spd, 0).rotate(ang)
                        particles.append(Particle(ball.pos.x, ball.pos.y, vel, (220,220,255), life=25))
                    # Potion color particles
                    for _ in range(3):
                        ang = random.uniform(0, 360)
                        spd = random.uniform(1, 2.5)
                        vel = pygame.Vector2(spd, 0).rotate(ang)
                        particles.append(Particle(ball.pos.x, ball.pos.y, vel, potion_col, life=25))
                    break

                # Other balls just bounce
                reflect(ball, b)
                ball.pos += ball.vel * 0.1
                break  # handled collision; exit wall loop

    # update particles
    for part in particles[:]:
        part.update()
        if part.life <= 0:
            particles.remove(part)

    # expire powerups
    for side, (ptype, exp) in list(power_timers.items()):
        if now >= exp:
            if ptype=='widen':
                paddles[side].widen()  # Only decrement stack on natural expiry
            # sticky / through just expire naturally
            del power_timers[side]

    # — Draw everything onto off-screen surface —
    scene_surf.blit(WHITE_BG, (0,0))
    scene_surf.blit(BACKGROUND, (0,0))
    castle.draw(scene_surf)
    # Overlay build animation (scaling bricks, sprouting turrets) if active
    if castle_building and hasattr(castle, '_build_anim_state'):
        draw_castle_build_anim(castle, scene_surf)
    # Draw persistent player wall underneath castle visuals
    player_wall.draw(scene_surf)
    for side,p in paddles.items():
        col = None
        if side in power_timers:
            col = POTION_COLORS.get(power_timers[side][0])
            # Flicker logic for widen
            if power_timers[side][0] == 'widen':
                time_left = power_timers[side][1] - now
                p.flicker = time_left <= 2000
            else:
                p.flicker = False
        else:
            p.flicker = False
        p.draw(scene_surf, overlay_color=col)
    for ball in balls: ball.draw(scene_surf, small_font)
    for part in particles:
        part.draw(scene_surf)

    # Draw hearts after castle so they appear on top of walls but under HUD
    draw_hearts(scene_surf)
    
    # Update and draw coins
    update_coins(dt, ms, balls)
    draw_coins(scene_surf)

    # Display score and current number of persistent debris pieces
    # --- HUD: Score and Coins at Top Center ---
    coins_text = str(get_coin_count())
    hud_text = f"{score}"
    score_surf = small_font.render(hud_text, True, (0,0,0))
    coin_surf = small_font.render(coins_text, True, (255,215,0))
    # simple 8-bit coin icon (yellow circle)
    coin_icon = pygame.Surface((12,12), pygame.SRCALPHA)
    pygame.draw.circle(coin_icon, (255,215,0), (6,6), 6)
    # compute layout – centered at top
    total_w = score_surf.get_width() + 8 + coin_icon.get_width() + coin_surf.get_width() + 10
    base_x = WIDTH//2 - total_w//2
    y = 12  # Top margin
    scene_surf.blit(score_surf, (base_x, y))
    x = base_x + score_surf.get_width() + 8
    scene_surf.blit(coin_icon, (x, y+score_surf.get_height()//2 - 6))
    x += coin_icon.get_width() + 2
    scene_surf.blit(coin_surf, (x, y))

    # Power status bars
    bar_y = 40
    bar_h = 6
    for idx,(side,(ptype, expiry)) in enumerate(power_timers.items()):
        ratio = max(0, (expiry-now)/POWER_DURATION)
        bar_w = 100
        x = 10 + idx*(bar_w+10)
        pygame.draw.rect(scene_surf, (80,80,80), (x, bar_y, bar_w, bar_h))
        clr = POTION_COLORS.get(ptype, (255,255,0))
        pygame.draw.rect(scene_surf, clr, (x, bar_y, int(bar_w*ratio), bar_h))
        label = small_font.render(ptype[0].upper(), True, clr)
        scene_surf.blit(label, (x+bar_w//2-4, bar_y-12))

    # FPS display (if enabled in options)
    if options_menu.get_setting('show_fps', False):
        fps_text = f"FPS: {int(clock.get_fps())}"
        fps_surf = small_font.render(fps_text, True, (255, 255, 255))
        scene_surf.blit(fps_surf, (WIDTH - fps_surf.get_width() - 10, 10))

    # Screen shake offset
    offset_x = offset_y = 0
    if shake_frames > 0 and options_menu.get_setting('screen_shake', True):
        # Ensure shake_intensity is always positive
        intensity = abs(shake_intensity)
        offset_x = random.randint(-intensity, intensity)
        offset_y = random.randint(-intensity, intensity)
        shake_frames -= 1
    elif shake_frames > 0:
        # If screen shake is disabled, just decrement frames without applying offset
        shake_frames -= 1

    # Skip regular blit if we are in wave-transition zoom mode
    if wave_transition['state'] == 'idle':
        screen.blit(scene_surf, (offset_x, offset_y))

    # draw / update paddle intro animations on top of scene
    for intro in intros[:]:
        # EDGE CASE FIX: Ensure consistent timing and prevent zero delta time
        ms_clamped = max(1, min(ms, 100))  # Minimum 1ms, maximum 100ms
        if intro.update(ms_clamped):
            # intro finished – activate paddle
            paddles[intro.side] = Paddle(intro.side)
            intros.remove(intro)
        intro.draw(screen)

    # ---------------- Wave announcement text ----------------
    if wave_text_time > 0 and wave_text and wave_transition['state']=='idle':
        t_ratio = max(0.0, wave_text_time / 3000)
        scale   = 1.0 + 0.2 * (1 - t_ratio)  # small zoom-out effect
        text_surf = wave_font.render(wave_text, True, (60, 0, 130))
        w,h = text_surf.get_size()
        text_surf = pygame.transform.scale(text_surf, (int(w*scale), int(h*scale)))
        text_rect = text_surf.get_rect(center=(WIDTH//2, HEIGHT//3))
        
        # Special animated banner for every wave
        banner_height = text_rect.height + 18
        t = 1.0 - (wave_text_time / 3000)
        # Banner sweeps in, holds, then sweeps out
        if t < 0.2:  # sweep in
            sweep_t = t / 0.2
            banner_x = -WIDTH + sweep_t * WIDTH
        elif t > 0.8:  # sweep out
            sweep_t = (t - 0.8) / 0.2
            banner_x = sweep_t * WIDTH
        else:  # hold
            banner_x = 0
        banner_rect = pygame.Rect(int(banner_x), text_rect.centery - banner_height//2, WIDTH, banner_height)
        banner_surf = pygame.Surface((banner_rect.width, banner_rect.height), pygame.SRCALPHA)
        banner_surf.fill((255,255,255,230))
        screen.blit(banner_surf, banner_rect)
        # --- Sparks and smoke effect at the start of every wave banner ---
        if abs(t-0.2) < 0.03 and not wave_banner_sparks and not wave_banner_smoke:
            # Only spawn once per banner
            num_sparks = 24
            num_smoke = 18
            for i in range(num_sparks):
                angle = random.uniform(-0.4, 0.4)  # mostly upward
                speed = random.uniform(4.0, 7.0)
                vel = pygame.Vector2(math.sin(angle), -math.cos(angle)) * speed
                color = random.choice([
                    (255, 255, 120), (255, 200, 80), (255, 255, 255), (255, 180, 60)
                ])
                size = random.randint(2, 4)
                pos = pygame.Vector2(WIDTH//2 + random.randint(-60, 60), banner_rect.bottom-8)
                wave_banner_sparks.append(Particle(pos.x, pos.y, vel, color, life=28, size=size, fade=True))
            for i in range(num_smoke):
                angle = random.uniform(-0.25, 0.25)
                speed = random.uniform(1.5, 2.8)
                vel = pygame.Vector2(math.sin(angle), -math.cos(angle)) * speed
                gray = random.randint(80, 140)
                color = (gray, gray, gray)
                size = random.randint(6, 12)
                pos = pygame.Vector2(WIDTH//2 + random.randint(-70, 70), banner_rect.bottom-4)
                wave_banner_smoke.append(Particle(pos.x, pos.y, vel, color, life=38, size=size, fade=True))
        # Draw sparks and smoke if present
        for p in wave_banner_sparks[:]:
            p.update()
            p.draw(screen)
            if p.life <= 0:
                wave_banner_sparks.remove(p)
        for p in wave_banner_smoke[:]:
            p.update()
            p.draw(screen)
            if p.life <= 0:
                wave_banner_smoke.remove(p)
        screen.blit(text_surf, text_rect)
        wave_text_time -= ms

        # When the banner is gone, clear any remaining particles
        if wave_text_time <= 0:
            wave_banner_sparks.clear()
            wave_banner_smoke.clear()

    # flash effect overlay
    if flash_timer > 0 and flash_color:
        alpha = int(120 * (flash_timer/FLASH_DURATION))
        flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash_surf.fill((*flash_color, alpha))
        screen.blit(flash_surf, (0,0))
        flash_timer -= ms

    # Magical barrier visual when active
    if barrier_active:
        border_col = (0,255,255)
        thickness = 4
        pygame.draw.rect(screen, border_col, (0,0,WIDTH,HEIGHT), thickness)

    if not wave_transition['active']:
        # Draw tutorial overlay last so it sits atop the scene
        tutorial_overlay.draw(screen)
        # Draw pause menu on top of everything else
        pause_menu.draw(screen)
        # Draw options menu on top of everything else
        options_menu.draw(screen)
        # Draw store on top of everything else
        store.draw(screen)
        pygame.display.flip()

    # ---------------------------------------------------------
    # TRANSITION STATE CHANGES
    # ---------------------------------------------------------
    # 1) Start APPROACH when only one block remains and no transition running
    if len(castle.blocks) == 1 and wave_transition['state'] == 'idle':
        last_block = castle.blocks[0]
        # Check if any ball is reasonably close and moving toward last block
        initiate = False
        for ball in balls:
            vec_to_block = pygame.Vector2(last_block.center) - ball.pos
            # within 200 px and heading toward block
            if vec_to_block.length_squared() < 200**2 and ball.vel.length_squared() > 0:
                if ball.vel.dot(vec_to_block) > 0:  # same general direction
                    initiate = True
                    break
        if initiate:
            wave_transition.update({
                'active': True,
                'state': 'approach',
                'timer': 0,
                'block_pos': (last_block.centerx, last_block.centery),
            })

    # --- Graceful exit from APPROACH when balls leave proximity ---
    if wave_transition['state'] == 'approach':
        if wave_transition['closeness'] < 0.02:
            wave_transition['no_close'] += ms
            # If no ball close for > 1 s, end approach smoothly
            if wave_transition['no_close'] > 1000:
                wave_transition.update({'state':'idle','active':False,'timer':0})
                wave_transition['closeness'] = 0.0
                wave_transition['no_close'] = 0
        else:
            wave_transition['no_close'] = 0

    # 2) Switch to PRE_STORE_DELAY the moment the last block is destroyed
    if len(castle.blocks) == 0 and wave_transition['state'] == 'approach':
        wave_transition.update({
            'state': 'pre_store_delay',
            'timer': 0,
        })

    # 3) Wait in slow-mo for a moment before fade
    if wave_transition['state'] == 'pre_store_delay':
        if wave_transition['timer'] >= wave_transition['duration_pre_store_delay']:
            wave_transition.update({'state': 'fade_to_store', 'timer': 0})

    # 4) Fade to black before store
    if wave_transition['state'] == 'fade_to_store':
        alpha = min(255, int(255 * wave_transition['timer'] / wave_transition['duration_fade_to_store']))
        wave_transition['fade_alpha'] = alpha
        if wave_transition['timer'] >= wave_transition['duration_fade_to_store']:
            wave_transition.update({'state': 'store_fade_in', 'timer': 0, 'fade_alpha': 255})
            wave_transition['store_opened'] = False  # Reset before store_fade_in

    # 5) Fade in the store (from black)
    if wave_transition['state'] == 'store_fade_in':
        # Open the store exactly once at the start of this state
        if not wave_transition.get('store_opened', False):
            store.open_store(wave)
            wave_transition['store_opened'] = True
        alpha = max(0, 255 - int(255 * wave_transition['timer'] / wave_transition['duration_store_fade_in']))
        wave_transition['fade_alpha'] = alpha
        if wave_transition['timer'] >= wave_transition['duration_store_fade_in']:
            wave_transition.update({'state': 'focus', 'timer': 0, 'fade_alpha': 0, 'store_opened': False})

    # 6) When store closes, start fade out
    if wave_transition['state'] == 'focus' and not store.active:
        wave_transition.update({'state': 'store_fade_out', 'timer': 0, 'fade_alpha': 0})

    # 7) Fade out to black after store
    if wave_transition['state'] == 'store_fade_out':
        alpha = min(255, int(255 * wave_transition['timer'] / wave_transition['duration_store_fade_out']))
        wave_transition['fade_alpha'] = alpha
        if wave_transition['timer'] >= wave_transition['duration_store_fade_out']:
            wave_transition.update({'state': 'resume_fade_in', 'timer': 0, 'fade_alpha': 255})
            # Prepare next wave here
            if wave_transition.get('next_castle') is None:
                next_wave = wave + 1
                next_mask_w, next_mask_h = get_wave_mask_size(next_wave)
                min_blocks = 4 if next_wave == 1 else 6
                next_castle, next_mask = create_castle_for_wave(next_wave)
                chosen_music = MUSIC_PATH
                if next_wave >= 2 and WAVE_MUSIC_FILES:
                    import random
                    chosen_music = random.choice(WAVE_MUSIC_FILES)
                wave_transition['next_castle'] = next_castle
                wave_transition['next_music'] = chosen_music

    # 8) Fade back in to the game
    if wave_transition['state'] == 'resume_fade_in':
        alpha = max(0, 255 - int(255 * wave_transition['timer'] / wave_transition['duration_resume_fade_in']))
        wave_transition['fade_alpha'] = alpha
        if wave_transition['timer'] >= wave_transition['duration_resume_fade_in']:
            wave_transition.update({'state': 'resume', 'timer': 0, 'fade_alpha': 0})

    # 9) After resume, start next wave as before
    if wave_transition['state'] == 'resume' and wave_transition['timer'] >= wave_transition['duration_resume']:
        if wave_transition.get('next_castle') is not None:
            wave += 1
            castle = wave_transition['next_castle']
            if hasattr(castle, '_build_anim_state'):
                castle_building = True
            balls.clear()
            clear_coins()  # Clear coins from previous wave
            for p in paddles.values():
                p.widen()
            power_timers.clear()
            wave_text = f"WAVE {wave}!"
            wave_text_time = 3000
            if wave_transition.get('next_music'):
                try:
                    pygame.mixer.music.load(wave_transition['next_music'])
                    pygame.mixer.music.set_volume(0.6)
                    pygame.mixer.music.play(-1)
                except Exception as e:
                    print(f"[Audio] Failed to load wave music: {e}")
        wave_transition.update({
            'state': 'idle',
            'active': False,
            'timer': 0,
            'next_castle': None,
            'next_music': None,
        })

    # -----------------------------------------------------------
    # BACKGROUND MUSIC MANAGEMENT
    # -----------------------------------------------------------
    if tutorial_overlay.active:
        now_time = pygame.time.get_ticks()
        if _tut_pause_until:
            # Currently in the silence gap – when time elapses restart music
            if now_time >= _tut_pause_until:
                pygame.mixer.music.play(-1, 0.0)
                last_tut_restart = now_time
                _tut_pause_until = 0
        else:
            # Check if it's time to stop and begin the silent gap
            if now_time - last_tut_restart >= TUT_LOOP_MS:
                pygame.mixer.music.stop()
                _tut_pause_until = now_time + TUT_SILENCE_MS
    elif tutorial_looping:
        # Player exited tutorial – if we were in gap make sure music resumes
        if not pygame.mixer.music.get_busy():
            pygame.mixer.music.play(-1, 0.0)
        tutorial_looping = False
        _tut_pause_until = 0
    else:
        # --- NEW: If music ends during a wave, pick a new random song (not the same as last) ---
        if wave >= 2 and WAVE_MUSIC_FILES and not pygame.mixer.music.get_busy():
            import random
            available = [f for f in WAVE_MUSIC_FILES if f != last_wave_music]
            if not available:
                available = WAVE_MUSIC_FILES  # fallback if all are the same
            chosen = random.choice(available)
            try:
                pygame.mixer.music.load(chosen)
                pygame.mixer.music.set_volume(0.6)
                pygame.mixer.music.play(-1)
                last_wave_music = chosen
            except Exception as e:
                print(f"[Audio] Failed to load wave music: {e}")
    # --------------------------------------------------------------------

    # restart music after scheduled fade-out once the timer has elapsed
    if music_restart_time and pygame.time.get_ticks() >= music_restart_time:
        # If we're on wave 2 or higher, pick a random available music file
        if wave >= 2 and WAVE_MUSIC_FILES:
            import random
            chosen_music = random.choice(WAVE_MUSIC_FILES)
            try:
                pygame.mixer.music.load(chosen_music)
                pygame.mixer.music.set_volume(0.6)
                pygame.mixer.music.play(-1)
            except Exception as e:
                print(f"[Audio] Failed to load wave music: {e}")
        else:
            pygame.mixer.music.play(-1)  # restart immediately, looping
        music_restart_time = 0

    # — Check lose conditions —
    if len(player_wall.blocks) == 0 and not paused:
        # Play dramatic slide-down SFX the moment the wall is destroyed
        if not game_over_sfx_played and 'game_over_slide' in sounds:
            sounds['game_over_slide'].play()
            game_over_sfx_played = True
        # Trigger fancy end screen then exit main loop
        final_score = score
        game_over_result = run_game_over(screen, final_score, WIDTH, HEIGHT)

        # --- Restart game state ---
        # Reset all game variables to initial state
        wave          = 1
        castle_dim_x  = 5
        castle_dim_y  = 5
        mask_w, mask_h = get_wave_mask_size(wave)
        min_blocks = 4 if wave == 1 else 6
        mask = generate_mask_for_difficulty(mask_w, mask_h, get_wave_difficulty(wave), min_wall_blocks=min_blocks)
        castle, mask = create_castle_for_wave(wave)
        # Disable cannon fire until the tutorial overlay is dismissed after restart
        castle.shooting_enabled = False
        player_wall   = PlayerWall()
        paddles = {
            'bottom': Paddle('bottom')
        }
        balls        = []
        score        = 0
        particles    = []
        # Reset coin and store state
        clear_coins()
        store.close_store()
        reset_upgrade_states()
        # Update game state references after restart
        store.set_game_state(paddles, player_wall, castle)
        shake_frames = 0
        shake_intensity = 0
        flash_color = None
        flash_timer = 0
        power_timers = {}
        barrier_timer = 0
        shoot_enable_time = 0
        wave_font      = pygame.font.SysFont(None, 72, italic=True)
        wave_text      = ""
        wave_text_time = 0
        intro_font = pygame.font.SysFont(None, 48, italic=True)
        intros = []
        game_over_sfx_played = False
        music_restart_time = 0
        # --- Reset tutorial music state ---
        tutorial_looping = True
        _tut_pause_until = 0
        last_tut_restart = pygame.time.get_ticks()
        try:
            pygame.mixer.music.load(MUSIC_PATH)
            pygame.mixer.music.set_volume(0.6)
            # Playback will start in the title screen overlay
        except Exception as e:
            print(f"[Audio] Failed to reload tutorial music: {e}")
        # Only show main menu if ESCAPE was pressed
        if game_over_result == 'main_menu':
            tutorial_overlay = TutorialOverlay()
            # Clear all debris and reset background
            castle.debris.clear()
            # Regenerate clean background
            BACKGROUND = generate_grass(WIDTH, HEIGHT)
        else:
            tutorial_overlay.active = False
        
        # Re-apply options settings after restart
        options_menu._apply_settings()
        # Continue the main loop after restart
        continue

    # Legacy paddle–based lose condition retained (secondary)
    if paddles and all(p.width < 20 for p in paddles.values()):
        print("All paddles gone. Game over.")
        running=False

    # --- Drawing ---
    if wave_transition['state']=='idle':
        screen.blit(scene_surf, (offset_x, offset_y))
    else:
        # --- Zoom-in/out effect based on transition state ---
        st = wave_transition['state']
        if st == 'approach':
            closeness = wave_transition.get('closeness', 0.0)
            zoom = 1.0 + (wave_transition['zoom_target'] - 1.0) * closeness
        elif st == 'focus':
            zoom = wave_transition['zoom_target']
        else:  # resume
            prog = min(1.0, wave_transition['timer'] / wave_transition['duration_resume'])
            # ease-out quad for smooth out
            zoom = wave_transition['zoom_target'] - (wave_transition['zoom_target'] - 1.0) * (prog * (2 - prog))
        # --- Apply slow-motion to particles and debris ---
        SLOW_SCALE = time_scale
        for part in particles[:]:
            # Temporarily scale velocity for slow motion
            orig_vel = part.vel.copy()
            part.vel = part.vel * SLOW_SCALE
            part.update()
            part.vel = orig_vel
            if part.life <= 0:
                particles.remove(part)
        for d in castle.debris:
            d['pos'] += d['vel'] * SLOW_SCALE
            d['vel'] *= d.get('friction', 0.985)
            if d.get('size',1) <= 0:
                castle.debris.remove(d)
        # Center on last block – but clamp so we never reveal whitespace
        bx, by = wave_transition['block_pos']
        # Calculate blit rect
        surf_w, surf_h = scene_surf.get_size()
        zoomed_w = int(surf_w * zoom)
        zoomed_h = int(surf_h * zoom)
        zoomed_surf = pygame.transform.smoothscale(scene_surf, (zoomed_w, zoomed_h))

        # Desired top-left offset that would put block at screen center
        offset_x = WIDTH // 2 - int(bx * zoom)
        offset_y = HEIGHT // 2 - int(by * zoom)
        # --- Clamp offsets so the zoomed surface fully covers the screen ---
        offset_x = max(min(offset_x, 0), WIDTH  - zoomed_w)
        offset_y = max(min(offset_y, 0), HEIGHT - zoomed_h)

        screen.fill((255,255,255))  # fills behind – should be hidden after clamping
        screen.blit(zoomed_surf, (offset_x, offset_y))

        # Draw overlays (store, pause menu, tutorial) during focus so the armory appears
        if st == 'focus':
            tutorial_overlay.draw(screen)
            pause_menu.draw(screen)
            options_menu.draw(screen)
            store.draw(screen)

        pygame.display.flip()

    # After tutorial overlay is dismissed, start first castle build if not already started
    if not tutorial_overlay.active and not castle_built_once and not tutorial_overlay.loading:
        print("[DEBUG] Starting castle build animation")
        castle_building = True
        castle_built_once = True

    # --- Fade overlay for store/game transitions ---
    if wave_transition['state'] in ('fade_to_store', 'store_fade_in', 'store_fade_out', 'resume_fade_in'):
        fade_alpha = wave_transition.get('fade_alpha', 0)
        if fade_alpha > 0:
            fade_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade_surf.fill((0, 0, 0, fade_alpha))
            screen.blit(fade_surf, (0, 0))

pygame.quit()
sys.exit()
