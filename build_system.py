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
        
        # Visual properties
        self.color = WHITE
        self.border_color = YELLOW
        self.health_bar_color = GREEN
        
        # Animation properties
        self.recoil_timer = 0
        self.recoil_distance = 0
        
    def update(self, dt_ms: int, enemies: List, player_wall: PlayerWall, castle_blocks: List = None) -> Optional[dict]:
        """Update turret logic. Returns projectile data if firing."""
        if not self.active:
            return None
            
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
        
        # Only fire if we have a target, cooldown is ready, and ammo available
        if self.target and pygame.time.get_ticks() - self.last_shot > self.shot_cooldown:
            # Check if we have ammo
            from ammo import spend_ammo, get_ammo_by_type, get_ammo_count
            turret_type = getattr(self, 'turret_type', 'basic')
            
            # Debug ammo before spending
            type_ammo = get_ammo_by_type(turret_type)
            general_ammo = get_ammo_count()
            print(f"DEBUG FIRING: Turret {turret_type} has {type_ammo} type ammo, {general_ammo} general ammo")
            
            if not spend_ammo(1, turret_type):
                # No ammo available
                print(f"DEBUG FIRING: Turret {turret_type} FAILED to spend ammo")
                return None
            
            print(f"DEBUG FIRING: Turret {turret_type} successfully spent ammo, FIRING!")
            
            # Fire at target
            current_time = pygame.time.get_ticks()
            self.last_shot = current_time
            
            # Trigger muzzle flash and recoil
            if hasattr(self, 'last_muzzle_flash'):
                self.last_muzzle_flash = current_time
            self.recoil_timer = current_time
            self.recoil_distance = 3  # pixels to recoil backwards
            
            # Calculate projectile velocity towards target using game's ball speed
            from config import BALL_SPEED
            turret_center = pygame.Vector2(self.x + BLOCK_SIZE // 2, self.y + BLOCK_SIZE // 2)
            direction = (self.target - turret_center).normalize()
            
            # Rapid turret: add spread for machine-gun effect
            if turret_type == 'rapid':
                spread_deg = 6
                direction = direction.rotate(random.uniform(-spread_deg, spread_deg))
            
            # Use the same speed as regular cannonballs, but heavy slower
            speed = BALL_SPEED
            if turret_type == 'heavy':
                speed *= 0.6  # Much slower for heavy bombs
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
    
    def draw(self, surface: pygame.Surface):
        """Draw the turret."""
        if not self.active:
            return
        
        center = pygame.Vector2(self.x + BLOCK_SIZE // 2, self.y + BLOCK_SIZE // 2)
        
        # Apply recoil offset
        recoil_offset = pygame.Vector2(0, 0)
        if hasattr(self, 'recoil_timer') and pygame.time.get_ticks() - self.recoil_timer < 100:
            progress = (pygame.time.get_ticks() - self.recoil_timer) / 100.0
            recoil_amount = self.recoil_distance * (1.0 - progress)
            angle_rad = math.radians(self.rotation + 180)  # opposite direction
            recoil_offset = pygame.Vector2(math.cos(angle_rad), math.sin(angle_rad)) * recoil_amount
        
        center += recoil_offset
        
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
        self.shot_cooldown = 800
        self.range = 220
        self.damage = 20
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
        self.damage = 15
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
        self.shot_cooldown = 1400
        self.range = 260
        self.damage = 40
        self.max_health = 150  # More durable
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
            
        # Accuracy upgrade - improves rotation speed
        accuracy_level = self.store.get_turret_upgrade_level("turret_accuracy")
        if accuracy_level > 0:
            turret.rotation_speed = getattr(turret, 'rotation_speed', 180) * (1 + accuracy_level * 0.3)
        
        # Reload upgrade - reduces shot cooldown
        reload_level = self.store.get_turret_upgrade_level("turret_reload")
        if reload_level > 0:
            turret.shot_cooldown = int(turret.shot_cooldown * (1 - reload_level * 0.15))
        
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
