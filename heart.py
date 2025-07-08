import pygame, random, math
from typing import List, Dict, Optional
from config import SCALE, WIDTH, HEIGHT, WHITE, PADDLE_MARGIN, PADDLE_LEN
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from paddle import Paddle

# -----------------------------------------------------------------------------
# Heart collectible – simple 8-bit pixel heart that heals the weakest paddle.
# -----------------------------------------------------------------------------

__all__ = ["maybe_spawn_hearts", "update_hearts", "draw_hearts", "clear_hearts"]

# Active heart instances in the world
_active_hearts: List["_Heart"] = []

# Track latest paddle states for spawn chance calculation
_last_paddles: Optional[Dict[str, "Paddle"]] = None

# Global cache for heal sound (None = not loaded yet, False = failed)
_HEAL_SOUND = None

# Minimum paddle pixel length considered "critical" (matches Paddle.shrink limit)
_MIN_PADDLE_WIDTH = 20


class _Heart:
    """A small collectible heart that spawns from destroyed castle blocks."""

    # Pre-bake a tiny 8-bit heart surface so every instance can blit it cheaply
    _TEX_CACHE: Dict[int, pygame.Surface] = {}

    def __init__(self, x: float, y: float, vel: pygame.Vector2):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(vel)
        self.resting = False  # once velocity is near zero the heart rests
        self.life_ms = 15000  # disappear after 15 s if not collected
        self.size_px = int(12 * SCALE)  # visual size of sprite
        self.collect_delay = 400  # ms before the heart can be collected

    # ---------------------------------------------------------------------
    # Behaviour & state updates
    # ---------------------------------------------------------------------
    def update(self, dt_frames: float, dt_ms: int):
        if not self.resting:
            # Apply simple friction so the heart slows down quickly
            self.vel *= 0.92
            # Stop once almost stationary
            if self.vel.length_squared() < 0.01:
                self.vel.xy = (0, 0)
                self.resting = True
        # Integrate position regardless (safe even if vel==0)
        self.pos += self.vel * dt_frames
        # Clamp inside the playfield so it does not drift off-screen
        self.pos.x = max(0, min(WIDTH, self.pos.x))
        self.pos.y = max(0, min(HEIGHT, self.pos.y))
        # Age out when lifetime expires
        self.life_ms -= dt_ms
        # Reduce collection delay
        if self.collect_delay > 0:
            self.collect_delay = max(0, self.collect_delay - dt_ms)
        return self.life_ms > 0

    # ------------------------------------------------------------------
    # Geometry helpers – keep collision as axis-aligned square for speed
    # ------------------------------------------------------------------
    def rect(self) -> pygame.Rect:
        half = self.size_px // 2
        return pygame.Rect(int(self.pos.x - half), int(self.pos.y - half),
                           self.size_px, self.size_px)

    # ------------------------------------------------------------------
    # Rendering – draw an 8-bit pixel heart with simple highlight
    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface):
        tex = self._get_tex(self.size_px)
        rect = tex.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        screen.blit(tex, rect)

    @classmethod
    def _get_tex(cls, size: int) -> pygame.Surface:
        """Return a cached Surface containing a pixel-art heart."""
        if size in cls._TEX_CACHE:
            return cls._TEX_CACHE[size]
        # Build texture
        import numpy as np
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        col = (220, 20, 60)
        hil = (255, 140, 170)
        outline_col = (0, 0, 0)

        # Parametric heart curve
        t = np.linspace(0, 2 * np.pi, 120)
        x = 16 * np.sin(t) ** 3
        y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)

        # Normalize and scale to fit the surface
        x = x - x.min()
        y = y - y.min()
        x = x / np.ptp(x) * (size * 0.9) + size * 0.05
        y = y / np.ptp(y) * (size * 0.9) + size * 0.05
        # Flip vertically to make the heart right-side up
        y = size - y
        pts = [(int(xi), int(yi)) for xi, yi in zip(x, y)]

        # Draw filled heart
        pygame.draw.polygon(surf, col, pts)
        # Draw black outline
        pygame.draw.aalines(surf, outline_col, True, pts)
        # Draw a large highlight (ellipse) on the upper left, rotated 90 degrees, scrunched vertically and shifted left
        highlight_width = size // 7
        highlight_height = int(size // 4 * 0.85)  # scrunch vertically by 15%
        highlight_rect = pygame.Rect(0, 0, highlight_width, highlight_height)
        highlight_rect.center = (int(size * 0.32) - 5, int(size * 0.28))  # move left by 10 pixels
        pygame.draw.ellipse(surf, hil, highlight_rect)

        cls._TEX_CACHE[size] = surf
        return surf


# -----------------------------------------------------------------------------
# Public interface helpers used by the rest of the game
# -----------------------------------------------------------------------------

def maybe_spawn_hearts(block_rect: pygame.Rect):
    """Spawn 1–3 hearts when *block_rect* is destroyed based on paddle health.

    Probability scales with the weakest paddle:
    • 90 % when any paddle is at minimum width.
    • Linearly decreases to 0 % when all paddles are ≥ 90 % of base length.
    """
    chance = _compute_spawn_chance()
    if random.random() >= chance:
        return  # no drop this time
    # --- decide count (10 % of drops become triple) ---
    count = 3 if random.random() < 0.10 else 1
    for _ in range(count):
        angle = random.uniform(0, 360)
        speed = random.uniform(2.5, 5.0) * SCALE
        vel = pygame.Vector2(speed, 0).rotate(angle)
        # print(f"[HEART] Spawning heart at ({block_rect.centerx}, {block_rect.centery}) with vel {vel}")
        _active_hearts.append(_Heart(block_rect.centerx, block_rect.centery, vel))


def _compute_spawn_chance() -> float:
    """Return spawn probability (0–1) based on current paddle health."""
    from config import PADDLE_LEN
    if not _last_paddles:
        return 0.0
    weakest = min(p.width for p in _last_paddles.values())
    # No chance once weakest paddle ≥ 90 % health
    high_threshold = int(PADDLE_LEN * 0.9)
    if weakest >= high_threshold:
        return 0.0
    # Linear interpolation between min size and 90 % health
    ratio = (weakest - _MIN_PADDLE_WIDTH) / max(1, (high_threshold - _MIN_PADDLE_WIDTH))
    ratio = max(0.0, min(1.0, ratio))
    return 0.9 * (1 - ratio)


def update_hearts(dt_frames: float, dt_ms: int, balls: list, paddles: Dict[str, "Paddle"]):
    """Update all active hearts and resolve collection by cannonballs."""
    from ball import Ball  # local import to avoid circular deps
    # --- Iterate in reverse so we can remove safely while looping ---
    for heart in _active_hearts[:]:
        alive = heart.update(dt_frames, dt_ms)
        if not alive:
            _active_hearts.remove(heart)
            continue
        # Collision check with player-controlled balls (any ball hit by paddle)
        h_rect = heart.rect()
        collected = False
        if heart.collect_delay == 0:  # only collectible after delay
            for ball in balls:
                if (isinstance(ball, Ball) and not getattr(ball, 'friendly', False) and h_rect.colliderect(ball.rect())):
                    collected = True
                    break
        if collected:
            # Heal weakest paddle (smallest width)
            if paddles:
                weakest = min(paddles.values(), key=lambda p: p.width)
                _heal_paddle(weakest)
            _active_hearts.remove(heart)

    # ---- Store paddles for chance calculation ----
    global _last_paddles
    _last_paddles = paddles


def draw_hearts(screen: pygame.Surface):
    """Render all hearts onto *screen*."""
    # Debug: print count once per frame when hearts exist
    # if _active_hearts:
    #     print(f"[HEART] Drawing {{_active_hearts.__len__()}} hearts")
    for heart in _active_hearts:
        heart.draw(screen)


def clear_hearts():
    """Clear all active hearts from the field (used for game reset)."""
    global _active_hearts
    _active_hearts = []


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

def _play_heal_sound():
    """Play the heart-collect sound effect with lazy loading."""
    global _HEAL_SOUND
    if _HEAL_SOUND is None:
        try:
            _HEAL_SOUND = pygame.mixer.Sound("Sound Response - 8 Bit Retro - Pulsating Arcade Glitch 2.wav")
            # Volume will be set by options menu
        except pygame.error as e:
            print("[Audio] Failed to load heal SFX:", e)
            _HEAL_SOUND = False  # mark as unusable
    if _HEAL_SOUND:
        # Update volume before playing
        _update_heal_sound_volume()
        _HEAL_SOUND.play()


def _update_heal_sound_volume():
    """Update heal sound volume based on current settings."""
    global _HEAL_SOUND
    if not _HEAL_SOUND:
        return
    
    try:
        import sys
        if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'options_menu'):
            options_menu = sys.modules['__main__'].options_menu
            if hasattr(options_menu, 'settings'):
                if options_menu.settings.get('sfx_muted', False):
                    _HEAL_SOUND.set_volume(0)
                else:
                    sfx_vol = options_menu.settings.get('sfx_volume', 0.75)
                    _HEAL_SOUND.set_volume(sfx_vol)
    except Exception as e:
        print(f"[Heart] Failed to update sound volume: {e}")


def _heal_paddle(paddle):
    """Restore paddle length by twice fireball damage (max = base length)."""
    from config import WIDTH, HEIGHT  # late import to avoid cycles
    # Target width: +40 % of *current* length capped at base PADDLE_LEN.
    new_len = min(PADDLE_LEN, int(paddle.width * 1.4))
    if new_len <= paddle.width:  # already at max – nothing to do
        return
    if paddle.side in ("top", "bottom"):
        centre = paddle.rect.centerx
        paddle.rect.width = new_len
        paddle.rect.x = max(PADDLE_MARGIN, min(WIDTH - new_len - PADDLE_MARGIN, centre - new_len // 2))
    else:
        centre = paddle.rect.centery
        paddle.rect.height = new_len
        paddle.rect.y = max(PADDLE_MARGIN, min(HEIGHT - new_len - PADDLE_MARGIN, centre - new_len // 2))
    paddle.width = new_len
    # Trigger visual pulse & sound on the healed paddle
    try:
        paddle.heal_pulse_timer = 60  # ~0.5 s at 120 FPS or 1 s at 60 FPS
    except AttributeError:
        pass
    _play_heal_sound()


if __name__ == "__main__":
    import sys
    pygame.init()
    size = 120
    screen = pygame.display.set_mode((size, size))
    pygame.display.set_caption("Heart Test")
    clock = pygame.time.Clock()
    heart_size = int(48 * SCALE)
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        screen.fill((30, 30, 30))
        # Draw the heart in the center
        surf = _Heart._get_tex(heart_size)
        rect = surf.get_rect(center=(size // 2, size // 2))
        screen.blit(surf, rect)
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    sys.exit() 