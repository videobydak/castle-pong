import pygame, random, math
from typing import List, Dict, Optional, Union
from config import SCALE, WIDTH, HEIGHT, WHITE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from paddle import Paddle

# -----------------------------------------------------------------------------
# Coin collectible – 8-bit pixel coins that provide currency for upgrades.
# -----------------------------------------------------------------------------

__all__ = ["maybe_spawn_coins", "update_coins", "draw_coins", "get_coin_count", "clear_coins"]

# Active coin instances in the world
_active_coins: List["_Coin"] = []

# Global coin counter
_total_coins = 0

# Global cache for coin collect sound (None = not loaded yet, False = failed)
_COIN_SOUND = None

# Coin multiplier (can be enhanced by store upgrades)
_coin_multiplier = 1.0


class _Coin:
    """A collectible coin that spawns from destroyed castle blocks."""

    # Pre-bake coin textures for different animation frames
    _TEX_CACHE: Dict[int, List[pygame.Surface]] = {}

    def __init__(self, x: float, y: float, vel: pygame.Vector2, value: int = 1):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(vel)
        self.resting = False  # once velocity is near zero the coin rests
        self.life_ms = 20000  # disappear after 20 s if not collected
        self.size_px = int(14 * SCALE)  # visual size of sprite
        self.collect_delay = 300  # ms before the coin can be collected
        self.value = value  # how many coins this represents
        self.anim_timer = 0  # for rotation animation
        self.bob_timer = random.uniform(0, 2 * math.pi)  # random phase for bobbing
        
        # Magnetism effect (can be enabled by store upgrades)
        self.magnetism_strength = 0.0

    def update(self, dt_frames: float, dt_ms: int, balls: Optional[list] = None):
        if not self.resting:
            # Apply simple friction so the coin slows down quickly
            self.vel *= 0.90
            # Stop once almost stationary
            if self.vel.length_squared() < 0.01:
                self.vel.xy = (0, 0)
                self.resting = True
        
        # Magnetism effect - attract towards white cannonballs
        if self.magnetism_strength > 0 and balls is not None:
            from ball import Ball  # local import to avoid circular deps
            for ball in balls:
                if isinstance(ball, Ball) and ball.color == WHITE and not getattr(ball, 'friendly', False):
                    dist_vec = ball.pos - self.pos
                    distance = dist_vec.length()
                    if distance < 100 and distance > 0:  # within magnetism range
                        # Apply attraction force
                        force = dist_vec.normalize() * self.magnetism_strength * (1.0 / max(distance * 0.01, 1.0))
                        self.vel += force * dt_frames
        
        # Integrate position
        self.pos += self.vel * dt_frames
        
        # Add gentle bobbing motion when resting
        if self.resting:
            self.bob_timer += dt_ms * 0.003
            bob_offset = math.sin(self.bob_timer) * 2
            self.pos.y += bob_offset * dt_frames * 0.1
        
        # Clamp inside the playfield so it does not drift off-screen
        self.pos.x = max(0, min(WIDTH, self.pos.x))
        self.pos.y = max(0, min(HEIGHT, self.pos.y))
        
        # Age out when lifetime expires
        self.life_ms -= dt_ms
        
        # Reduce collection delay
        if self.collect_delay > 0:
            self.collect_delay = max(0, self.collect_delay - dt_ms)
        
        # Update animation timer
        self.anim_timer += dt_ms
        
        return self.life_ms > 0

    def rect(self) -> pygame.Rect:
        half = self.size_px // 2
        return pygame.Rect(int(self.pos.x - half), int(self.pos.y - half),
                           self.size_px, self.size_px)

    def draw(self, screen: pygame.Surface):
        # Get animated texture (rotating coin effect)
        frame = int(self.anim_timer / 100) % 8  # 8 frames, 100ms each
        tex = self._get_tex(self.size_px, frame)
        rect = tex.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        screen.blit(tex, rect)
        
        # Draw value indicator for multi-coin pickups
        if self.value > 1:
            from pygame import font
            small_font = font.SysFont(None, int(16 * SCALE))
            value_text = small_font.render(f"{self.value}", True, (255, 255, 255))
            value_rect = value_text.get_rect(center=(int(self.pos.x), int(self.pos.y - self.size_px//2 - 8)))
            # Draw black outline
            for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1)]:
                outline_rect = value_rect.copy()
                outline_rect.x += dx
                outline_rect.y += dy
                outline_text = small_font.render(f"{self.value}", True, (0, 0, 0))
                screen.blit(outline_text, outline_rect)
            screen.blit(value_text, value_rect)

    @classmethod
    def _get_tex(cls, size: int, frame: int) -> pygame.Surface:
        """Return a cached Surface containing an 8-bit coin animation frame."""
        if size not in cls._TEX_CACHE:
            cls._TEX_CACHE[size] = []
            # Generate 8 frames for rotation animation
            for f in range(8):
                surf = pygame.Surface((size, size), pygame.SRCALPHA)
                
                # Calculate coin ellipse width based on rotation frame
                # Frames 0-3: narrow to wide, frames 4-7: wide to narrow
                if f <= 3:
                    width_ratio = 0.2 + 0.8 * (f / 3.0)
                else:
                    width_ratio = 1.0 - 0.8 * ((f - 4) / 3.0)
                
                coin_width = int(size * 0.8 * width_ratio)
                coin_height = int(size * 0.8)
                
                # Golden color scheme
                if width_ratio > 0.7:
                    outer_color = (255, 215, 0)  # gold
                    inner_color = (255, 255, 150)  # bright gold
                elif width_ratio > 0.4:
                    outer_color = (204, 172, 0)  # darker gold
                    inner_color = (255, 215, 0)  # gold
                else:
                    outer_color = (153, 129, 0)  # darkest gold (side view)
                    inner_color = (204, 172, 0)  # darker gold
                
                center = (size // 2, size // 2)
                
                # Draw outer ellipse
                if coin_width > 2:
                    outer_rect = pygame.Rect(center[0] - coin_width//2, center[1] - coin_height//2, 
                                           coin_width, coin_height)
                    pygame.draw.ellipse(surf, outer_color, outer_rect)
                    
                    # Draw inner highlight ellipse
                    if coin_width > 6:
                        inner_width = max(2, coin_width - 4)
                        inner_height = max(2, coin_height - 4)
                        inner_rect = pygame.Rect(center[0] - inner_width//2, center[1] - inner_height//2,
                                               inner_width, inner_height)
                        pygame.draw.ellipse(surf, inner_color, inner_rect)
                    
                    # Draw center detail for wider frames
                    if width_ratio > 0.5 and coin_width > 8:
                        detail_width = max(1, coin_width // 3)
                        detail_height = max(1, coin_height // 3)
                        detail_rect = pygame.Rect(center[0] - detail_width//2, center[1] - detail_height//2,
                                                detail_width, detail_height)
                        pygame.draw.ellipse(surf, (255, 255, 200), detail_rect)
                
                # Draw black outline
                if coin_width > 1:
                    outline_rect = pygame.Rect(center[0] - coin_width//2, center[1] - coin_height//2, 
                                             coin_width, coin_height)
                    pygame.draw.ellipse(surf, (0, 0, 0), outline_rect, 1)
                
                cls._TEX_CACHE[size].append(surf)
        
        return cls._TEX_CACHE[size][frame]


# -----------------------------------------------------------------------------
# Public interface helpers used by the rest of the game
# -----------------------------------------------------------------------------

def maybe_spawn_coins(block_rect: pygame.Rect):
    """Spawn coins when *block_rect* is destroyed.
    
    10% chance to spawn coins:
    - 20% chance for 2 coins
    - 10% chance for 3 coins  
    - 70% chance for 1 coin (remaining percentage)
    """
    global _coin_multiplier
    
    # 10% base chance to spawn coins
    if random.random() >= 0.10:
        return  # no coins this time
    
    # Determine coin count
    coin_roll = random.random()
    if coin_roll < 0.20:  # 20% chance
        count = 2
    elif coin_roll < 0.30:  # 10% chance (20% + 10%)
        count = 3
    else:  # 70% chance (remaining)
        count = 1
    
    # Apply coin multiplier from upgrades
    actual_count = int(count * _coin_multiplier)
    if actual_count < 1:
        actual_count = 1
    
    for i in range(actual_count):
        angle = random.uniform(0, 360)
        speed = random.uniform(3.0, 6.0) * SCALE
        vel = pygame.Vector2(speed, 0).rotate(angle)
        
        # Slight variation in spawn position for multiple coins
        offset_x = random.uniform(-5, 5) if actual_count > 1 else 0
        offset_y = random.uniform(-5, 5) if actual_count > 1 else 0
        
        coin = _Coin(block_rect.centerx + offset_x, block_rect.centery + offset_y, vel)
        _active_coins.append(coin)


def update_coins(dt_frames: float, dt_ms: int, balls: list):
    """Update all active coins and resolve collection by cannonballs."""
    global _total_coins
    from ball import Ball  # local import to avoid circular deps
    
    # --- Iterate in reverse so we can remove safely while looping ---
    for coin in _active_coins[:]:
        alive = coin.update(dt_frames, dt_ms, balls)
        if not alive:
            _active_coins.remove(coin)
            continue
        
        # Collision check with WHITE cannonballs only
        c_rect = coin.rect()
        collected = False
        if coin.collect_delay == 0:  # only collectible after delay
            for ball in balls:
                if (isinstance(ball, Ball) and ball.color == WHITE and 
                    not getattr(ball, 'friendly', False) and c_rect.colliderect(ball.rect())):
                    collected = True
                    break
        
        if collected:
            # Add coins to total
            _total_coins += coin.value
            _play_coin_sound()
            _active_coins.remove(coin)


def draw_coins(screen: pygame.Surface):
    """Render all coins onto *screen*."""
    for coin in _active_coins:
        coin.draw(screen)


def get_coin_count() -> int:
    """Return total coins collected."""
    return _total_coins


def spend_coins(amount: int) -> bool:
    """Spend coins if available. Returns True if successful."""
    global _total_coins
    if _total_coins >= amount:
        _total_coins -= amount
        return True
    return False


def set_coin_multiplier(multiplier: float):
    """Set the coin drop multiplier from store upgrades."""
    global _coin_multiplier
    _coin_multiplier = multiplier


def set_magnetism_strength(strength: float):
    """Set magnetism strength for all coins."""
    for coin in _active_coins:
        coin.magnetism_strength = strength


def clear_coins():
    """Clear all active coins (used for game reset)."""
    global _active_coins
    _active_coins = []


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

def _play_coin_sound():
    """Play the coin-collect sound effect with lazy loading."""
    global _COIN_SOUND
    if _COIN_SOUND is None:
        try:
            _COIN_SOUND = pygame.mixer.Sound("Sound Response - 8 Bit Retro - Arcade Blip.wav")
            _COIN_SOUND.set_volume(0.7)
        except pygame.error as e:
            print("[Audio] Failed to load coin SFX:", e)
            _COIN_SOUND = False  # mark as unusable
    if _COIN_SOUND:
        _COIN_SOUND.play()


if __name__ == "__main__":
    # Test coin animation
    import sys
    pygame.init()
    size = 200
    screen = pygame.display.set_mode((size, size))
    pygame.display.set_caption("Coin Animation Test")
    clock = pygame.time.Clock()
    
    test_coin = _Coin(size//2, size//2, pygame.Vector2(0, 0), 1)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        dt = clock.tick(60)
        test_coin.update(dt / (1000/60), dt)
        
        screen.fill((50, 50, 50))
        test_coin.draw(screen)
        pygame.display.flip()
    
    pygame.quit()
    sys.exit()