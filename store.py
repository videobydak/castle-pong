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
        
        # Game state references for applying effects
        self.game_state = None
        
        # Initialize all upgrades
        self.upgrades = self._initialize_upgrades()
        
        # UI state
        self.hover_item = None
        self.button_hover_states = {}
        
        # Pixel font (PressStart2P)
        self.pixel_font_title  = self._load_pixel_font(36)
        self.pixel_font_large  = self._load_pixel_font(28)
        self.pixel_font_medium = self._load_pixel_font(20)
        self.pixel_font_small  = self._load_pixel_font(14)
        
        # Feedback messages (fading)
        self.feedback_msgs = []  # list[dict{text,color,life,max_life}]
        
        # Purchase effect particles
        self.purchase_particles = []
        
        # Sound effects
        self.purchase_sound = None
        self.error_sound = None
        self._load_sounds()

        # How many upgrade items fit on screen at once
        self.items_per_page = 5

        # Visual tuning
        self.item_height = 80  # vertical space per upgrade row

        # Track selected item for keyboard navigation
        self.selected_item = 0

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

    def _load_pixel_font(self, size: int):
        """Load bundled PressStart2P font or fallback to monospace."""
        import os
        pix_path = 'PressStart2P-Regular.ttf'
        if os.path.isfile(pix_path):
            try:
                # Ensure pygame font module is ready (Store may be imported before pygame.init())
                if not pygame.font.get_init():
                    try:
                        pygame.font.init()
                    except Exception:
                        pass
                return pygame.font.Font(pix_path, size)
            except Exception:
                pass
        return pygame.font.SysFont('Courier New', size, bold=True)

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
        self.selected_item = 0
        self.hover_item = None
        # Recompute how many upgrade rows fit on screen with current item_height
        store_height = HEIGHT * 2 // 3
        content_height = store_height - 200
        self.items_per_page = max(1, content_height // self.item_height)

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
                self.selected_item = 0
                return True
            elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                self.current_tab = (self.current_tab + 1) % len(self.tab_names)
                self.scroll_offset = 0
                self.selected_item = 0
                return True
            elif event.key == pygame.K_UP or event.key == pygame.K_w:
                if self.selected_item > 0:
                    self.selected_item -= 1
                else:
                    # If at top, scroll up if possible
                    if self.scroll_offset > 0:
                        self.scroll_offset -= 1
                    # else wrap to last visible item
                    else:
                        current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
                        visible = min(self.items_per_page, len(current_upgrades) - self.scroll_offset)
                        self.selected_item = max(visible - 1, 0)
                return True
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
                visible = min(self.items_per_page, len(current_upgrades) - self.scroll_offset)
                if self.selected_item < visible - 1:
                    self.selected_item += 1
                else:
                    # If at bottom, scroll down if possible
                    max_scroll = max(0, len(current_upgrades) - self.items_per_page)
                    if self.scroll_offset < max_scroll:
                        self.scroll_offset += 1
                    # else wrap to first item
                    else:
                        self.selected_item = 0
                return True
            elif event.key == pygame.K_SPACE:
                # Attempt to purchase selected item
                current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
                idx = self.scroll_offset + self.selected_item
                if 0 <= idx < len(current_upgrades):
                    upgrade = current_upgrades[idx]
                    if upgrade.can_purchase():
                        if upgrade.purchase():
                            self._apply_upgrade_effect(upgrade)
                            # Find the item_rect for the selected item to spawn particles
                            store_rect = pygame.Rect(WIDTH // 8, HEIGHT // 6, WIDTH * 3 // 4, HEIGHT * 2 // 3)
                            content_rect = pygame.Rect(store_rect.x + 20, store_rect.y + 140, store_rect.width - 40, store_rect.height - 200)
                            item_y = content_rect.y + self.selected_item * self.item_height
                            buy_button_rect = pygame.Rect(content_rect.right - 100, item_y + 5, 90, 30)
                            self._create_purchase_particles(buy_button_rect.center)
                            if self.purchase_sound:
                                self.purchase_sound.play()
                            self._add_feedback("Purchased!", (80, 200, 80))
                        else:
                            if self.error_sound:
                                self.error_sound.play()
                            self._add_feedback("Not enough coins!", (220, 80, 80))
                    else:
                        if self.error_sound:
                            self.error_sound.play()
                        self._add_feedback("Cannot purchase!", (220, 80, 80))
                return True
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # left click
                return self._handle_click(event.pos)
        
        elif event.type == pygame.MOUSEMOTION:
            self._handle_hover(event.pos)
        
        elif event.type == pygame.MOUSEWHEEL:
            # Scroll list with mouse wheel (pygame uses y: +1 up, -1 down)
            if event.y > 0:
                self.scroll_offset = max(0, self.scroll_offset - 1)
                self.selected_item = 0
            elif event.y < 0:
                max_scroll = max(0, len(self.upgrades[self.tab_names[self.current_tab]]) - self.items_per_page)
                self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                self.selected_item = 0
            return True
        
        return False

    def _handle_click(self, pos: Tuple[int, int]) -> bool:
        """Handle mouse clicks in the store."""
        mouse_x, mouse_y = pos
        
        # Calculate the same rect values that are used inside the draw() method so
        # the clickable areas line-up perfectly with what the player sees.
        store_rect = pygame.Rect(WIDTH // 8, HEIGHT // 6, WIDTH * 3 // 4, HEIGHT * 2 // 3)
        tab_y = store_rect.y + 80  # matches _draw_tabs()
        tab_height = 40
        tab_width = store_rect.width // len(self.tab_names)
        
        # Check tab clicks
        for i, _ in enumerate(self.tab_names):
            tab_x = store_rect.x + i * tab_width
            if tab_x <= mouse_x <= tab_x + tab_width and tab_y <= mouse_y <= tab_y + tab_height:
                self.current_tab = i
                self.scroll_offset = 0
                return True
        
        # Check upgrade purchase clicks
        if store_rect.collidepoint(pos):
            # Recreate the content_rect used in drawing to ensure hitboxes match visuals
            content_rect = pygame.Rect(store_rect.x + 20, store_rect.y + 140,
                                      store_rect.width - 40, store_rect.height - 200)

            current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
            item_height = self.item_height

            for i, upgrade in enumerate(current_upgrades[self.scroll_offset:self.scroll_offset + self.items_per_page]):
                item_y = content_rect.y + i * item_height
                buy_button_rect = pygame.Rect(content_rect.right - 100, item_y + 5, 90, 30)

                if buy_button_rect.collidepoint(pos) and upgrade.can_purchase():
                    if upgrade.purchase():
                        self._apply_upgrade_effect(upgrade)
                        self._create_purchase_particles(buy_button_rect.center)
                        if self.purchase_sound:
                            self.purchase_sound.play()
                        self._add_feedback("Purchased!", (80, 200, 80))
                        return True
                    else:
                        if self.error_sound:
                            self.error_sound.play()
                        self._add_feedback("Not enough coins!", (220, 80, 80))
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
        store_rect = pygame.Rect(WIDTH // 8, HEIGHT // 6, WIDTH * 3 // 4, HEIGHT * 2 // 3)
        content_rect = pygame.Rect(store_rect.x + 20, store_rect.y + 140,
                                   store_rect.width - 40, store_rect.height - 200)
        if content_rect.collidepoint(pos):
            current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
            item_height = self.item_height
            
            for i, upgrade in enumerate(current_upgrades[self.scroll_offset:self.scroll_offset + self.items_per_page]):
                item_y = content_rect.y + i * item_height
                if item_y <= mouse_y <= item_y + item_height:
                    self.hover_item = upgrade
                    break

    def _apply_upgrade_effect(self, upgrade: StoreUpgrade):
        """Apply the effect of a purchased upgrade to the game."""
        # Track the purchase
        if upgrade.id not in self.player_upgrades:
            self.player_upgrades[upgrade.id] = 0
        self.player_upgrades[upgrade.id] += 1
        
        # Apply specific upgrade effects immediately if we have game state
        if self.game_state:
            try:
                from upgrade_effects import apply_consumable_upgrades, apply_single_upgrades, apply_tiered_upgrades
                
                paddles = self.game_state['paddles']
                player_wall = self.game_state['player_wall']
                castle = self.game_state['castle']
                
                if upgrade.upgrade_type == "consumable":
                    apply_consumable_upgrades(self, upgrade.id, paddles, player_wall, castle)
                elif upgrade.upgrade_type == "single":
                    apply_single_upgrades(self, upgrade.id, paddles, player_wall, castle)
                elif upgrade.upgrade_type == "tiered":
                    level = self.player_upgrades[upgrade.id]
                    apply_tiered_upgrades(self, upgrade.id, level, paddles, player_wall, castle)
                    
            except ImportError:
                print(f"Warning: Could not import upgrade effects for {upgrade.id}")

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

        # Update feedback messages
        for msg in self.feedback_msgs[:]:
            msg['life'] -= 1
            if msg['life'] <= 0:
                self.feedback_msgs.remove(msg)

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
        title_text = self.pixel_font_title.render(f"ARMORY - Wave {self.wave_number}", True, (255, 215, 0))
        title_rect = title_text.get_rect(center=(WIDTH // 2, store_rect.y + 30))
        screen.blit(title_text, title_rect)
        
        # Coin display
        coin_text = self.pixel_font_medium.render(f"Coins: {coin.get_coin_count()}", True, (255, 215, 0))
        screen.blit(coin_text, (store_rect.x + 20, store_rect.y + 60))
        
        # Tabs
        self._draw_tabs(screen, store_rect)
        
        # Current tab content
        self._draw_tab_content(screen, store_rect)
        
        # Instructions
        instruction_font = self.pixel_font_small
        instructions = [
            "Scroll / Arrows / Click Tabs to Navigate  |  Click Cost to Buy  |  ESC to Close",
            "Single: One-time  |  Tiered: Multi-level  |  Consumable: Wave Use"
        ]
        for i, instruction in enumerate(instructions):
            instruction_text = instruction_font.render(instruction, True, (200, 200, 200))
            screen.blit(instruction_text, (store_rect.x + 20, store_rect.bottom - 40 + i * 20))
        
        # Draw feedback messages (fade out)
        for idx, msg in enumerate(self.feedback_msgs):
            alpha = int(255 * (msg['life'] / msg['max_life']))
            txt_surf = self.pixel_font_medium.render(msg['text'], True, msg['color'])
            txt_surf.set_alpha(alpha)
            txt_rect = txt_surf.get_rect(center=(WIDTH // 2, store_rect.bottom - 70 - idx * 30))
            screen.blit(txt_surf, txt_rect)
        
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
        tab_font = self.pixel_font_medium
        
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
        item_height = self.item_height
        
        # Draw upgrades
        for i, upgrade in enumerate(current_upgrades[self.scroll_offset:self.scroll_offset + self.items_per_page]):
            item_y = content_rect.y + i * item_height
            item_rect = pygame.Rect(content_rect.x, item_y, content_rect.width, item_height - 5)
            
            # Item background
            if upgrade == self.hover_item or i == self.selected_item:
                pygame.draw.rect(screen, (100, 100, 140), item_rect)
                pygame.draw.rect(screen, (255, 215, 0), item_rect, 3)  # gold border for selected
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
        
        if self.scroll_offset + self.items_per_page < len(current_upgrades):
            arrow_down = "▼ More below"
            down_text = pygame.font.SysFont(None, 24).render(arrow_down, True, (255, 255, 255))
            screen.blit(down_text, (content_rect.centerx - down_text.get_width()//2, content_rect.bottom + 5))

    def _draw_upgrade_item(self, screen: pygame.Surface, item_rect: pygame.Rect, upgrade: StoreUpgrade):
        """Draw a single upgrade item."""
        # Name using pixel font
        name_color = (255, 215, 0) if upgrade.can_purchase() else (128, 128, 128)
        max_name_w = item_rect.width - 120
        display_name = self._truncate_text(self.pixel_font_large, upgrade.name, max_name_w)
        name_text = self.pixel_font_large.render(display_name, True, name_color)
        screen.blit(name_text, (item_rect.x + 10, item_rect.y + 8))
        
        # Description smaller pixel font
        desc_color = (200, 200, 200)
        max_desc_w = item_rect.width - 120
        display_desc = self._truncate_text(self.pixel_font_small, upgrade.description, max_desc_w)
        desc_text = self.pixel_font_small.render(display_desc, True, desc_color)
        screen.blit(desc_text, (item_rect.x + 10, item_rect.y + 38))
        
        # Level/status indicator
        if upgrade.upgrade_type == "tiered":
            level_text = f"Level {upgrade.current_level}/{upgrade.max_level}"
        elif upgrade.upgrade_type == "single":
            level_text = "OWNED" if upgrade.purchased else "AVAILABLE"
        else:  # consumable
            level_text = f"Used {upgrade.current_level} times"
        
        level_surface = self.pixel_font_small.render(level_text, True, (150, 150, 150))
        screen.blit(level_surface, (item_rect.x + 10, item_rect.bottom - 20))
        
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
            buy_text = self.pixel_font_small.render(f"{cost}", True, (255, 255, 255))
            buy_rect = buy_text.get_rect(center=buy_button_rect.center)
            screen.blit(buy_text, buy_rect)
        else:
            # Show "MAX" or "OWNED"
            status_text = "MAX" if upgrade.upgrade_type == "tiered" else "OWNED"
            status_surface = self.pixel_font_small.render(status_text, True, (100, 100, 100))
            screen.blit(status_surface, (item_rect.right - 100, item_rect.y + 15))

    def get_upgrade_level(self, upgrade_id: str) -> int:
        """Get the current level/count for an upgrade."""
        return self.player_upgrades.get(upgrade_id, 0)

    def has_upgrade(self, upgrade_id: str) -> bool:
        """Check if player owns a specific upgrade."""
        return self.player_upgrades.get(upgrade_id, 0) > 0

    def _add_feedback(self, text: str, color: Tuple[int,int,int]):
        """Add a temporary on-screen feedback message."""
        self.feedback_msgs.append({
            'text': text,
            'color': color,
            'life': 90,
            'max_life': 90,
        })

    def _truncate_text(self, font, text: str, max_width: int) -> str:
        """Return text truncated with ellipsis if it exceeds *max_width*."""
        if font.size(text)[0] <= max_width:
            return text
        ellipsis = "..."
        while text and font.size(text + ellipsis)[0] > max_width:
            text = text[:-1]
        return text + ellipsis

    def set_game_state(self, paddles, player_wall, castle):
        """Set game state references for applying effects."""
        self.game_state = {
            'paddles': paddles,
            'player_wall': player_wall,
            'castle': castle
        }


# Global store instance
_store = Store()

def get_store() -> Store:
    """Get the global store instance."""
    return _store