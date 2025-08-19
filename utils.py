# Utility helpers and simple particle/texture generators for the 8-bit look

import pygame, random, math, sys, os
from pathlib import Path
from config import SCALE, BLOCK_COLOR_L1, BLOCK_COLOR_L2, BLOCK_COLOR_L3, BLOCK_COLOR_DEFAULT, BLOCK_COLOR_WALKWAY, BLOCK_COLOR_GARDEN

# Generate a background grass texture once
def generate_grass(w,h):
    grass = pygame.Surface((w,h))
    tile = 8
    for y in range(0,h,tile):
        for x in range(0,w,tile):
            shade = random.choice([(20,120,20), (30,140,30), (25,130,25)])
            grass.fill(shade, pygame.Rect(x,y,tile,tile))
    return grass

# --- 8-bit texture helpers ---
def make_checker(size, col1, col2):
    surf = pygame.Surface((size, size))
    tile = size // 2
    surf.fill(col1)
    pygame.draw.rect(surf, col2, (0,0,tile,tile))
    pygame.draw.rect(surf, col2, (tile,tile,tile,tile))
    return surf

# --- Texture: 8-bit bricks for castle walls ---
def make_bricks(size, base_col=BLOCK_COLOR_DEFAULT[0], mortar_col=(60,60,60), **kwargs):
    """Return a surface with a brick pattern that includes subtle highlights and shadows
    for a brighter, more contrasty look."""

    # Derive brighter and darker variants for highlight / shadow edges
    def _lighter(col, amt=40):
        return tuple(min(255, c + amt) for c in col)

    def _darker(col, amt=40):
        return tuple(max(0, c - amt) for c in col)

    base_light = _lighter(base_col, 30)   # overall brighter base fill
    highlight  = _lighter(base_col, 60)   # edge highlight
    shadow     = _darker(base_col, 60)    # edge shadow

    surf = pygame.Surface((size, size))
    surf.fill(base_light)

    brick_h = size // 4  # 4 rows of bricks
    brick_w = size // 2  # 2 bricks per row

    for row in range(4):
        y = row * brick_h
        offset = (brick_w // 2) if row % 2 else 0

        # Horizontal mortar line (between rows)
        pygame.draw.line(surf, mortar_col, (0, y), (size, y), 1)

        for col in range(3):  # slight overlap to cover edges
            x = (col * brick_w - offset) % size

            # Vertical mortar
            pygame.draw.line(surf, mortar_col, (x, y), (x, y + brick_h), 1)

            # Highlight (top & left edges of brick)
            pygame.draw.line(surf, highlight, (x + 1, y + 1), (x + brick_w - 2, y + 1))
            pygame.draw.line(surf, highlight, (x + 1, y + 1), (x + 1, y + brick_h - 2))

            # Shadow (bottom & right edges)
            br = x + brick_w - 2
            bb = y + brick_h - 2
            pygame.draw.line(surf, shadow, (x + 1, bb), (br, bb))
            pygame.draw.line(surf, shadow, (br, y + 1), (br, bb))

    # Optional outer border – enabled only when explicitly asked for.
    # By default bricks now have no thick outline so that neighbouring
    # castle tiles can blend seamlessly. A border will be drawn later at
    # the castle level only for edges that are actually exposed.
    if kwargs.get('draw_border', False):
        pygame.draw.rect(surf, shadow, surf.get_rect(), 1)
    return surf

# --- Texture: rounded-corner brick tile (quarter-circle cut-out) ---
def make_round_bricks(size, base_col=BLOCK_COLOR_DEFAULT[0], mortar_col=(60,60,60), corner='tl'):
    """Return a brick surface with a rounded outer corner.

    corner: 'tl', 'tr', 'bl', or 'br' for which corner is curved.
    The curved section is transparent so neighbouring flat tiles can snug up
    without leaving a hard edge.
    """
    surf = make_bricks(size, base_col, mortar_col, draw_border=False).convert_alpha()

    # Draw a filled quarter-circle of fully transparent pixels to punch out
    # the corner so it appears rounded when blitted.
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))

    # Map so that the removed quarter-circle faces OUTWARD (grass side) rather
    # than inward.  This fixes the previous inversion bug where the curved part
    # appeared inside the castle.
    if corner == 'tl':
        centre = (-size, -size)
    elif corner == 'tr':
        centre = (size*2, -size)
    elif corner == 'bl':
        centre = (-size, size*2)
    else:  # 'br'
        centre = (size*2, size*2)

    pygame.draw.circle(mask, (0, 0, 0, 255), centre, size)
    # Subtract the mask from surf (set alpha to 0 where mask is opaque)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    return surf

# --- Texture: small garden / grass courtyard tile ---
def make_garden(size):
    """Tiny grassy tile for inner courtyards."""
    surf = pygame.Surface((size, size))
    tile = size // 4
    for y in range(0, size, tile):
        for x in range(0, size, tile):
            shade = random.choice([(34, 139, 34), (46, 160, 46), (40, 149, 40)])
            pygame.draw.rect(surf, shade, (x, y, tile, tile))
    # faint dirt specks
    for _ in range(int(size * size * 0.02)):
        surf.set_at((random.randint(0, size - 1), random.randint(0, size - 1)), (60, 40, 20))
    return surf

# --- Simple particle for debris/FX ---
class Particle:
    __slots__ = ("pos", "vel", "color", "life", "size", "alpha", "fade", "_base_size", "_base_life", "friction")
    def __init__(self, x, y, vel, color, life, size=1, alpha=255, fade=True, friction=None):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(vel) * SCALE  # scale velocity
        self.color = color
        self.life = life  # frames
        self._base_life = life
        self.size = int(size * SCALE)  # scale size
        self._base_size = int(size * SCALE)
        self.alpha = alpha
        self.fade = fade  # If true, alpha fades out as life decreases
        # Introduce per-particle friction so particles decelerate uniquely
        self.friction = friction if friction is not None else random.uniform(0.94, 0.985)
    def update(self):
        self.pos += self.vel
        # Apply per-particle friction for varied deceleration
        self.vel *= self.friction
        self.life -= 1
        if self.fade and self.life > 0:
            life_ratio = self.life / max(1, self._base_life)
            self.alpha = int(255 * life_ratio)
            self.size = max(1, int(self._base_size * life_ratio))
    def draw(self, surf):
        if self.life > 0:
            if self.size > 1:
                self.draw_circle(surf)
            else:
                c = self.color if self.alpha >= 255 else (*self.color[:3], self.alpha)
                surf.set_at((int(self.pos.x), int(self.pos.y)), c)
    def draw_circle(self, surf):
        if self.life > 0:
            c = self.color if self.alpha >= 255 else (*self.color[:3], self.alpha)
            pygame.draw.circle(surf, c, (int(self.pos.x), int(self.pos.y)), self.size)

# --- Texture: 8-bit wooden plank tile ---

def make_wood(size=8, base_col=(176, 96, 32)):
    """Return a small square Surface with an 8-bit wood-plank pattern."""
    surf = pygame.Surface((size, size))
    # two vertical stripes per tile to simulate planks
    col_variants = [
        tuple(max(0, min(255, c + random.randint(-20, 20))) for c in base_col)
        for _ in range(4)
    ]
    strip_w = size // 2
    # left plank
    pygame.draw.rect(surf, col_variants[0], (0, 0, strip_w, size))
    # right plank
    pygame.draw.rect(surf, col_variants[1], (strip_w, 0, strip_w, size))
    # add subtle darker grain lines
    for _ in range(random.randint(1, 3)):
        y = random.randint(0, size - 1)
        pygame.draw.line(surf, col_variants[2], (0, y), (size, y))
    # occasional knot pixel
    if random.random() < 0.3:
        xk, yk = random.randint(0, size - 1), random.randint(0, size - 1)
        surf.set_at((xk, yk), col_variants[3])
    return surf 

# -----------------------------------------------------------------------------
#  Cross-platform asset helper & automatic pygame monkey-patches
# -----------------------------------------------------------------------------


def resource_path(relative: str) -> str:
    """Return an absolute path to *relative* that works both from source and
    when the program is bundled (PyInstaller/py2app).

    Example::

        surf = pygame.image.load(resource_path("gfx/sprite.png"))

    """
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base_path) / relative)


def resource_exists(relative: str) -> bool:
    """Check if a resource exists, works both from source and when bundled.
    
    This is needed because os.path.isfile() doesn't work with bundled resources.
    """
    # If we're running from source, use normal file check
    if not hasattr(sys, "_MEIPASS"):
        return os.path.isfile(relative)
    
    # If we're bundled, check if the resource exists in the bundle
    resource_file = resource_path(relative)
    return os.path.isfile(resource_file)


def load_font(font_name: str, size: int, fallback_name: str = 'Courier New', fallback_bold: bool = True) -> pygame.font.Font:
    """Load a font with proper resource path handling and fallback.
    
    This function handles font loading for both source and bundled versions.
    """
    try:
        # Try to load the custom font using resource_path
        font_path = resource_path(font_name)
        if os.path.isfile(font_path):
            return pygame.font.Font(font_path, size)
        
        # If resource_path didn't work, try the original filename
        if os.path.isfile(font_name):
            return pygame.font.Font(font_name, size)
            
    except Exception as e:
        print(f"[Font] Failed to load {font_name}: {e}")
    
    # Fallback to system font - use Font instead of SysFont for Mac compatibility
    print(f"[Font] Using fallback font: None (default)")
    return pygame.font.Font(None, size)


# Monkey-patch pygame so existing ``pygame.mixer.Sound("foo.wav")`` and
# ``pygame.font.Font("PressStart2P-Regular.ttf", size)`` calls keep working even
# after the game is frozen into a single executable.  If the original relative
# path fails, we retry through ``resource_path``.


def _patch_pygame_loaders():
    if getattr(pygame, "_castle_pong_asset_patch", False):  # already patched
        return

    pygame._castle_pong_asset_patch = True

    # --- Sound objects -------------------------------------------------------
    _orig_sound = pygame.mixer.Sound

    def _sound_wrapper(*args, **kwargs):
        """Wrapper that redirects relative file paths through resource_path.

        pygame allows several ways to create a Sound:
            Sound("path.wav")
            Sound(file="path.wav")
            Sound(buffer=b"…")
            Sound(array=my_ndarray)

        Our patch should only touch cases that supply a *file* path and leave
        buffer/array constructions untouched.  Additionally, some callers (e.g.
        pygame.sndarray.make_sound) create sounds via the *array* keyword and
        **do not** pass the positional *file* parameter.  The old wrapper
        expected the positional argument and therefore broke with a
        TypeError.  This new implementation handles all variants safely.
        """

        # Determine if a file path was provided either positionally or via the
        # keyword argument.  If so, rewrite it when it is a relative path that
        # cannot be found on disk (important for PyInstaller builds).
        if args:
            file_arg = args[0]
            if isinstance(file_arg, str) and not os.path.isabs(file_arg) and not os.path.exists(file_arg):
                args = (resource_path(file_arg),) + args[1:]
        elif 'file' in kwargs and isinstance(kwargs['file'], str):
            f = kwargs['file']
            if not os.path.isabs(f) and not os.path.exists(f):
                kwargs['file'] = resource_path(f)

        # All other creation modes (buffer=, array=) are forwarded verbatim.
        return _orig_sound(*args, **kwargs)

    pygame.mixer.Sound = _sound_wrapper

    # --- Music loader --------------------------------------------------------
    _orig_music_load = pygame.mixer.music.load

    def _music_load_wrapper(file, *args, **kwargs):
        if isinstance(file, str) and not os.path.isabs(file) and not os.path.exists(file):
            file = resource_path(file)
        return _orig_music_load(file, *args, **kwargs)

    pygame.mixer.music.load = _music_load_wrapper

    # --- Font loader ---------------------------------------------------------
    _orig_font = pygame.font.Font

    def _font_wrapper(file, size, *args, **kwargs):
        if file and isinstance(file, str) and not os.path.isabs(file) and not os.path.exists(file):
            file = resource_path(file)
        return _orig_font(file, size, *args, **kwargs)

    pygame.font.Font = _font_wrapper


# Apply patches immediately on import so the rest of the game benefits.
_patch_pygame_loaders()

# -----------------------------------------------------------------------------
#  End of utils additions
# ----------------------------------------------------------------------------- 