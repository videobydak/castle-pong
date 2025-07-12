import random
import builtins as _builtins
import pygame

# --- Constants ---
WIDTH, HEIGHT = 1280, 900
FPS = 60  # Reduced from 120 to 60 for better web browser compatibility

BASE_BLOCK_SIZE = 30
BLOCK_SIZE = 45   # 50% larger than previous 30
SCALE = BLOCK_SIZE / BASE_BLOCK_SIZE

PADDLE_THICK = int(12 * SCALE)
PADDLE_LEN = int(150 * SCALE)  # Increased by 50% and scaled
BALL_RADIUS = int(8 * SCALE)
CANNON_GAP = int(10 * SCALE)
CANNON_LEN = int(25 * SCALE)

# Paddle movement parameters
PADDLE_MAX_SPEED = 10  # pixels per frame (at 60 FPS baseline)
PADDLE_ACCEL      = 0.6  # acceleration per frame while key held
PADDLE_FRICTION   = 0.85 # velocity retained each frame when no input
BALL_SPEED = 5
BALL_FRICTION = 0.999   # multiplier each frame (~0.1% loss, keeps cannonballs lively)
BALL_SHATTER_SPEED = BALL_SPEED * 0.45 # 7% of BALL_SPEED (4*0.07)
SHOOT_INTERVAL = 2000       # ms between castle shots
POWERUP_CHANCE = 0.03        # chance a shot is power-up

# Colors
WHITE = (255,255,255)
RED   = (255,0,0)
GREEN = (0,255,0)
BLUE  = (0,0,255)
YELLOW= (255,255,0)
BG    = (30,30,30)
GREY = (100,100,100)   # cannon colour

# Cannon visuals
CANNON_ARC = 180       # sweep half-width (±180° → 360° total)
CANNON_SPEED = 0.002  # radians per ms – how fast the barrels swing 

PADDLE_MARGIN = int(30 * SCALE)  # gap between paddles and arena edge 
# Dedicated gap for the *bottom* paddle so it clears the player wall
# (double the regular margin plus 10 px → 50 px).
BOTTOM_PADDLE_MARGIN = PADDLE_MARGIN * 2 + int(10 * SCALE)

# --- Control Settings ---
# Default key bindings for game controls
DEFAULT_CONTROLS = {
    'bottom_paddle_left': pygame.K_LEFT,
    'bottom_paddle_right': pygame.K_RIGHT,
    'top_paddle_left': pygame.K_a,
    'top_paddle_right': pygame.K_d,
    'left_paddle_up': pygame.K_w,
    'left_paddle_down': pygame.K_s,
    'right_paddle_up': pygame.K_UP,
    'right_paddle_down': pygame.K_DOWN,
    'bump_launch': pygame.K_SPACE,
    'pause_menu': pygame.K_ESCAPE
}

# Current control mappings (can be modified by options menu)
# This will be loaded from settings file or use defaults
CURRENT_CONTROLS = DEFAULT_CONTROLS.copy()

# Control action descriptions for the UI
CONTROL_DESCRIPTIONS = {
    'bottom_paddle_left': 'Bottom Paddle Left',
    'bottom_paddle_right': 'Bottom Paddle Right',
    'top_paddle_left': 'Top Paddle Left',
    'top_paddle_right': 'Top Paddle Right',
    'left_paddle_up': 'Left Paddle Up',
    'left_paddle_down': 'Left Paddle Down',
    'right_paddle_up': 'Right Paddle Up',
    'right_paddle_down': 'Right Paddle Down',
    'bump_launch': 'Bump/Launch',
    'pause_menu': 'Pause Menu'
}

# Helper function to get key name for display
def get_key_name(key_code):
    """Get a readable name for a pygame key code."""
    key_name = pygame.key.name(key_code)
    # Convert some common key names to more readable format
    if key_name == 'left':
        return '←'
    elif key_name == 'right':
        return '→'
    elif key_name == 'up':
        return '↑'
    elif key_name == 'down':
        return '↓'
    elif key_name == 'space':
        return 'SPACE'
    elif key_name == 'escape':
        return 'ESC'
    elif key_name == 'return':
        return 'ENTER'
    elif key_name == 'backspace':
        return 'BACKSPACE'
    elif key_name == 'tab':
        return 'TAB'
    elif key_name == 'left shift':
        return 'SHIFT'
    elif key_name == 'right shift':
        return 'SHIFT'
    elif key_name == 'left ctrl':
        return 'CTRL'
    elif key_name == 'right ctrl':
        return 'CTRL'
    elif key_name == 'left alt':
        return 'ALT'
    elif key_name == 'right alt':
        return 'ALT'
    else:
        return key_name.upper()

# Helper function to update control mappings
def update_control_mapping(action, new_key):
    """Update a control mapping and save to settings."""
    global CURRENT_CONTROLS
    CURRENT_CONTROLS[action] = new_key

# Helper function to get control key for an action
def get_control_key(action):
    """Get the current key mapping for a control action."""
    return CURRENT_CONTROLS.get(action, DEFAULT_CONTROLS.get(action))

# Helper function to check if a key is pressed for a specific action
def is_control_pressed(action, keys):
    """Check if the key for a specific action is currently pressed."""
    key = get_control_key(action)
    return keys[key] if key else False

# Helper function to check for control conflicts
def has_control_conflicts():
    """Check if any control keys are mapped to the same key."""
    used_keys = {}
    conflicts = []
    
    for action, key in CURRENT_CONTROLS.items():
        if key in used_keys:
            conflicts.append((action, used_keys[key]))
        else:
            used_keys[key] = action
    
    return conflicts

# Universal potion color palette
POTION_COLORS = {
    'widen':  (0,120,255),    # blue
    'sticky': (0,200,0),      # green
    'through': (255, 140, 0), # orange
    'barrier': (0,255,255),   # cyan
    'pierce': (200,0,255)     # purple
}

# Potion type weights for rarity (higher = more common)
POTION_TYPE_WEIGHTS = [
    ('widen', 20),   # most common
    ('sticky', 20),  # most common
    ('through', 10), # uncommon
    ('barrier', 5),  # rare
    ('pierce', 2)    # rarest
]

# Block color pairs for castle and player wall (centralized here)
BLOCK_COLOR_L1 = ((30, 30, 30), (10, 10, 10))        # Layer 1 (darkest)
BLOCK_COLOR_L2 = ((80, 80, 80), (50, 50, 50))     # Layer 2 (medium)
BLOCK_COLOR_L3 = ((130, 130, 130), (110, 110, 110))  # Layer 3 (lightest)
BLOCK_COLOR_DEFAULT = ((110, 110, 110), (90, 90, 90))# Fallback/default wall
BLOCK_COLOR_WALKWAY = ((160, 160, 160), (140, 140, 140)) # Walkway
BLOCK_COLOR_GARDEN = ((34, 139, 34), (46, 160, 46))      # Garden

# --- Crack Generation Parameters ---
CRACK_SEGMENTS_BASE = 2         # Base number of crack segments per hit
CRACK_SEGMENTS_RANDOM = 3      # Max random additional segments per hit
CRACK_SEGMENT_LENGTH_BASE = 60  # Base length of each crack segment
CRACK_SEGMENT_LENGTH_RANDOM = 60 # Max random additional length per segment
CRACK_BRANCH_PROB = 0.55         # Probability a segment will branch
CRACK_BRANCH_MIN = 1            # Minimum number of branches per crack
CRACK_BRANCH_MAX = 2            # Maximum number of branches per crack
CRACK_ANGLE_RANDOMNESS = 0.55    # Radians, max deviation from main direction
CRACK_WIDTH = 2               # Pixel width of crack lines
CRACK_COLOR = (20, 20, 20)      # Color of cracks

MAGNUS_COEFF = 0.054  # Coefficient controlling side force generated by spin (Magnus effect)
SPIN_DAMPING  = 0.995  # Per-frame damping applied to angular velocity
SPIN_TRANSFER = .1    # Fraction of paddle tangential velocity converted into spin on hit
LINEAR_TRANSFER = 0.7  # Fraction of paddle tangential velocity added to linear velocity on hit

DEBUG = False  # Set to False to disable debug console logs

# --- Debug Settings ---
DEBUG_STARTING_COINS = 1000000  # Set to a positive number to start with that many coins (only works when DEBUG = True)

# --- Background music playlist configuration ---
# Specify each track filename and its exact duration in milliseconds. The
# game will start a new track after the given duration instead of relying on
# the mixer to signal the end of playback.
#
# Example durations are placeholders – update these numbers to the precise
# lengths of your actual files (they must match or the loop will start too
# early/late).
BACKGROUND_MUSIC_TRACKS = [
    ("Untitled3.mp3", 101_000),  # 1:41
    ("Untitled4.mp3", 156_000),  # 2:36
    ("Untitled5.mp3", 72_000),   # 1:12
    ("Untitled6.mp3", 61_000),   # 1:01
]

def get_audio_file_for_platform(filename):
    """Convert audio filename to appropriate format for current platform.
    For pygame-web (emscripten), use OGG files instead of MP3."""
    try:
        import platform
        if platform.system() == "Emscripten":
            # Running on pygame-web, use OGG
            if filename.endswith('.mp3'):
                return filename[:-4] + '.ogg'
    except:
        pass
    return filename

# Get platform-appropriate background music tracks
def get_background_music_tracks():
    """Get background music tracks with appropriate file extensions for current platform."""
    return [(get_audio_file_for_platform(filename), duration) 
            for filename, duration in BACKGROUND_MUSIC_TRACKS]

_original_print = _builtins.print

def _debug_filter_print(*args, **kwargs):
    """Custom print that omits messages starting with '[DEBUG]' when DEBUG is False."""
    if not DEBUG:
        if args and isinstance(args[0], str) and args[0].startswith("[DEBUG]"):
            return  # Skip debug message
    _original_print(*args, **kwargs)

_builtins.print = _debug_filter_print

def get_random_potion_type(rng=random):
    try:
        from upgrade_effects import get_unlocked_potions
        unlocked = get_unlocked_potions()
    except ImportError:
        unlocked = []
    if not unlocked:
        return None
    # Filter weights to only unlocked potions
    filtered = [(ptype, w) for (ptype, w) in POTION_TYPE_WEIGHTS if ptype in unlocked]
    if not filtered:
        return None
    types, weights = zip(*filtered)
    return rng.choices(types, weights=weights, k=1)[0] 