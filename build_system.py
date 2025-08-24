import pygame
import math
import random
from typing import List, Dict, Optional, Tuple
from config import WIDTH, HEIGHT, BLOCK_SIZE, SCALE, WHITE, YELLOW, RED, GREEN, BLUE
from player_wall import PlayerWall

# -----------------------------------------------------------------------------
# Build System - Turret placement and management
# -----------------------------------------------------------------------------

class Turret:
    """Base class for all turrets that can be placed on the map."""
    
    def __init__(self, x: int, y: int, turret_type: str):
        self.x = x
        self.y = y
        self.turret_type = turret_type
        self.rect = pygame.Rect(x, y, BLOCK_SIZE, BLOCK_SIZE)
        self.health = 100
        self.max_health = 100
        self.active = True
        self.last_shot = 0
        self.shot_cooldown = 1000  # ms
        self.range = 150  # pixels
        self.damage = 25
        self.target = None
        self.rotation = 0
        self.rotation_speed = 120  # degrees per second
        
        # Accuracy properties (low base accuracy, improves with upgrades)
        self.accuracy = 0.1  # Base accuracy (0.0 = very inaccurate, 1.0 = perfect)
        self.spread_degrees = 25  # Base projectile spread in degrees
        self.timing_variation = 0.4  # Shot timing variation (0.0 = perfect, 1.0 = very random)
        
        # Visual properties
        self.color = WHITE
        self.border_color = YELLOW
        self.health_bar_color = GREEN
        
        # Animation states
        self.charge_start_time = 0  # When charging animation began
        self.charge_duration = 1000  # ms to charge before firing
        self.charging = False
        self.reload_start_time = 0  # When reload animation began
        
        # Animation properties
        self.recoil_timer = 0
        self.recoil_distance = 0
        
    def update(self, dt_ms: int, enemies: List, player_wall: PlayerWall, castle_blocks: List = None) -> Optional[dict]:
        """Update turret logic. Returns projectile data if firing."""
        if not self.active:
            return None
            
        now = pygame.time.get_ticks()

        # ------------------------------------------------------------
        # Rapid-fire reload handling (generic – only active if attrs exist)
        # ------------------------------------------------------------
        if getattr(self, 'reloading', False):
            if now - getattr(self, 'reload_start', 0) < getattr(self, 'reload_cooldown', 0):
                # Still reloading – cannot do anything but rotate
                self._find_target(enemies, player_wall, castle_blocks)
                self._update_rotation(dt_ms)
                return None
            else:
                # Reload complete – reset counters
                self.reloading = False
                self.burst_count = 0

        # Find target (prioritize projectiles over castle blocks)
        self.target = self._find_target(enemies, player_wall, castle_blocks)
        
        # Debug: print turret status occasionally
        if pygame.time.get_ticks() % 2000 < 50:  # Every 2 seconds for 50ms
            from ammo import get_ammo_by_type, get_ammo_count
            type_ammo = get_ammo_by_type(self.turret_type)
            general_ammo = get_ammo_count()
            cooldown_ready = pygame.time.get_ticks() - self.last_shot > self.shot_cooldown
            target_info = f"at ({self.target.x:.0f},{self.target.y:.0f})" if self.target else "NONE"
            castle_block_count = len(castle_blocks) if castle_blocks else 0
            print(f"DEBUG: Turret {self.turret_type} at ({self.x},{self.y}): target={target_info}, ammo={type_ammo}/{general_ammo}, cooldown_ready={cooldown_ready}, castle_blocks={castle_block_count}")
        
        # Always update rotation for smooth movement
        self._update_rotation(dt_ms)
        
        # Apply timing variation based on accuracy
        timing_variation = getattr(self, 'timing_variation', 0.2)
        actual_cooldown = self.shot_cooldown * (1 + random.uniform(-timing_variation, timing_variation))
        
        # Charging phase - start charging if ready to fire but not already charging
        if (self.target and now - self.last_shot > actual_cooldown and not self.charging):
            # Start charging
            self.charging = True
            self.charge_start_time = now
        
        # Fire if charging is complete
        if self.charging and now - self.charge_start_time >= self.charge_duration:
            # Check if we still have a valid target
            if not self.target:
                self.charging = False  # Stop charging if target is lost
                return None
                
            # Check if we have ammo
            from ammo import spend_ammo, get_ammo_by_type, get_ammo_count
            turret_type = getattr(self, 'turret_type', 'basic')
            
            # Try to spend ammo
            if not spend_ammo(1, turret_type):
                # No ammo available
                self.charging = False  # Stop charging if no ammo
                return None
            
                        # Fire at target
            current_time = now
            self.last_shot = current_time
            
            # Reset charging state
            self.charging = False
            self.reload_start_time = current_time

            # Track burst for rapid-fire turrets
            if hasattr(self, 'burst_size'):
                self.burst_count += 1
                if self.burst_count >= self.burst_size:
                    self.reloading = True
                    self.reload_start = current_time

            # Trigger muzzle flash and recoil animations
            if hasattr(self, 'last_muzzle_flash'):
                self.last_muzzle_flash = current_time
            
            # Start recoil animation
            self.recoil_timer = current_time
            self.recoil_distance = 3  # pixels to recoil backward

            # Play turret shot sound effect
            self._play_shot_sound(turret_type)
            
            # Calculate projectile velocity towards target using game's ball speed
            from config import BALL_SPEED
            turret_center = pygame.Vector2(self.x + BLOCK_SIZE // 2, self.y + BLOCK_SIZE // 2)
            direction = (self.target - turret_center).normalize()
            
            # Apply accuracy-based spread to all turret types
            accuracy = getattr(self, 'accuracy', 0.3)
            spread_degrees = getattr(self, 'spread_degrees', 15)
            timing_variation = getattr(self, 'timing_variation', 0.2)
            
            # Calculate actual spread based on accuracy
            actual_spread = spread_degrees * (1 - accuracy)
            
            # DEBUG: Print accuracy values (comment out for release)
            # print(f"DEBUG: {turret_type} turret firing - accuracy:{accuracy:.2f}, spread_deg:{spread_degrees}, actual_spread:{actual_spread:.1f}")
            
            # Rapid turret keeps its position variation AND gets accuracy spread
            if turret_type == 'rapid':
                # Machine gun positional spread (always present)
                position_spread = 6
                direction = direction.rotate(random.uniform(-position_spread, position_spread))
                
            # Apply accuracy-based trajectory spread to all turrets
            if actual_spread > 0:
                direction = direction.rotate(random.uniform(-actual_spread, actual_spread))
            
            # Use the same speed as regular cannonballs
            # Heavy bombs start at normal speed but slow down faster due to friction (see ball.py)
            speed = BALL_SPEED
            velocity = direction * speed
            
            return {
                'pos': turret_center,
                'vel': velocity,
                'damage': self.damage,
                'color': getattr(self, 'projectile_color', WHITE),
                'turret_type': turret_type
            }
            
        return None
    
    def _find_target(self, enemies: List, player_wall: PlayerWall, castle_blocks: List = None) -> Optional[pygame.Vector2]:
        """Find the best target within range. Prefer castle blocks only."""
        turret_center = pygame.Vector2(self.x + BLOCK_SIZE // 2, self.y + BLOCK_SIZE // 2)
        closest_target = None
        closest_distance = float('inf')

        # ------------------------------------------------------------
        #  Target selection logic – prefer blocks **within range** but
        #  fall back to the nearest block overall so the turret always
        #  has something to track & fire at.  This prevents the "never
        #  fires" bug when the player builds turrets a little too far
        #  from the castle.
        # ------------------------------------------------------------
        if castle_blocks:
            for block in castle_blocks:
                if not hasattr(block, 'centerx'):
                    continue
                if getattr(block, 'width', 0) <= 0 or getattr(block, 'height', 0) <= 0:
                    continue
                block_center = pygame.Vector2(block.centerx, block.centery)
                distance = turret_center.distance_to(block_center)

                # First pass: look for **within–range** targets
                if distance <= self.range and distance < closest_distance:
                    closest_target = block_center
                    closest_distance = distance

            # Second pass fallback – pick *nearest* block even if out of range
            if closest_target is None:
                for block in castle_blocks:
                    if not hasattr(block, 'centerx'):
                        continue
                    block_center = pygame.Vector2(block.centerx, block.centery)
                    distance = turret_center.distance_to(block_center)
                    if distance < closest_distance:
                        closest_target = block_center
                        closest_distance = distance

        return closest_target
    
    def _update_rotation(self, dt_ms: int):
        """Update turret rotation to face target with smooth rotation."""
        if self.target:
            dx = self.target.x - (self.x + BLOCK_SIZE // 2)
            dy = self.target.y - (self.y + BLOCK_SIZE // 2)
            target_angle = math.degrees(math.atan2(dy, dx))
            
            # Smooth rotation - don't snap instantly
            angle_diff = target_angle - self.rotation
            
            # Normalize angle difference to [-180, 180]
            while angle_diff > 180:
                angle_diff -= 360
            while angle_diff < -180:
                angle_diff += 360
            
            # Rotate at a limited speed (degrees per second)
            max_rotation_speed = getattr(self, 'rotation_speed', 180)  # Use upgraded speed if available
            max_rotation_this_frame = max_rotation_speed * (dt_ms / 1000.0)
            
            if abs(angle_diff) <= max_rotation_this_frame:
                self.rotation = target_angle
            else:
                self.rotation += max_rotation_this_frame * (1 if angle_diff > 0 else -1)
                
            # Keep rotation in [0, 360) range
            self.rotation = self.rotation % 360
    
    def take_damage(self, damage: int):
        """Take damage from enemy attacks."""
        self.health = max(0, self.health - damage)
        if self.health <= 0:
            self.active = False
    
    def _play_shot_sound(self, turret_type: str):
        """Play appropriate shot sound for turret type."""
        try:
            # Import castle module to access shot sounds
            import castle as castle_module
            castle_module._prepare_shot_sounds()
            if not castle_module._SHOT_SOUNDS:
                return
            
            # Update volumes
            castle_module._update_cannon_sound_volumes()
            
            # Play appropriate sound based on turret type
            if turret_type == 'basic':
                # Normal pitch for basic turret
                sfx = castle_module._SHOT_SOUNDS.get('normal')
            elif turret_type == 'rapid':
                # Higher pitch, lighter sound for rapid fire
                sfx = castle_module._SHOT_SOUNDS.get('1.9') or castle_module._SHOT_SOUNDS.get('normal')
            elif turret_type == 'heavy':
                # Lower pitch for heavy turret
                sfx = castle_module._SHOT_SOUNDS.get('0.85') or castle_module._SHOT_SOUNDS.get('normal')
            else:
                sfx = castle_module._SHOT_SOUNDS.get('normal')
            
            if sfx:
                sfx.play()
        except Exception as e:
            # Fail silently if sound can't be played
            pass
    
    def draw(self, surface: pygame.Surface):
        """Draw the turret."""
        if not self.active:
            return
        
        # Calculate base position with recoil animation
        now = pygame.time.get_ticks()
        recoil_offset = pygame.Vector2(0, 0)
        
        # Apply recoil animation (turret moves backward briefly after firing)
        if hasattr(self, 'recoil_timer') and self.recoil_timer > 0:
            recoil_elapsed = now - self.recoil_timer
            recoil_duration = 200  # ms
            if recoil_elapsed < recoil_duration:
                # Calculate recoil progress (starts at 1, goes to 0)
                progress = 1 - (recoil_elapsed / recoil_duration)
                # Move turret backward along barrel direction
                angle_rad = math.radians(self.rotation)
                direction = pygame.Vector2(math.cos(angle_rad), math.sin(angle_rad))
                recoil_offset = -direction * (self.recoil_distance * progress)
            else:
                self.recoil_timer = 0  # Clear recoil timer
        
        center = pygame.Vector2(self.x + BLOCK_SIZE // 2, self.y + BLOCK_SIZE // 2) + recoil_offset
        
        # Use turret-specific colors or defaults
        base_color = getattr(self, 'turret_color', (100, 100, 120))
        barrel_color = getattr(self, 'barrel_color', (80, 80, 100))
        
        # Calculate highlight and shadow from base color
        highlight_color = tuple(min(255, c + 60) for c in base_color)
        shadow_color = tuple(max(0, c - 40) for c in base_color)
        
        # Draw larger square base (different from circular cannon base)
        base_size = int(BLOCK_SIZE * 0.7)  # Larger base
        base_rect = pygame.Rect(
            center.x - base_size // 2,
            center.y - base_size // 2,
            base_size,
            base_size
        )
        
        # Draw square base with better 3D effect
        pygame.draw.rect(surface, base_color, base_rect)
        # Top and left highlight
        pygame.draw.line(surface, highlight_color, base_rect.topleft, base_rect.topright, 2)
        pygame.draw.line(surface, highlight_color, base_rect.topleft, base_rect.bottomleft, 2)
        # Bottom and right shadow
        pygame.draw.line(surface, shadow_color, base_rect.bottomleft, base_rect.bottomright, 2)
        pygame.draw.line(surface, shadow_color, base_rect.topright, base_rect.bottomright, 2)
        
        # Always draw barrel (not just when targeting)
        angle_rad = math.radians(self.rotation)
        direction = pygame.Vector2(math.cos(angle_rad), math.sin(angle_rad))
        barrel_length = int(BLOCK_SIZE * 0.6)  # Longer, more visible barrel
        barrel_width = 8  # Wider barrel
        
        # Calculate barrel rectangle
        barrel_end = center + direction * barrel_length
        perp = direction.rotate(90).normalize() if direction.length() > 0 else pygame.Vector2(0, 1)
        half_width = perp * (barrel_width / 2)
        
        # Barrel corners
        p1 = center + half_width
        p2 = center - half_width
        p3 = barrel_end - half_width
        p4 = barrel_end + half_width
        
        # Draw barrel with 3D effect
        pygame.draw.polygon(surface, barrel_color, [p1, p2, p3, p4])
        pygame.draw.line(surface, highlight_color, p1, p4, 2)
        pygame.draw.line(surface, shadow_color, p2, p3, 2)
        
        # Draw barrel tip
        pygame.draw.circle(surface, shadow_color, (int(barrel_end.x), int(barrel_end.y)), barrel_width // 2)
        pygame.draw.circle(surface, barrel_color, (int(barrel_end.x), int(barrel_end.y)), barrel_width // 2 - 1)
        
        # Draw center pivot
        pygame.draw.circle(surface, shadow_color, (int(center.x), int(center.y)), 6)
        pygame.draw.circle(surface, base_color, (int(center.x), int(center.y)), 4)
        
        # Draw muzzle flash if recently fired
        if hasattr(self, 'last_muzzle_flash') and hasattr(self, 'muzzle_flash_color'):
            flash_duration = getattr(self, 'muzzle_flash_duration', 150)
            if pygame.time.get_ticks() - self.last_muzzle_flash < flash_duration:
                flash_size = int((flash_duration - (pygame.time.get_ticks() - self.last_muzzle_flash)) / flash_duration * 12)
                if flash_size > 0:
                    pygame.draw.circle(surface, self.muzzle_flash_color, (int(barrel_end.x), int(barrel_end.y)), flash_size)
                    pygame.draw.circle(surface, (255, 255, 255), (int(barrel_end.x), int(barrel_end.y)), flash_size // 2)
        
        # Draw charging animation for all turrets
        if hasattr(self, 'charging') and self.charging:
            charge_elapsed = now - self.charge_start_time
            charge_progress = min(1.0, charge_elapsed / self.charge_duration)
            
            # Charging ring around turret base
            ring_color = (255, int(255 * (0.5 + 0.5 * charge_progress)), 0)  # Orange to yellow
            ring_alpha = int(100 + 100 * charge_progress)
            ring_radius = int(BLOCK_SIZE * 0.4 * (0.5 + 0.5 * charge_progress))
            
            # Draw pulsing charge ring
            pulse = math.sin(now * 0.015) * 0.2 + 0.8
            final_radius = int(ring_radius * pulse)
            
            # Create a surface for alpha blending
            charge_surf = pygame.Surface((final_radius * 2 + 4, final_radius * 2 + 4), pygame.SRCALPHA)
            charge_color = (*ring_color, ring_alpha)
            pygame.draw.circle(charge_surf, charge_color, (final_radius + 2, final_radius + 2), final_radius, 2)
            
            # Blit to main surface
            charge_rect = charge_surf.get_rect(center=(int(center.x), int(center.y)))
            surface.blit(charge_surf, charge_rect)
        
        # Draw reload progress bar for non-rapid turrets
        if (not hasattr(self, 'reloading') or not self.reloading) and hasattr(self, 'reload_start_time'):
            reload_elapsed = now - self.reload_start_time  
            reload_progress = min(1.0, reload_elapsed / self.shot_cooldown)
            
            if reload_progress < 1.0:  # Still reloading
                bar_width = BLOCK_SIZE - 4
                bar_height = 4
                bar_x = int(center.x - bar_width // 2)
                bar_y = int(center.y + BLOCK_SIZE // 2 - 10)
                
                # Background bar
                pygame.draw.rect(surface, (100, 0, 0), (bar_x, bar_y, bar_width, bar_height))
                
                # Progress bar
                progress_width = int(bar_width * reload_progress)
                progress_color = (0, 255, 0) if reload_progress > 0.8 else (255, 255, 0) if reload_progress > 0.5 else (255, 100, 0)
                pygame.draw.rect(surface, progress_color, (bar_x, bar_y, progress_width, bar_height))
                
                # Border
                pygame.draw.rect(surface, (255, 255, 255), (bar_x, bar_y, bar_width, bar_height), 1)

        # Brief trajectory tracer right after firing (helps indicate aim)
        if hasattr(self, 'last_shot') and pygame.time.get_ticks() - self.last_shot < 120:
            tracer_len = int(BLOCK_SIZE * 0.9)
            tracer_end = center + direction * tracer_len
            tracer_color = (255, 255, 180)
            pygame.draw.line(surface, tracer_color, center, tracer_end, 2)
        
        # Heavy charge glow before firing
        if getattr(self, 'turret_type', '') == 'heavy':
            time_since_last = pygame.time.get_ticks() - getattr(self, 'last_shot', 0)
            # Show charge buildup for the last 500ms before cooldown ends
            if time_since_last < self.shot_cooldown and time_since_last > max(0, self.shot_cooldown - 500):
                phase = (self.shot_cooldown - time_since_last) / 500.0
                alpha = int(30 + 120 * phase)
                pulse = math.sin(pygame.time.get_ticks() * 0.02) * 0.3 + 0.7
                glow_size = int(BLOCK_SIZE * (0.6 + 0.4 * phase * pulse))
                glow = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
                center_glow = glow_size
                pygame.draw.circle(glow, (0, int(255 * pulse), 0, alpha), (center_glow, center_glow), glow_size)
                pygame.draw.circle(glow, (100, 255, 100, int(alpha * 0.5)), (center_glow, center_glow), int(glow_size * 0.7))
                surface.blit(glow, (center.x - center_glow, center.y - center_glow))

        # Rapid fire reload animation  
        if getattr(self, 'turret_type', '') == 'rapid' and getattr(self, 'reloading', False):
            now = pygame.time.get_ticks()
            reload_elapsed = now - getattr(self, 'reload_start', now)
            reload_duration = getattr(self, 'reload_cooldown', 3000)
            
            if reload_elapsed < reload_duration:
                # Calculate progress (0 to 1)
                progress = reload_elapsed / reload_duration
                
                # Draw reload circle animation
                circle_radius = int(BLOCK_SIZE * 0.4)
                # Draw background circle
                pygame.draw.circle(surface, (60, 60, 60), (int(center.x), int(center.y)), circle_radius, 3)
                
                # Draw progress arc
                if progress > 0:
                    start_angle = -math.pi / 2  # Start at top
                    end_angle = start_angle + (2 * math.pi * progress)
                    
                    # Create points for arc
                    points = [(int(center.x), int(center.y))]
                    for i in range(int(progress * 360) + 1):
                        angle = start_angle + (i / 360.0) * 2 * math.pi
                        x = center.x + circle_radius * math.cos(angle)
                        y = center.y + circle_radius * math.sin(angle)
                        points.append((int(x), int(y)))
                    
                    if len(points) > 2:
                        pygame.draw.polygon(surface, (255, 150, 0), points)
                        pygame.draw.circle(surface, (255, 200, 0), (int(center.x), int(center.y)), circle_radius, 2)
        
        # Draw health bar if damaged
        if self.health < self.max_health:
            bar_width = BLOCK_SIZE
            bar_height = 6
            bar_x = self.x
            bar_y = self.y - 12
            
            # Background
            pygame.draw.rect(surface, (60, 0, 0), (bar_x, bar_y, bar_width, bar_height))
            
            # Health
            health_width = int((self.health / self.max_health) * bar_width)
            pygame.draw.rect(surface, self.health_bar_color, (bar_x, bar_y, health_width, bar_height))
            
            # Border
            pygame.draw.rect(surface, WHITE, (bar_x, bar_y, bar_width, bar_height), 1)


class BasicTurret(Turret):
    """Basic turret with standard stats."""
    
    def __init__(self, x: int, y: int):
        super().__init__(x, y, "basic")
        self.shot_cooldown = 3000
        self.range = 220
        self.damage = 20
        self.rotation_speed = 120  # Base rotation speed for upgrades
        # Accuracy properties  
        self.accuracy = 0.2  # Low base accuracy - very inaccurate initially
        self.spread_degrees = 20  # High spread
        self.timing_variation = 0.3  # Poor timing consistency
        # Visual properties
        self.turret_color = (120, 120, 140)  # Blue-gray
        self.barrel_color = (90, 90, 110)
        self.projectile_color = WHITE
        self.muzzle_flash_color = (255, 255, 150)  # Yellow flash
        self.last_muzzle_flash = 0


class RapidTurret(Turret):
    """Fast-firing turret with lower damage."""
    
    def __init__(self, x: int, y: int):
        super().__init__(x, y, "rapid")
        self.shot_cooldown = 140
        self.range = 180
        # Balance tweak – each bullet counts as 0.25 block hit → 4 bullets per health
        # The castle damage routine scales fractional hits based on *damage* so we
        # lower the base damage to 10 to work with the (dmg*0.25)/10 formula.
        self.damage = 10
        self.rotation_speed = 180  # Faster rotation for rapid targeting
        
        # Accuracy properties (less accurate due to rapid fire)
        self.accuracy = 0.1  # Very low base accuracy for machine gun
        self.spread_degrees = 30  # Very high spread for machine gun effect
        self.timing_variation = 0.5  # High timing variation

        # --- Burst-fire specific state ------------------------------
        self.burst_size = 8          # rounds per burst
        self.burst_count = 0         # shots fired in current burst
        self.reload_cooldown = 5000  # ms to reload after a burst (3 seconds)
        self.reloading = False
        self.reload_start = 0        # timestamp when reload began
        self.charge_duration = 100     # ms to charge before firing
        # Visual properties
        self.turret_color = (140, 100, 100)   # Reddish
        self.barrel_color = (110, 70, 70)
        self.projectile_color = (255, 150, 150)  # Light red projectiles
        self.muzzle_flash_color = (255, 200, 100)  # Orange flash
        self.last_muzzle_flash = 0
        self.muzzle_flash_duration = 80  # Shorter flash for rapid fire


class HeavyTurret(Turret):
    """Slow but powerful turret."""
    
    def __init__(self, x: int, y: int):
        super().__init__(x, y, "heavy")
        self.shot_cooldown = 10000  # 10 second base reload time
        self.range = 260
        self.damage = 40
        self.max_health = 150  # More durable
        self.rotation_speed = 90   # Slower, more deliberate rotation
        
        # Accuracy properties (most accurate but slowest)
        self.accuracy = 0.3  # Moderate base accuracy for heavy artillery
        self.spread_degrees = 15  # Moderate spread for precision
        self.timing_variation = 0.2  # Decent timing consistency
        
        # Visual properties
        self.turret_color = (100, 140, 100)   # Greenish
        self.barrel_color = (70, 110, 70)
        self.projectile_color = (150, 255, 150)  # Light green projectiles
        self.muzzle_flash_color = (200, 255, 200)  # Green flash
        self.last_muzzle_flash = 0
        self.charge_particles = []
        self.is_charging = False


class BuildSystem:
    """Manages turret placement and building mechanics."""
    
    def __init__(self, player_wall: PlayerWall, store=None):
        self.player_wall = player_wall
        self.store = store  # Reference to store for upgrade levels
        self.turrets: List[Turret] = []
        self.buildable_area = self._calculate_buildable_area()
        self.selected_turret_type = "basic"
        self.placement_preview = None
        self.placement_valid = False
        
        # Turret costs
        self.turret_costs = {
            "basic": 50,
            "rapid": 75,
            "heavy": 100
        }
        
        # Turret types available
        self.available_turret_types = ["basic", "rapid", "heavy"]
        
    def _calculate_buildable_area(self) -> pygame.Rect:
        """Calculate the area where turrets can be placed."""
        # Buildable area is player wall + one tile above
        if self.player_wall.blocks:
            # Use the first block as reference
            first_block = self.player_wall.blocks[0]
            wall_rect = pygame.Rect(0, first_block.y, WIDTH, first_block.height * len(self.player_wall.blocks))
        else:
            # Fallback if no blocks exist
            wall_rect = pygame.Rect(0, HEIGHT - 2 * BLOCK_SIZE, WIDTH, 2 * BLOCK_SIZE)
        
        # Extend one tile above
        buildable_rect = pygame.Rect(
            wall_rect.x,
            wall_rect.y - BLOCK_SIZE,
            wall_rect.width,
            wall_rect.height + BLOCK_SIZE
        )
        
        return buildable_rect
    
    def can_place_turret(self, x: int, y: int) -> bool:
        """Check if a turret can be placed at the given position."""
        # Check if position is within buildable area
        if not self.buildable_area.collidepoint(x, y):
            return False
            
        # Check if position overlaps with existing turrets
        placement_rect = pygame.Rect(x, y, BLOCK_SIZE, BLOCK_SIZE)
        for turret in self.turrets:
            if placement_rect.colliderect(turret.rect):
                return False
                
        # Check if position overlaps with player wall blocks
        for block in self.player_wall.blocks:
            if placement_rect.colliderect(block):
                return False
        
        return True
    
    def get_placement_preview(self, mouse_pos: Tuple[int, int]) -> Tuple[bool, pygame.Rect]:
        """Get placement preview for mouse position."""
        # Snap to grid
        grid_x = (mouse_pos[0] // BLOCK_SIZE) * BLOCK_SIZE
        grid_y = (mouse_pos[1] // BLOCK_SIZE) * BLOCK_SIZE
        
        preview_rect = pygame.Rect(grid_x, grid_y, BLOCK_SIZE, BLOCK_SIZE)
        can_place = self.can_place_turret(grid_x, grid_y)
        
        return can_place, preview_rect
    
    def place_turret(self, x: int, y: int, turret_type: str) -> bool:
        """Place a turret at the given position. Returns True if successful."""
        if not self.can_place_turret(x, y):
            return False
            
        # Unlock ammo type when first turret is placed
        from ammo import unlock_type, get_ammo_by_type
        print(f"DEBUG: Placing {turret_type} turret at ({x}, {y})")
        print(f"DEBUG: Ammo before unlock: {get_ammo_by_type(turret_type)}")
        unlock_type(turret_type)
        print(f"DEBUG: Ammo after unlock: {get_ammo_by_type(turret_type)}")
            
        # Create turret based on type
        if turret_type == "basic":
            turret = BasicTurret(x, y)
        elif turret_type == "rapid":
            turret = RapidTurret(x, y)
        elif turret_type == "heavy":
            turret = HeavyTurret(x, y)
        else:
            return False
        
        # Apply store upgrades to the new turret
        self._apply_turret_upgrades(turret)
            
        self.turrets.append(turret)
        return True
    
    def _apply_turret_upgrades(self, turret):
        """Apply store upgrades to a turret."""
        if not self.store:
            return
            
        # Accuracy upgrade - improves rotation speed and reduces spread
        accuracy_level = self.store.get_turret_upgrade_level("turret_accuracy")
        if accuracy_level > 0:
            turret.rotation_speed = getattr(turret, 'rotation_speed', 180) * (1 + accuracy_level * 0.3)
            # Improve accuracy and reduce spread
            turret.accuracy = min(1.0, getattr(turret, 'accuracy', 0.3) + accuracy_level * 0.2)
            turret.spread_degrees = max(2, getattr(turret, 'spread_degrees', 15) * (1 - accuracy_level * 0.3))
            turret.timing_variation = max(0.05, getattr(turret, 'timing_variation', 0.2) * (1 - accuracy_level * 0.4))
        
        # Reload upgrade - reduces shot cooldown and reload cooldown for rapid fire
        reload_level = self.store.get_turret_upgrade_level("turret_reload")
        if reload_level > 0:
            turret.shot_cooldown = int(turret.shot_cooldown * (1 - reload_level * 0.15))
            # Also apply to rapid fire reload cooldown (burst reload time)
            if hasattr(turret, 'reload_cooldown'):
                turret.reload_cooldown = int(turret.reload_cooldown * (1 - reload_level * 0.15))
        
        # Damage upgrade - increases damage
        damage_level = self.store.get_turret_upgrade_level("turret_damage")
        if damage_level > 0:
            turret.damage = int(turret.damage * (1 + damage_level * 0.25))
        
        # Range upgrade - extends targeting range
        range_level = self.store.get_turret_upgrade_level("turret_range")
        if range_level > 0:
            turret.range = int(turret.range * (1 + range_level * 0.2))
        
        # Health upgrade - increases durability
        health_level = self.store.get_turret_upgrade_level("turret_health")
        if health_level > 0:
            turret.max_health = int(turret.max_health * (1 + health_level * 0.3))
            turret.health = turret.max_health  # Start at full health
    
    def get_placement_preview(self, mouse_pos: Tuple[int, int]) -> Tuple[bool, pygame.Rect]:
        """Get placement preview rectangle and validity for given position."""
        from config import BLOCK_SIZE
        
        # Snap to grid
        grid_x = (mouse_pos[0] // BLOCK_SIZE) * BLOCK_SIZE
        grid_y = (mouse_pos[1] // BLOCK_SIZE) * BLOCK_SIZE
        
        # Create preview rectangle
        preview_rect = pygame.Rect(grid_x, grid_y, BLOCK_SIZE, BLOCK_SIZE)
        
        # Check if placement is valid
        is_valid = self.can_place_turret(grid_x, grid_y)
        
        print(f"BuildSystem.get_placement_preview: pos={mouse_pos} -> grid=({grid_x}, {grid_y}), valid={is_valid}")
        
        return is_valid, preview_rect
    
    def get_turret_cost(self, turret_type: str) -> int:
        """Get the cost of a turret type."""
        return self.turret_costs.get(turret_type, 0)
    
    def update(self, dt_ms: int, enemies: List, player_wall: PlayerWall, castle_blocks: List = None) -> List[dict]:
        """Update all turrets and return list of projectile data."""
        projectiles = []
        
        for turret in self.turrets[:]:  # Copy list to allow removal during iteration
            if not turret.active:
                self.turrets.remove(turret)
                continue
                
            projectile_data = turret.update(dt_ms, enemies, player_wall, castle_blocks)
            if projectile_data:
                projectiles.append(projectile_data)
        
        return projectiles
    
    def draw(self, surface: pygame.Surface, show_buildable_area: bool = False):
        """Draw all turrets and buildable area highlight."""
        # Only show buildable area when explicitly requested (during build menu)
        if show_buildable_area:
            # Draw buildable area highlight (semi-transparent)
            highlight_surface = pygame.Surface((self.buildable_area.width, self.buildable_area.height))
            highlight_surface.set_alpha(50)
            highlight_surface.fill((0, 255, 0))  # Green highlight
            surface.blit(highlight_surface, self.buildable_area.topleft)
            
            # Draw buildable area border
            pygame.draw.rect(surface, (0, 200, 0), self.buildable_area, 2)
        
        # Draw all turrets
        for turret in self.turrets:
            turret.draw(surface)
    
    def get_turret_cost(self, turret_type: str) -> int:
        """Get the cost of a turret type."""
        return self.turret_costs.get(turret_type, 0)
    
    def get_total_turret_count(self) -> int:
        """Get the total number of active turrets."""
        return len(self.turrets)
