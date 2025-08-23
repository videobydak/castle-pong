import pygame, random, math
from typing import Dict, List, Optional, Tuple, Any
from config import WIDTH, HEIGHT, SCALE, WHITE, YELLOW, get_control_key
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
        self.tab_names = ["Restoration", "Upgrades", "Fortune", "Potions", "Turrets"]
        
        # Track whether store was opened automatically (wave transition) or manually (pause menu)
        self.opened_automatically = False
        
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
        self.items_per_page = 3  # Fixed 3 items per page

        # Visual tuning
        self.item_height = 80  # minimum vertical space per upgrade row

        # Track selected item for keyboard navigation
        self.selected_item = 0

    def _load_sounds(self):
        """Load store sound effects."""
        try:
            self.purchase_sound = pygame.mixer.Sound("Sound Response - 8 Bit Jingles - Glide up Win.wav")
            # Volume will be set by options menu
        except pygame.error:
            pass
        
        try:
            self.error_sound = pygame.mixer.Sound("Sound Response - 8 Bit Retro - Slide Down Game Over.wav")
            # Volume will be set by options menu
        except pygame.error:
            pass
    
    def _update_sound_volumes(self):
        """Update store sound volumes based on current settings."""
        try:
            import sys
            if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'options_menu'):
                options_menu = sys.modules['__main__'].options_menu
                if hasattr(options_menu, 'settings'):
                    if options_menu.settings.get('sfx_muted', False):
                        if self.purchase_sound:
                            self.purchase_sound.set_volume(0)
                        if self.error_sound:
                            self.error_sound.set_volume(0)
                    else:
                        sfx_vol = options_menu.settings.get('sfx_volume', 0.75)
                        if self.purchase_sound:
                            self.purchase_sound.set_volume(sfx_vol)
                        if self.error_sound:
                            self.error_sound.set_volume(sfx_vol * 0.5)  # Error sound is quieter
        except Exception as e:
            print(f"[Store] Failed to update sound volumes: {e}")

    def _load_pixel_font(self, size: int):
        """Load bundled PressStart2P font or fallback to monospace."""
        from utils import load_font
        return load_font('PressStart2P-Regular.ttf', size)

    def _initialize_upgrades(self) -> Dict[str, List[StoreUpgrade]]:
        """Create all store upgrades organized by category."""
        upgrades = {
            "Restoration": [
                StoreUpgrade("paddle_heal", "Healer's Balm", 
                           "Restore your paddle to full length", 15, 1, "consumable"),
                StoreUpgrade("wall_repair", "Stone Mason's Kit", 
                           "Repair damaged castle wall blocks", 25, 1, "consumable"),
                StoreUpgrade("repair_drone", "Golem Servant", 
                           "Deploy an automaton that slowly repairs wall damage", 120, 1, "single"),
                StoreUpgrade("emergency_heal", "Angel's Grace", 
                           "Automatically heal when paddle becomes critically small", 90, 2, "tiered"),
            ],
            "Upgrades": [
                StoreUpgrade("fortified_walls", "Fortified Walls", 
                           "Upgrade your castle wall to reinforced (level 1) and then fortress grade (level 2)", 60, 2, "tiered"),
                StoreUpgrade("paddle_width", "Giant's Grip", 
                           "Permanently widen your paddle for better deflection", 50, 5, "tiered"),
                StoreUpgrade("paddle_agility", "Wind Walker's Grace", 
                           "Reduce paddle inertia for snappier movement", 45, 3, "tiered"),
                StoreUpgrade("fire_resistance", "Wet Paddle Charm", 
                           "Grants complete immunity to red fireball damage", 60, 1, "single"),
            ],
            "Fortune": [
                StoreUpgrade("coin_multiplier", "Midas Touch", 
                           "Temporarily double all coin drops for this wave", 80, 1, "consumable"),
                StoreUpgrade("time_slow", "Chronos Blessing", 
                           "Slow down time for 10 seconds when activated", 95, 1, "consumable"),
                StoreUpgrade("lucky_charm", "Rabbit's Foot", 
                           "Increase heart drop chance for this wave", 40, 1, "consumable"),
                StoreUpgrade("coin_boost", "Fortune's Favor", 
                           "Increase coins earned per block destroyed", 70, 4, "tiered"),
                StoreUpgrade("lodestone_magnetism", "Lodestone Magnetism", 
                           "Coins are attracted to balls from a distance (level 1), from even farther (level 2), and will drift toward balls automatically (level 3)", 55, 3, "tiered"),
            ],
            "Potions": [
                StoreUpgrade("potion_widen", "Widen", 
                           "Unlocks the chance to spawn a Widen potion (enlarges paddle on pickup)", 40, 1, "single"),
                StoreUpgrade("potion_sticky", "Sticky", 
                           "Unlocks the chance to spawn a Sticky potion (balls stick to paddle until launched)", 35, 1, "single"),
                StoreUpgrade("potion_barrier", "Barrier", 
                           "Unlocks the chance to spawn a Barrier potion (temporary shield around playfield)", 50, 1, "single"),
                StoreUpgrade("potion_pierce", "Pierce", 
                           "Unlocks the chance to spawn a Pierce potion (balls pass through blocks)", 60, 1, "single"),
                StoreUpgrade("potion_through", "Alchemy", 
                           "Unlocks the chance to spawn an Alchemy potion (converts regular cannonballs into potions or fireballs when hit by the paddle)", 55, 1, "single"),
            ],
                            "Turrets": [
                    StoreUpgrade("turret_accuracy", "Targeting System",
                               "Improve turret accuracy and target acquisition speed", 45, 3, "tiered"),
                    StoreUpgrade("turret_reload", "Auto-Loader",
                               "Reduce turret reload time for faster firing", 50, 4, "tiered"),
                    StoreUpgrade("turret_damage", "Armor Piercing",
                               "Increase turret projectile damage", 60, 3, "tiered"),
                    StoreUpgrade("turret_range", "Long Range Optics",
                               "Extend turret targeting range", 55, 3, "tiered"),
                    StoreUpgrade("turret_health", "Reinforced Plating",
                               "Increase turret durability against enemy fire", 40, 3, "tiered"),
                    StoreUpgrade("ammo_basic", "Basic Ammo Pack",
                               "Purchase 25 rounds of basic ammunition", 15, 1, "consumable"),
                    StoreUpgrade("ammo_rapid", "Rapid Ammo Pack",
                               "Purchase 20 rounds of rapid-fire ammunition", 20, 1, "consumable"),
                    StoreUpgrade("ammo_heavy", "Heavy Ammo Pack",
                               "Purchase 10 rounds of heavy ammunition", 30, 1, "consumable"),
                    StoreUpgrade("ammo_bulk", "Bulk Ammo Crate",
                               "Purchase 50 rounds of general ammunition", 35, 1, "consumable"),
                ]
        }
        return upgrades

    def get_turret_upgrade_level(self, upgrade_id: str) -> int:
        """Get the current level of a turret upgrade."""
        return self.player_upgrades.get(upgrade_id, 0)

    def open_store(self, wave_number: int, automatic: bool = False):
        """Open the store interface."""
        self.active = True
        self.wave_number = wave_number
        self.current_tab = 0
        self.scroll_offset = 0
        self.selected_item = 0
        self.hover_item = None
        self.opened_automatically = automatic

    def close_store(self):
        """Close the store interface."""
        self.active = False
        
        # Return to appropriate menu based on how store was opened
        try:
            import sys
            _main = sys.modules['__main__']
            
            if self.opened_automatically:
                # Return to game (don't open pause menu)
                pass
            else:
                # Return to pause menu during gameplay
                if hasattr(_main, 'pause_menu'):
                    _main.pause_menu.active = True
        except Exception as e:
            print("[Store] Failed to return to appropriate menu:", e)
        
        # Reset the flag
        self.opened_automatically = False

    def handle_event(self, event: pygame.event.Event):
        """Handle store input events."""
        if not self.active:
            return False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_store()
                return True
            elif event.key == get_control_key('bottom_paddle_left'):
                self.current_tab = (self.current_tab - 1) % len(self.tab_names)
                self.scroll_offset = 0
                self.selected_item = 0
                return True
            elif event.key == get_control_key('bottom_paddle_right'):
                self.current_tab = (self.current_tab + 1) % len(self.tab_names)
                self.scroll_offset = 0
                self.selected_item = 0
                return True
            elif event.key == get_control_key('right_paddle_up'):
                if self.selected_item > 0:
                    self.selected_item -= 1
                else:
                    current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
                    if self.scroll_offset > 0:
                        self.scroll_offset -= 1
                        self.selected_item = self.items_per_page - 1
                    else:
                        max_pages = (len(current_upgrades) - 1) // self.items_per_page
                        self.scroll_offset = max_pages
                        self.selected_item = min(self.items_per_page - 1, len(current_upgrades) - 1 - (max_pages * self.items_per_page))
                return True
            elif event.key == get_control_key('right_paddle_down'):
                current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
                if self.selected_item < min(self.items_per_page - 1, len(current_upgrades) - 1 - (self.scroll_offset * self.items_per_page)):
                    self.selected_item += 1
                else:
                    max_pages = (len(current_upgrades) - 1) // self.items_per_page
                    if self.scroll_offset < max_pages:
                        self.scroll_offset += 1
                        self.selected_item = 0
                    else:
                        self.scroll_offset = 0
                        self.selected_item = 0
                return True
            elif event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                # Attempt to purchase selected item
                current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
                start_index = self.scroll_offset * self.items_per_page
                item_index = start_index + self.selected_item
                
                if 0 <= item_index < len(current_upgrades):
                    upgrade = current_upgrades[item_index]
                    if upgrade.can_purchase():
                        if upgrade.purchase():
                            self._apply_upgrade_effect(upgrade)
                            # Find the item_rect for the selected item to spawn particles
                            store_rect = pygame.Rect(WIDTH // 8, HEIGHT // 6, WIDTH * 3 // 4, HEIGHT * 2 // 3)
                            content_rect = pygame.Rect(store_rect.x + 20, store_rect.y + 140, store_rect.width - 40, store_rect.height - 200)
                            
                            # Calculate the position of the selected item
                            current_y = content_rect.y
                            for i in range(self.selected_item):
                                # Calculate item height for the item at this position
                                item = current_upgrades[start_index + i]
                                desc_lines = self._wrap_text(self.pixel_font_small, item.description, content_rect.width - 200)
                                desc_height = len(desc_lines) * 18
                                required_height = 8 + 30 + desc_height + 12 + 20 + 10
                                item_height = required_height
                                current_y += item_height
                            
                            buy_button_rect = pygame.Rect(content_rect.right - 100, current_y + 5, 90, 30)
                            self._create_purchase_particles(buy_button_rect.center)
                            if self.purchase_sound:
                                self._update_sound_volumes()
                                self.purchase_sound.play()
                            self._add_feedback("Purchased!", (80, 200, 80))
                        else:
                            if self.error_sound:
                                self._update_sound_volumes()
                                self.error_sound.play()
                            self._add_feedback("Not enough coins!", (220, 80, 80))
                    else:
                        if self.error_sound:
                            self._update_sound_volumes()
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
                current_upgrades = self.upgrades[self.tab_names[self.current_tab]]
                max_pages = (len(current_upgrades) - 1) // self.items_per_page
                self.scroll_offset = min(max_pages, self.scroll_offset + 1)
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
            
            # Fixed pagination: show exactly 3 items per page
            start_index = self.scroll_offset * self.items_per_page
            end_index = min(start_index + self.items_per_page, len(current_upgrades))
            items_to_show = current_upgrades[start_index:end_index]
            
            # Calculate item heights for the items we're showing
            item_heights = []
            for upgrade in items_to_show:
                desc_lines = self._wrap_text(self.pixel_font_small, upgrade.description, content_rect.width - 200)
                desc_height = len(desc_lines) * 18  # 18px per line
                required_height = 8 + 30 + desc_height + 12 + 20 + 10
                item_heights.append(required_height)

            # Check buy button clicks
            current_y = content_rect.y
            for i, upgrade in enumerate(items_to_show):
                item_height = item_heights[i]
                buy_button_rect = pygame.Rect(content_rect.right - 100, current_y + 5, 90, 30)

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
                
                current_y += item_height
        
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
            
            # Fixed pagination: show exactly 3 items per page
            start_index = self.scroll_offset * self.items_per_page
            end_index = min(start_index + self.items_per_page, len(current_upgrades))
            items_to_show = current_upgrades[start_index:end_index]
            
            # Calculate item heights for the items we're showing
            item_heights = []
            for upgrade in items_to_show:
                desc_lines = self._wrap_text(self.pixel_font_small, upgrade.description, content_rect.width - 200)
                desc_height = len(desc_lines) * 18  # 18px per line
                required_height = 8 + 30 + desc_height + 12 + 20 + 10
                item_heights.append(required_height)
            
            # Check hover on items
            current_y = content_rect.y
            for i, upgrade in enumerate(items_to_show):
                item_height = item_heights[i]
                if current_y <= mouse_y <= current_y + item_height:
                    self.hover_item = upgrade
                    break
                current_y += item_height

    def _apply_upgrade_effect(self, upgrade: StoreUpgrade):
        """Apply the effect of a purchased upgrade to the game."""
        # Track the purchase
        if upgrade.id not in self.player_upgrades:
            self.player_upgrades[upgrade.id] = 0
        self.player_upgrades[upgrade.id] += 1
        
        # Handle ammo purchases directly
        if upgrade.id.startswith("ammo_"):
            from ammo import add_ammo, unlock_type
            if upgrade.id == "ammo_basic":
                unlock_type('basic')
                add_ammo(25, "basic")
                self._add_feedback("Added 25 Basic Ammo!", (100, 255, 100))
            elif upgrade.id == "ammo_rapid":
                unlock_type('rapid')
                add_ammo(20, "rapid")
                self._add_feedback("Added 20 Rapid Ammo!", (100, 255, 100))
            elif upgrade.id == "ammo_heavy":
                unlock_type('heavy')
                add_ammo(10, "heavy")
                self._add_feedback("Added 10 Heavy Ammo!", (100, 255, 100))
            elif upgrade.id == "ammo_bulk":
                add_ammo(50)  # General ammo
                self._add_feedback("Added 50 General Ammo!", (100, 255, 100))
            return
        
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
        title_text = self.pixel_font_title.render(f"SHOP - Wave {self.wave_number}", True, (255, 215, 0))
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
        instruction_text = instruction_font.render("Arrow Keys to Navigate | Spacebar to Buy", True, (200, 200, 200))
        screen.blit(instruction_text, (store_rect.x + 20, store_rect.bottom - 40))
        
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
        close_text = self.pixel_font_small.render("CLOSE", True, (255, 255, 255))
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
        
        # Fixed pagination: show exactly 3 items per page
        start_index = self.scroll_offset * self.items_per_page
        end_index = min(start_index + self.items_per_page, len(current_upgrades))
        items_to_show = current_upgrades[start_index:end_index]
        
        # Calculate item heights for the items we're showing
        item_heights = []
        for upgrade in items_to_show:
            desc_lines = self._wrap_text(self.pixel_font_small, upgrade.description, content_rect.width - 200)
            desc_height = len(desc_lines) * 18  # 18px per line
            # Base height: 8 (name) + 30 (spacing) + desc_height + 12 (spacing) + 20 (level) + 10 (padding)
            required_height = 8 + 30 + desc_height + 12 + 20 + 10
            item_heights.append(required_height)
        
        # Draw upgrades with calculated heights
        current_y = content_rect.y
        for i, upgrade in enumerate(items_to_show):
            item_height = item_heights[i]
            item_rect = pygame.Rect(content_rect.x, current_y, content_rect.width, item_height - 5)
            
            # Item background
            if upgrade == self.hover_item or i == self.selected_item:
                pygame.draw.rect(screen, (100, 100, 140), item_rect)
                pygame.draw.rect(screen, (255, 215, 0), item_rect, 3)  # gold border for selected
            else:
                pygame.draw.rect(screen, (50, 50, 70), item_rect)
            
            pygame.draw.rect(screen, (255, 255, 255), item_rect, 1)
            
            # Item details
            self._draw_upgrade_item(screen, item_rect, upgrade)
            
            current_y += item_height
        
        # Scroll indicators with item ranges
        total_items = len(current_upgrades)
        if total_items > 0:
            start_item = start_index + 1
            end_item = end_index
            
            # Always show the current range below the last visible item
            range_text = f"{start_item} - {end_item} of {total_items}"
            range_text_surface = self.pixel_font_small.render(range_text, True, (200, 200, 200))
            # Position below the last visible item
            last_item_bottom = current_y
            screen.blit(range_text_surface, (content_rect.centerx - range_text_surface.get_width()//2, last_item_bottom + 10))

    def _draw_upgrade_item(self, screen: pygame.Surface, item_rect: pygame.Rect, upgrade: StoreUpgrade):
        """Draw a single upgrade item."""
        # Draw a single upgrade row (icon, name, description, cost, buy button)
        font = self.pixel_font_medium
        small_font = self.pixel_font_small
        
        # Calculate positions with proper spacing
        name_y = item_rect.y + 8
        desc_start_y = name_y + 30  # More space after name
        desc_line_height = 18
        
        # Name
        name_text = font.render(upgrade.name, True, (255, 255, 255))
        screen.blit(name_text, (item_rect.x + 10, name_y))
        
        # Description (multi-line wrap)
        desc_max_width = item_rect.width - 180
        desc_lines = self._wrap_text(small_font, upgrade.description, desc_max_width)
        
        # Calculate description height
        desc_height = len(desc_lines) * desc_line_height
        
        for i, line in enumerate(desc_lines):
            desc_text = small_font.render(line, True, (200, 200, 200))
            screen.blit(desc_text, (item_rect.x + 10, desc_start_y + i * desc_line_height))
        
        # Level/status indicator - position after description with spacing
        level_y = desc_start_y + desc_height + 12  # Extra spacing after description
        
        if upgrade.upgrade_type == "tiered":
            level_text = f"Level {upgrade.current_level}/{upgrade.max_level}"
        elif upgrade.upgrade_type == "single":
            level_text = "OWNED" if upgrade.purchased else "AVAILABLE"
        else:  # consumable
            level_text = f"Used {upgrade.current_level} times"
        
        level_surface = self.pixel_font_small.render(level_text, True, (150, 150, 150))
        screen.blit(level_surface, (item_rect.x + 10, level_y))
        
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

    def _wrap_text(self, font, text: str, max_width: int):
        # Wrap text into a list of lines that fit within max_width
        words = text.split()
        lines = []
        current = ''
        for word in words:
            test = current + (' ' if current else '') + word
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines



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