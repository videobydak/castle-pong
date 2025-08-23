import pygame
from typing import Optional, Tuple
from config import WIDTH, HEIGHT, WHITE, YELLOW, RED, GREEN, BLUE
from build_system import BuildSystem
from coin import get_coin_count, spend_coins

# -----------------------------------------------------------------------------
# Build Menu - Interface for placing turrets and defenses
# -----------------------------------------------------------------------------

class BuildMenu:
    """Build menu interface for placing turrets and defenses."""
    
    def __init__(self, build_system: BuildSystem):
        self.build_system = build_system
        self.active = False
        self.selected_turret_type = "basic"
        self.placement_mode = False
        self.placement_preview = None
        self.placement_valid = False
        self.show_menu_ui = True  # Controls whether to show the menu buttons
        
        # UI dimensions
        self.menu_width = 500  # Even larger to fit bigger buttons
        self.menu_height = 600  # Even larger to fit bigger buttons
        self.menu_x = (WIDTH - self.menu_width) // 2
        self.menu_y = (HEIGHT - self.menu_height) // 2
        
        # Button dimensions
        self.button_width = 200  # Much larger width for text
        self.button_height = 100  # Much larger height for text + cost
        self.button_spacing = 30  # Increased spacing for larger buttons
        
        # Turret type buttons
        self.turret_buttons = {}
        self._create_turret_buttons()
        
        # Action buttons
        self.action_buttons = {}
        self._create_action_buttons()
        
        # Font setup
        self.pixel_font_large = self._load_pixel_font(24)
        self.pixel_font_medium = self._load_pixel_font(18)
        self.pixel_font_small = self._load_pixel_font(14)
        
        # Hover states
        self.hover_turret_type = None
        self.hover_action = None
        
        # Keyboard navigation state
        self.selected_index = 0  # 0-2 for turrets, 3 for cancel button
        
        # Placement navigation state
        self.placement_grid_x = 0  # Grid position for keyboard placement
        self.placement_grid_y = 0
        
    def _load_pixel_font(self, size: int):
        """Load the pixel font at the specified size."""
        try:
            return pygame.font.Font("PressStart2P-Regular.ttf", size)
        except:
            return pygame.font.Font(None, size)
    
    def _create_turret_buttons(self):
        """Create turret type selection buttons."""
        button_y = self.menu_y + 140  # Moved down to account for coins display
        start_x = self.menu_x + (self.menu_width - self.button_width) // 2
        
        # Basic Turret
        self.turret_buttons["basic"] = {
            'rect': pygame.Rect(start_x, button_y, self.button_width, self.button_height),
            'name': "Basic Turret",
            'cost': 50,
            'description': "Standard turret with balanced stats"
        }
        
        # Rapid Turret
        button_y += self.button_height + 10
        self.turret_buttons["rapid"] = {
            'rect': pygame.Rect(start_x, button_y, self.button_width, self.button_height),
            'name': "Rapid Turret", 
            'cost': 75,
            'description': "Fast-firing with lower damage"
        }
        
        # Heavy Turret
        button_y += self.button_height + 10
        self.turret_buttons["heavy"] = {
            'rect': pygame.Rect(start_x, button_y, self.button_width, self.button_height),
            'name': "Heavy Turret",
            'cost': 100,
            'description': "Slow but powerful"
        }
    
    def _create_action_buttons(self):
        """Create action buttons - just Cancel."""
        button_y = self.menu_y + self.menu_height - 80  # Adjusted for larger menu
        
        # Cancel button (to close build menu)
        self.action_buttons["cancel"] = {
            'rect': pygame.Rect(self.menu_x + (self.menu_width - 100) // 2, button_y, 100, 50),
            'name': "Cancel"
        }
    
    def show(self):
        """Show the build menu."""
        self.active = True
        self.placement_mode = False
        self.show_menu_ui = True
        self.selected_turret_type = "basic"
        self.selected_index = 0  # Start with first turret selected
        # Don't initialize placement preview until we enter placement mode
        self.placement_preview = None
        self.placement_valid = False

    
    def hide(self):
        """Hide the build menu."""
        self.active = False
        self.placement_mode = False
        self.placement_preview = None
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events. Returns True if event was consumed."""
        if not self.active:
            return False
        
        # Debug: Print all events when build menu is active
        print(f"BuildMenu received event: {event.type} - {event}")
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = event.pos
                
                # Check turret type buttons - clicking selects turret type only
                for turret_type, button_data in self.turret_buttons.items():
                    if button_data['rect'].collidepoint(mouse_pos):
                        if not self.placement_mode:
                            # Click selects turret type, but doesn't enter placement mode
                            self.selected_turret_type = turret_type
                            # Update selected index to match
                            turret_types = list(self.turret_buttons.keys())
                            self.selected_index = turret_types.index(turret_type)
                        return True
                
                # Check action buttons
                for action, button_data in self.action_buttons.items():
                    if button_data['rect'].collidepoint(mouse_pos):
                        if action == "cancel":
                            self.hide()
                            return True
                
                # Mouse placement disabled - only keyboard placement allowed
                # if self.placement_mode:
                #     self._handle_placement_click(mouse_pos)
                #     return True
        
        elif event.type == pygame.MOUSEMOTION:
            if not self.placement_mode:  # Only update hover when not in placement mode
                # Update hover states for buttons
                self._update_hover_states(event.pos)
            # Completely ignore mouse motion during placement mode
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.placement_mode:
                    print("ESC: Canceling placement mode")
                    self.placement_mode = False
                    self.show_menu_ui = True  # Show menu again when canceling placement
                    self.placement_preview = None  # Clear preview explicitly
                    self.placement_valid = False
                else:
                    # Close build menu and return to end-of-wave screen
                    self.hide()
                return True
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                if self.placement_mode:
                    # Move placement cursor in placement mode
                    from config import WIDTH, HEIGHT, BLOCK_SIZE
                    max_grid_x = WIDTH // BLOCK_SIZE - 1
                    max_grid_y = HEIGHT // BLOCK_SIZE - 1
                    
                    old_x, old_y = self.placement_grid_x, self.placement_grid_y
                    
                    if event.key == pygame.K_LEFT:
                        self.placement_grid_x = max(0, self.placement_grid_x - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.placement_grid_x = min(max_grid_x, self.placement_grid_x + 1)
                    elif event.key == pygame.K_UP:
                        self.placement_grid_y = max(0, self.placement_grid_y - 1)
                    elif event.key == pygame.K_DOWN:
                        self.placement_grid_y = min(max_grid_y, self.placement_grid_y + 1)
                    
                    print(f"Arrow key pressed: grid moved from ({old_x}, {old_y}) to ({self.placement_grid_x}, {self.placement_grid_y})")
                    
                    # Update placement preview using keyboard grid position (no mouse)
                    print(f"Updating placement preview from keyboard")
                    self._update_placement_preview()
                else:
                    # Navigate between turrets and cancel button (0-3)
                    if event.key in (pygame.K_LEFT, pygame.K_UP):
                        self.selected_index = (self.selected_index - 1) % 4
                    else:
                        self.selected_index = (self.selected_index + 1) % 4
                    
                    # Update selected turret type if we're on a turret
                    if self.selected_index < 3:
                        turret_types = list(self.turret_buttons.keys())
                        self.selected_turret_type = turret_types[self.selected_index]
                return True
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                if self.placement_mode and self.placement_valid:
                    # Place turret at current grid position
                    from config import BLOCK_SIZE
                    grid_pixel_x = self.placement_grid_x * BLOCK_SIZE
                    grid_pixel_y = self.placement_grid_y * BLOCK_SIZE
                    print(f"Enter/Space pressed: attempting to place turret at grid ({self.placement_grid_x}, {self.placement_grid_y}) = pixel ({grid_pixel_x}, {grid_pixel_y})")
                    self._handle_placement_click((grid_pixel_x, grid_pixel_y))
                elif self.placement_mode and not self.placement_valid:
                    print("Enter/Space pressed but placement not valid")
                elif not self.placement_mode:
                    if self.selected_index == 3:  # Cancel button selected
                        self.hide()
                    elif self.selected_index < 3 and self._can_afford_turret(self.selected_turret_type):
                        # Enter placement mode if we can afford the turret
                        print(f"Entering placement mode for {self.selected_turret_type}")
                        self.placement_mode = True
                        # Hide the menu UI so player can see the game field
                        self.show_menu_ui = False
                        # Initialize placement grid to center of buildable area
                        from config import WIDTH, HEIGHT, BLOCK_SIZE
                        self.placement_grid_x = WIDTH // (2 * BLOCK_SIZE)  # Center of screen width
                        self.placement_grid_y = (HEIGHT - 3 * BLOCK_SIZE) // BLOCK_SIZE  # Near player wall
                        print(f"Initial placement grid: ({self.placement_grid_x}, {self.placement_grid_y})")
                        # Update preview using keyboard position (no mouse position)
                        self._update_placement_preview()
                return True
        
        return False
    
    def _can_afford_turret(self, turret_type: str) -> bool:
        """Check if player can afford the specified turret type."""
        turret_cost = self.build_system.get_turret_cost(turret_type)
        return get_coin_count() >= turret_cost
    
    def _handle_placement_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicking to place a turret."""
        if not self.placement_valid:
            return
        
        # Get grid position
        from config import BLOCK_SIZE
        grid_x = (mouse_pos[0] // BLOCK_SIZE) * BLOCK_SIZE
        grid_y = (mouse_pos[1] // BLOCK_SIZE) * BLOCK_SIZE
        
        # Check if we can afford the turret
        turret_cost = self.build_system.get_turret_cost(self.selected_turret_type)
        if get_coin_count() >= turret_cost:
            # Try to place the turret first
            if self.build_system.place_turret(grid_x, grid_y, self.selected_turret_type):
                # Success! Now spend the coins
                spend_coins(turret_cost)
                # Exit placement mode and auto-continue
                self.placement_mode = False
                self._update_placement_preview()
                # Auto-close build menu and continue to next wave
                self.hide()
            else:
                # Failed to place - don't spend coins
                print("Failed to place turret at", grid_x, grid_y)
        else:
            print("Not enough coins for turret")
    
    def _update_placement_preview(self, mouse_pos: Optional[Tuple[int, int]] = None):
        """Update the placement preview."""
        if not self.placement_mode:
            self.placement_preview = None
            self.placement_valid = False
            return
        
        # If no mouse position provided, use current grid position for keyboard navigation
        if mouse_pos is None:
            if hasattr(self, 'placement_grid_x') and hasattr(self, 'placement_grid_y'):
                from config import BLOCK_SIZE
                mouse_pos = (self.placement_grid_x * BLOCK_SIZE, self.placement_grid_y * BLOCK_SIZE)
                print(f"Using keyboard grid position: ({self.placement_grid_x}, {self.placement_grid_y}) -> {mouse_pos}")
            else:
                # Fallback to center of screen
                from config import WIDTH, HEIGHT
                mouse_pos = (WIDTH // 2, HEIGHT // 2)
                print(f"Using fallback center position: {mouse_pos}")
        
        # Get placement preview from build system
        print(f"Getting placement preview for position: {mouse_pos}")
        self.placement_valid, self.placement_preview = self.build_system.get_placement_preview(mouse_pos)
        print(f"Placement preview result: valid={self.placement_valid}, preview={self.placement_preview}")
    
    def _update_hover_states(self, mouse_pos: Tuple[int, int]):
        """Update hover states for buttons."""
        self.hover_turret_type = None
        self.hover_action = None
        
        # Check turret buttons
        for turret_type, button_data in self.turret_buttons.items():
            if button_data['rect'].collidepoint(mouse_pos):
                self.hover_turret_type = turret_type
                break
        
        # Check action buttons
        for action, button_data in self.action_buttons.items():
            if button_data['rect'].collidepoint(mouse_pos):
                self.hover_action = action
                break
    
    def update(self, dt_ms: int):
        """Update the build menu."""
        if not self.active:
            return
        
        # Don't continuously update placement preview - only update on keyboard input
        # The placement preview is updated by keyboard events in handle_event()
    
    def draw(self, surface: pygame.Surface):
        """Draw the build menu."""
        if not self.active:
            return
        
        # Debug output
        print(f"DEBUG: Drawing build menu - placement_mode={self.placement_mode}, show_menu_ui={self.show_menu_ui}")
        
        # Don't fill the screen - let the game scene show through
        
        # Draw build system overlay when in placement mode
        if self.placement_mode and self.build_system:
            self.build_system.draw(surface, show_buildable_area=True)
        
        # Only draw menu UI if not in placement mode or if show_menu_ui is True
        if self.show_menu_ui:
            # Draw menu background
            pygame.draw.rect(surface, (50, 50, 50), (self.menu_x, self.menu_y, self.menu_width, self.menu_height))
            pygame.draw.rect(surface, WHITE, (self.menu_x, self.menu_y, self.menu_width, self.menu_height), 2)
            
            # Draw title
            title_text = self.pixel_font_large.render("BUILD MENU", True, YELLOW)
            title_rect = title_text.get_rect(center=(self.menu_x + self.menu_width // 2, self.menu_y + 30))
            surface.blit(title_text, title_rect)
            
            # Draw current coins
            coins_text = f"Coins: {get_coin_count()}"
            coins_surf = self.pixel_font_medium.render(coins_text, True, YELLOW)
            coins_rect = coins_surf.get_rect(center=(self.menu_x + self.menu_width // 2, self.menu_y + 60))
            surface.blit(coins_surf, coins_rect)
            
            # Draw turret type buttons
            self._draw_turret_buttons(surface)
            
            # Draw action buttons
            self._draw_action_buttons(surface)
        
        # Draw placement preview if in placement mode
        if self.placement_mode and self.placement_preview:
            self._draw_placement_preview(surface)
    
    def _draw_turret_buttons(self, surface: pygame.Surface):
        """Draw turret type selection buttons."""
        turret_types = list(self.turret_buttons.keys())
        for i, (turret_type, button_data) in enumerate(self.turret_buttons.items()):
            rect = button_data['rect']
            is_hovered = (turret_type == self.hover_turret_type)
            is_keyboard_selected = (self.selected_index == i and not self.placement_mode)
            
            # Button background - keyboard selection takes priority over other states
            if is_keyboard_selected:
                bg_color = (255, 200, 0)  # Bright yellow for keyboard selection
                text_color = (0, 0, 0)
                border_color = (255, 255, 0)
                border_width = 4
            elif is_hovered:
                bg_color = (100, 100, 100)
                text_color = WHITE
                border_color = WHITE
                border_width = 2
            else:
                bg_color = (80, 80, 100)
                text_color = WHITE
                border_color = WHITE
                border_width = 2
            
            pygame.draw.rect(surface, bg_color, rect)
            pygame.draw.rect(surface, border_color, rect, border_width)
            
            # Button text - positioned higher to fit cost below
            text = self.pixel_font_small.render(button_data['name'], True, text_color)
            text_rect = text.get_rect(center=(rect.centerx, rect.centery - 15))
            surface.blit(text, text_rect)
            
            # Cost - positioned lower
            cost_color = RED if not self._can_afford_turret(turret_type) else YELLOW
            cost_text = self.pixel_font_small.render(f"{button_data['cost']} coins", True, cost_color)
            cost_rect = cost_text.get_rect(center=(rect.centerx, rect.centery + 15))
            surface.blit(cost_text, cost_rect)
    
    def _draw_action_buttons(self, surface: pygame.Surface):
        """Draw action buttons."""
        for action, button_data in self.action_buttons.items():
            rect = button_data['rect']
            is_hovered = (action == self.hover_action)
            is_keyboard_selected = (self.selected_index == 3 and action == "cancel" and not self.placement_mode)
            is_enabled = button_data.get('enabled', True)
            
            # Button background
            if is_keyboard_selected:
                bg_color = (255, 200, 0)  # Bright yellow for keyboard selection
                text_color = (0, 0, 0)
                border_color = (255, 255, 0)
                border_width = 4
            elif not is_enabled:
                bg_color = (60, 60, 60)
                text_color = (100, 100, 100)
                border_color = WHITE
                border_width = 2
            elif is_hovered:
                bg_color = (100, 100, 100)
                text_color = WHITE
                border_color = WHITE
                border_width = 2
            else:
                bg_color = (80, 80, 80)
                text_color = WHITE
                border_color = WHITE
                border_width = 2
            
            pygame.draw.rect(surface, bg_color, rect)
            pygame.draw.rect(surface, border_color, rect, border_width)
            
            # Button text
            text = self.pixel_font_small.render(button_data['name'], True, text_color)
            text_rect = text.get_rect(center=rect.center)
            surface.blit(text, text_rect)
    
    def _draw_placement_preview(self, surface: pygame.Surface):
        """Draw placement preview."""
        if not self.placement_preview:
            return
        
        # Draw preview rectangle with better visibility
        preview_color = GREEN if self.placement_valid else RED
        
        # Semi-transparent fill
        preview_surf = pygame.Surface((self.placement_preview.width, self.placement_preview.height))
        preview_surf.set_alpha(100)
        preview_surf.fill(preview_color)
        surface.blit(preview_surf, self.placement_preview.topleft)
        
        # Thick border
        pygame.draw.rect(surface, preview_color, self.placement_preview, 4)
        
        # Corner markers for better visibility
        corner_size = 8
        corners = [
            self.placement_preview.topleft,
            (self.placement_preview.topright[0] - corner_size, self.placement_preview.topright[1]),
            (self.placement_preview.bottomleft[0], self.placement_preview.bottomleft[1] - corner_size),
            (self.placement_preview.bottomright[0] - corner_size, self.placement_preview.bottomright[1] - corner_size)
        ]
        
        for corner in corners:
            pygame.draw.rect(surface, preview_color, (corner[0], corner[1], corner_size, corner_size))
        
        # Draw preview text with background
        preview_text = f"Place {self.turret_buttons[self.selected_turret_type]['name']}"
        if not self.placement_valid:
            preview_text += " (Invalid Location)"
            
        text_surf = self.pixel_font_small.render(preview_text, True, WHITE)
        text_rect = text_surf.get_rect(center=(self.placement_preview.centerx, self.placement_preview.centery - 30))
        
        # Text background
        bg_rect = text_rect.inflate(10, 4)
        pygame.draw.rect(surface, (0, 0, 0), bg_rect)
        pygame.draw.rect(surface, preview_color, bg_rect, 2)
        surface.blit(text_surf, text_rect)
        
        # Show keyboard controls hint
        if self.placement_mode:
            hint_text = "Arrow Keys: Move | Enter/Space: Place | Esc: Cancel"
            hint_surf = self.pixel_font_small.render(hint_text, True, WHITE)
            hint_rect = hint_surf.get_rect(center=(self.placement_preview.centerx, self.placement_preview.centery + 40))
            
            # Hint background
            hint_bg_rect = hint_rect.inflate(10, 4)
            pygame.draw.rect(surface, (0, 0, 0), hint_bg_rect)
            pygame.draw.rect(surface, YELLOW, hint_bg_rect, 1)
            surface.blit(hint_surf, hint_rect)
