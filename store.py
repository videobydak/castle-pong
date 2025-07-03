import pygame, random, math
from typing import Dict, List, Optional, Tuple, Any
from config import WIDTH, HEIGHT, SCALE
import coin

# -----------------------------------------------------------------------------
# Store System - Tabbed interface for purchasing upgrades between waves
# -----------------------------------------------------------------------------

class StoreUpgrade:
    """Represents a single upgrade item in the store."""
    
    def __init__(self, id: str, name: str, description: str, cost: int, max_level: int = 1, 
                 upgrade_type: str = "single", cost_multiplier: float = 1.5):
        self.id = id
        self.name = name
        self.description = description
        self.base_cost = cost
        self.max_level = max_level
        self.current_level = 0
        self.upgrade_type = upgrade_type  # "single", "tiered", "consumable"
        self.cost_multiplier = cost_multiplier
        self.purchased = False

    def get_current_cost(self) -> int:
        """Calculate cost for next level based on current progress."""
        if self.upgrade_type == "consumable":
            return self.base_cost
        elif self.upgrade_type == "tiered":
            return int(self.base_cost * (self.cost_multiplier ** self.current_level))
        else:  # single
            return self.base_cost if not self.purchased else 0

    def can_purchase(self) -> bool:
        """Check if this upgrade can be purchased."""
        if self.upgrade_type == "single":
            return not self.purchased
        elif self.upgrade_type == "tiered":
            return self.current_level < self.max_level
        else:  # consumable
            return True

    def purchase(self) -> bool:
        """Attempt to purchase this upgrade. Returns True if successful."""
        if not self.can_purchase():
            return False
        
        cost = self.get_current_cost()
        if coin.spend_coins(cost):
            if self.upgrade_type == "single":
                self.purchased = True
                self.current_level = 1
            elif self.upgrade_type == "tiered":
                self.current_level += 1
            else:  # consumable
                self.current_level += 1  # Track total purchases for display
            return True
        return False


class Store:
    """Main store interface with tabbed navigation."""
    
    def __init__(self):
        self.active = False
        self.current_tab = 0
        self.scroll_offset = 0
        self.tab_names = ["Defense", "Power", "Mystical", "Utility"]
        
        # Store state tracking
        self.wave_number = 1
        self.player_upgrades = {}  # id -> current_level or purchase_count
        
        # Initialize all upgrades
        self.upgrades = self._initialize_upgrades()
        
        # UI state
        self.hover_item = None
        self.button_hover_states = {}
        
        # Purchase effect particles
        self.purchase_particles = []
        
        # Sound effects
        self.purchase_sound = None
        self.error_sound = None
        self._load_sounds()

    def _load_sounds(self):
        """Load store sound effects."""
        try:
            self.purchase_sound = pygame.mixer.Sound("Sound Response - 8 Bit Jingles - Glide up Win.wav")
            self.purchase_sound.set_volume(0.6)
        except pygame.error:
            pass
        
        try:
            self.error_sound = pygame.mixer.Sound("Sound Response - 8 Bit Retro - Slide Down Game Over.wav")
            self.error_sound.set_volume(0.3)
        except pygame.error:
            pass

    def _initialize_upgrades(self) -> Dict[str, List[StoreUpgrade]]:
        """Create all store upgrades organized by category."""
        upgrades = {
            "Defense": [
                StoreUpgrade("paddle_heal", "Healer's Balm", 
                           "Restore your paddle to full length", 15, 1, "consumable"),
                StoreUpgrade("wall_repair", "Stone Mason's Kit", 
                           "Repair damaged castle wall blocks", 25, 1, "consumable"),
                StoreUpgrade("wall_layer1", "Apprentice Fortification", 
                           "Upgrade castle wall from rubble to basic stone", 40, 1, "single"),
                StoreUpgrade("wall_layer2", "Master Stonework", 
                           "Upgrade castle wall from stone to reinforced blocks", 80, 1, "single"),
                StoreUpgrade("wall_layer3", "Legendary Masonry", 
                           "Upgrade castle wall to impenetrable fortress grade", 150, 1, "single"),
                StoreUpgrade("extra_life", "Phoenix Feather", 
                           "Grants one extra chance when the wall breaks", 100, 3, "tiered"),
                StoreUpgrade("repair_drone", "Golem Servant", 
                           "Deploy an automaton that slowly repairs wall damage", 120, 1, "single"),
                StoreUpgrade("fire_resistance", "Wet Paddle Charm", 
                           "Reduces fireball damage to your paddle by half", 60, 1, "single"),
            ],
            "Power": [
                StoreUpgrade("paddle_width", "Giant's Grip", 
                           "Permanently widen your paddle for better deflection", 50, 5, "tiered"),
                StoreUpgrade("paddle_agility", "Wind Walker's Grace", 
                           "Reduce paddle inertia for snappier movement", 45, 3, "tiered"),
                StoreUpgrade("coin_boost", "Fortune's Favor", 
                           "Increase coins earned per block destroyed", 70, 4, "tiered"),
                StoreUpgrade("ball_magnetism", "Lodestone Aura", 
                           "Your paddle attracts coins from greater distance", 55, 1, "single"),
                StoreUpgrade("multi_ball", "Mirror's Edge", 
                           "Next cannonball splits into two upon impact", 90, 1, "consumable"),
                StoreUpgrade("power_shot", "Titan's Might", 
                           "Next three shots pierce through multiple blocks", 75, 1, "consumable"),
            ],
            "Mystical": [
                StoreUpgrade("coin_multiplier", "Midas Touch", 
                           "Temporarily double all coin drops for this wave", 80, 1, "consumable"),
                StoreUpgrade("time_slow", "Chronos Blessing", 
                           "Slow down time for 10 seconds when activated", 95, 1, "consumable"),
                StoreUpgrade("lucky_charm", "Rabbit's Foot", 
                           "Increase heart drop chance for this wave", 40, 1, "consumable"),
                StoreUpgrade("shield_barrier", "Arcane Ward", 
                           "Creates magical barrier that stops enemy projectiles", 110, 1, "consumable"),
                StoreUpgrade("block_vision", "Oracle's Sight", 
                           "Reveals weak points in castle blocks for bonus damage", 65, 1, "consumable"),
                StoreUpgrade("ghost_paddle", "Spectral Form", 
                           "Paddle becomes ethereal, passing through enemy shots", 85, 1, "consumable"),
            ],
            "Utility": [
                StoreUpgrade("auto_collect", "Treasure Hunter's Instinct", 
                           "Automatically collect coins when cannonball gets close", 70, 3, "tiered"),
                StoreUpgrade("coin_radius", "Merchant's Reach", 
                           "Increase coin collection range significantly", 50, 1, "single"),
                StoreUpgrade("score_bonus", "Glory Seeker's Pride", 
                           "Earn bonus points for stylish block destruction", 35, 3, "tiered"),
                StoreUpgrade("wave_preview", "Strategic Foresight", 
                           "See preview of next wave's castle layout", 60, 1, "single"),
                StoreUpgrade("emergency_heal", "Angel's Grace", 
                           "Automatically heal when paddle becomes critically small", 90, 2, "tiered"),
                StoreUpgrade("coin_magnet", "Prospector's Dream", 
                           "All coins slowly drift toward your paddle", 75, 1, "single"),
            ]
        }
        return upgrades

    def open_store(self, wave_number: int):
        """Open the store interface."""
        self.active = True
        self.wave_number = wave_number
        self.current_tab = 0
        self.scroll_offset = 0
        self.hover_item = None

    def close_store(self):
        """Close the store interface."""
        self.active = False

    def handle_event(self, event: pygame.event.Event):
        """Handle store input events."""
        if not self.active:
            return False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_store()
                return True
            elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                self.current_tab = (self.current_tab - 1) % len(self.tab_names)
                self.scroll_offset = 0
                return True
            elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                self.current_tab = (self.current_tab + 1) % len(self.tab_names)
                self.scroll_offset = 0
                return True
            elif event.key == pygame.K_UP or event.key == pygame.K_w:
                self.scroll_offset = max(0, self.scroll_offset - 1)
                return True
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                max_scroll = max(0, len(self.upgrades[self.tab_names[self.current_tab]]) - 6)
                self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                return True
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # left click
                return self._handle_click(event.pos)
        
        elif event.type == pygame.MOUSEMOTION:
            self._handle_hover(event.pos)
        
        return False

    def _handle_click(self, pos: Tuple[int, int]) -> bool:
        """Handle mouse clicks in the store."""
        mouse_x, mouse_y = pos
        
        # Check tab clicks
        tab_y = HEIGHT // 6
        tab_width = WIDTH // len(self.tab_names)
        for i, tab_name in enumerate(self.tab_names):
            tab_x = i * tab_width
            if tab_x <= mouse_x <= tab_x + tab_width and tab_y - 30 <= mouse_y <= tab_y:
                self.current_tab = i
                self.scroll_offset = 0
                return True
        
        # Check upgrade purchase clicks
        store_rect = pygame.Rect(WIDTH // 8, HEIGHT // 4, WIDTH * 3 // 4, HEIGHT // 2)
        if store_rect.collidepoint(pos):
            current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
            item_height = 60
            
            for i, upgrade in enumerate(current_upgrades[self.scroll_offset:self.scroll_offset + 6]):
                item_y = store_rect.y + i * item_height
                buy_button_rect = pygame.Rect(store_rect.right - 100, item_y + 5, 90, 30)
                
                if buy_button_rect.collidepoint(pos) and upgrade.can_purchase():
                    if upgrade.purchase():
                        self._apply_upgrade_effect(upgrade)
                        self._create_purchase_particles(buy_button_rect.center)
                        if self.purchase_sound:
                            self.purchase_sound.play()
                        return True
                    else:
                        if self.error_sound:
                            self.error_sound.play()
                        return True
        
        # Check close button
        close_button = pygame.Rect(WIDTH - 100, 50, 80, 40)
        if close_button.collidepoint(pos):
            self.close_store()
            return True
        
        return False

    def _handle_hover(self, pos: Tuple[int, int]):
        """Handle mouse hover for UI feedback."""
        mouse_x, mouse_y = pos
        self.hover_item = None
        
        # Check upgrade hover
        store_rect = pygame.Rect(WIDTH // 8, HEIGHT // 4, WIDTH * 3 // 4, HEIGHT // 2)
        if store_rect.collidepoint(pos):
            current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
            item_height = 60
            
            for i, upgrade in enumerate(current_upgrades[self.scroll_offset:self.scroll_offset + 6]):
                item_y = store_rect.y + i * item_height
                if item_y <= mouse_y <= item_y + item_height:
                    self.hover_item = upgrade
                    break

    def _apply_upgrade_effect(self, upgrade: StoreUpgrade):
        """Apply the effect of a purchased upgrade to the game."""
        # Track the purchase
        if upgrade.id not in self.player_upgrades:
            self.player_upgrades[upgrade.id] = 0
        self.player_upgrades[upgrade.id] += 1
        
        # Apply specific upgrade effects immediately for consumables
        if upgrade.upgrade_type == "consumable":
            try:
                from upgrade_effects import apply_consumable_upgrades
                # We'll need to get game state from somewhere - for now this is a placeholder
                # The main game loop will handle this
                pass
            except ImportError:
                pass

    def _create_purchase_particles(self, center: Tuple[int, int]):
        """Create particle effect for successful purchase."""
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 6)
            vel_x = math.cos(angle) * speed
            vel_y = math.sin(angle) * speed
            
            particle = {
                'x': center[0] + random.uniform(-10, 10),
                'y': center[1] + random.uniform(-10, 10),
                'vel_x': vel_x,
                'vel_y': vel_y,
                'life': 60,
                'max_life': 60,
                'color': (255, 215, 0)  # gold
            }
            self.purchase_particles.append(particle)

    def update(self, dt_ms: int):
        """Update store animations and effects."""
        if not self.active:
            return
        
        # Update purchase particles
        for particle in self.purchase_particles[:]:
            particle['x'] += particle['vel_x']
            particle['y'] += particle['vel_y']
            particle['vel_y'] += 0.2  # gravity
            particle['life'] -= 1
            
            if particle['life'] <= 0:
                self.purchase_particles.remove(particle)

    def draw(self, screen: pygame.Surface):
        """Draw the store interface."""
        if not self.active:
            return
        
        # Semi-transparent overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # Main store window
        store_rect = pygame.Rect(WIDTH // 8, HEIGHT // 6, WIDTH * 3 // 4, HEIGHT * 2 // 3)
        pygame.draw.rect(screen, (40, 40, 60), store_rect)
        pygame.draw.rect(screen, (255, 255, 255), store_rect, 3)
        
        # Title
        title_font = pygame.font.SysFont(None, 48, bold=True)
        title_text = title_font.render(f"⚔ ARMORY ⚔ - Wave {self.wave_number}", True, (255, 215, 0))
        title_rect = title_text.get_rect(center=(WIDTH // 2, store_rect.y + 30))
        screen.blit(title_text, title_rect)
        
        # Coin display
        coin_font = pygame.font.SysFont(None, 36, bold=True)
        coin_text = coin_font.render(f"Coins: {coin.get_coin_count()}", True, (255, 215, 0))
        screen.blit(coin_text, (store_rect.x + 20, store_rect.y + 60))
        
        # Tabs
        self._draw_tabs(screen, store_rect)
        
        # Current tab content
        self._draw_tab_content(screen, store_rect)
        
        # Instructions
        instruction_font = pygame.font.SysFont(None, 24)
        instructions = [
            "Arrow Keys / WASD: Navigate | Click: Purchase | ESC: Close",
            "Single: One-time purchase | Tiered: Multiple levels | Consumable: Use per wave"
        ]
        for i, instruction in enumerate(instructions):
            instruction_text = instruction_font.render(instruction, True, (200, 200, 200))
            screen.blit(instruction_text, (store_rect.x + 20, store_rect.bottom - 40 + i * 20))
        
        # Close button
        close_button = pygame.Rect(WIDTH - 100, 50, 80, 40)
        pygame.draw.rect(screen, (150, 50, 50), close_button)
        pygame.draw.rect(screen, (255, 255, 255), close_button, 2)
        close_font = pygame.font.SysFont(None, 32, bold=True)
        close_text = close_font.render("CLOSE", True, (255, 255, 255))
        close_rect = close_text.get_rect(center=close_button.center)
        screen.blit(close_text, close_rect)
        
        # Purchase particles
        for particle in self.purchase_particles:
            alpha = int(255 * (particle['life'] / particle['max_life']))
            color = (*particle['color'], alpha)
            size = max(1, int(4 * (particle['life'] / particle['max_life'])))
            
            particle_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(particle_surf, color, (size, size), size)
            screen.blit(particle_surf, (particle['x'] - size, particle['y'] - size))

    def _draw_tabs(self, screen: pygame.Surface, store_rect: pygame.Rect):
        """Draw the tab navigation."""
        tab_y = store_rect.y + 80
        tab_width = store_rect.width // len(self.tab_names)
        tab_font = pygame.font.SysFont(None, 32, bold=True)
        
        for i, tab_name in enumerate(self.tab_names):
            tab_x = store_rect.x + i * tab_width
            tab_rect = pygame.Rect(tab_x, tab_y, tab_width, 40)
            
            # Tab background
            if i == self.current_tab:
                pygame.draw.rect(screen, (80, 80, 120), tab_rect)
            else:
                pygame.draw.rect(screen, (60, 60, 80), tab_rect)
            
            pygame.draw.rect(screen, (255, 255, 255), tab_rect, 2)
            
            # Tab text
            tab_text = tab_font.render(tab_name, True, (255, 255, 255))
            tab_text_rect = tab_text.get_rect(center=tab_rect.center)
            screen.blit(tab_text, tab_text_rect)

    def _draw_tab_content(self, screen: pygame.Surface, store_rect: pygame.Rect):
        """Draw the content of the current tab."""
        content_rect = pygame.Rect(store_rect.x + 20, store_rect.y + 140, 
                                 store_rect.width - 40, store_rect.height - 200)
        
        current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
        item_height = 60
        
        # Draw upgrades
        for i, upgrade in enumerate(current_upgrades[self.scroll_offset:self.scroll_offset + 6]):
            item_y = content_rect.y + i * item_height
            item_rect = pygame.Rect(content_rect.x, item_y, content_rect.width, item_height - 5)
            
            # Item background
            if upgrade == self.hover_item:
                pygame.draw.rect(screen, (70, 70, 100), item_rect)
            else:
                pygame.draw.rect(screen, (50, 50, 70), item_rect)
            
            pygame.draw.rect(screen, (255, 255, 255), item_rect, 1)
            
            # Item details
            self._draw_upgrade_item(screen, item_rect, upgrade)
        
        # Scroll indicators
        if self.scroll_offset > 0:
            arrow_up = "▲ More above"
            up_text = pygame.font.SysFont(None, 24).render(arrow_up, True, (255, 255, 255))
            screen.blit(up_text, (content_rect.centerx - up_text.get_width()//2, content_rect.y - 25))
        
        if self.scroll_offset + 6 < len(current_upgrades):
            arrow_down = "▼ More below"
            down_text = pygame.font.SysFont(None, 24).render(arrow_down, True, (255, 255, 255))
            screen.blit(down_text, (content_rect.centerx - down_text.get_width()//2, content_rect.bottom + 5))

    def _draw_upgrade_item(self, screen: pygame.Surface, item_rect: pygame.Rect, upgrade: StoreUpgrade):
        """Draw a single upgrade item."""
        # Name
        name_font = pygame.font.SysFont(None, 32, bold=True)
        name_color = (255, 215, 0) if upgrade.can_purchase() else (128, 128, 128)
        name_text = name_font.render(upgrade.name, True, name_color)
        screen.blit(name_text, (item_rect.x + 10, item_rect.y + 5))
        
        # Description
        desc_font = pygame.font.SysFont(None, 24)
        desc_text = desc_font.render(upgrade.description, True, (200, 200, 200))
        screen.blit(desc_text, (item_rect.x + 10, item_rect.y + 28))
        
        # Level/status indicator
        if upgrade.upgrade_type == "tiered":
            level_text = f"Level {upgrade.current_level}/{upgrade.max_level}"
        elif upgrade.upgrade_type == "single":
            level_text = "OWNED" if upgrade.purchased else "AVAILABLE"
        else:  # consumable
            level_text = f"Used {upgrade.current_level} times"
        
        level_font = pygame.font.SysFont(None, 20)
        level_surface = level_font.render(level_text, True, (150, 150, 150))
        screen.blit(level_surface, (item_rect.x + 10, item_rect.bottom - 18))
        
        # Price and buy button
        if upgrade.can_purchase():
            cost = upgrade.get_current_cost()
            buy_button_rect = pygame.Rect(item_rect.right - 100, item_rect.y + 5, 90, 30)
            
            # Button color based on affordability
            can_afford = coin.get_coin_count() >= cost
            button_color = (50, 150, 50) if can_afford else (150, 50, 50)
            
            pygame.draw.rect(screen, button_color, buy_button_rect)
            pygame.draw.rect(screen, (255, 255, 255), buy_button_rect, 2)
            
            # Button text
            buy_font = pygame.font.SysFont(None, 24, bold=True)
            buy_text = buy_font.render(f"{cost}", True, (255, 255, 255))
            buy_rect = buy_text.get_rect(center=buy_button_rect.center)
            screen.blit(buy_text, buy_rect)
        else:
            # Show "MAX" or "OWNED"
            status_text = "MAX" if upgrade.upgrade_type == "tiered" else "OWNED"
            status_font = pygame.font.SysFont(None, 24, bold=True)
            status_surface = status_font.render(status_text, True, (100, 100, 100))
            screen.blit(status_surface, (item_rect.right - 100, item_rect.y + 15))

    def get_upgrade_level(self, upgrade_id: str) -> int:
        """Get the current level/count for an upgrade."""
        return self.player_upgrades.get(upgrade_id, 0)

    def has_upgrade(self, upgrade_id: str) -> bool:
        """Check if player owns a specific upgrade."""
        return self.player_upgrades.get(upgrade_id, 0) > 0


# Global store instance
_store = Store()

def get_store() -> Store:
    """Get the global store instance."""
    return _store