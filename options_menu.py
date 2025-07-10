import pygame
import sys
import os
import json
from config import (WIDTH, HEIGHT, WHITE, YELLOW, DEFAULT_CONTROLS, CURRENT_CONTROLS, 
                   CONTROL_DESCRIPTIONS, get_key_name, update_control_mapping, 
                   has_control_conflicts)

class OptionsMenu:
    """Options screen with volume controls, mute toggles, game settings, and control remapping."""
    
    def __init__(self):
        self.active = False
        self.bg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.bg.fill((0, 0, 0, 230))
        
        # Track whether options was opened from main menu or during gameplay
        self.opened_from_main_menu = False
        
        # Font setup
        self.title_font = self._load_pixel_font(96)
        self.btn_font = self._load_pixel_font(32)
        self.label_font = self._load_pixel_font(24)
        self.key_font = self._load_pixel_font(20)
        
        self.title_surf = self._render_outline("Options", self.title_font, YELLOW, (0, 0, 0), 2)
        self.title_rect = self.title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 6))
        
        # Settings storage
        self.settings = self._load_settings()
        
        # Control state
        #   nav_index 0  -> Tabs row
        #   nav_index 1..len(options)   -> option rows
        #   nav_index len(options)+1    -> Back button
        #   nav_index len(options)+2    -> Reset button
        self.nav_index = 1  # Start on first option row by default
        self.selected_option = 0  # Convenience cache for current option idx
        self.dragging_slider = None
        self.mouse_held = False
        
        # Control remapping state
        self.remapping_control = None  # Which control is being remapped
        self.remapping_start_time = 0
        
        # Current section ('audio', 'video', 'controls')
        self.current_section = 'audio'
        
        # Setup UI elements
        self._setup_ui_elements()
        # --- Scrolling state ---
        # When the controls section contains more options than can fit on screen,
        # we scroll the list vertically and keep the selected option visible.
        self.scroll_offset = 0  # Current vertical scroll offset in pixels
        self.max_scroll = 0     # Maximum allowed scroll based on content height

        # Establish initial scroll limits (after UI elements exist)
        self._update_scroll_limits()
    
    def _load_settings(self):
        """Load settings from file or create defaults."""
        default_settings = {
            'music_volume': 0.75,  # Changed from 0.6 to 0.75 (75%)
            'sfx_volume': 0.75,    # Changed from 0.4 to 0.75 (75%)
            'music_muted': False,
            'sfx_muted': False,
            'screen_shake': True,
            'show_fps': False,
            'controls': DEFAULT_CONTROLS.copy()
        }
        
        try:
            if os.path.exists('game_settings.json'):
                with open('game_settings.json', 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new settings
                    default_settings.update(loaded)
                    
                    # Update control mappings if they exist in the loaded settings
                    if 'controls' in loaded:
                        # Update global control mappings
                        for action, key in loaded['controls'].items():
                            if action in DEFAULT_CONTROLS:
                                update_control_mapping(action, key)
                    
        except Exception as e:
            print(f"[Options] Failed to load settings: {e}")
        
        return default_settings
    
    def _save_settings(self):
        """Save current settings to file."""
        try:
            # Include current control mappings in settings
            self.settings['controls'] = CURRENT_CONTROLS.copy()
            
            with open('game_settings.json', 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"[Options] Failed to save settings: {e}")
    
    def _setup_ui_elements(self):
        """Setup all UI elements with positions and rectangles."""
        # ---------- Tabs (size to text) ----------
        def _create_tab_rects(labels, y, padding=40, spacing=24):
            font = self.btn_font
            widths = [font.size(lbl)[0] + padding for lbl in labels]
            total = sum(widths) + spacing * (len(labels) - 1)
            start_x = WIDTH // 2 - total // 2
            rects = []
            x = start_x
            for w in widths:
                rects.append(pygame.Rect(x, y, w, 40))
                x += w + spacing
            return rects

        tab_y = self.title_rect.bottom + 30
        tab_labels = ['Audio', 'Video', 'Controls']
        tab_rects = _create_tab_rects(tab_labels, tab_y)

        self.tabs = {
            key: {'rect': r, 'label': lbl, 'hover': False}
            for key, r, lbl in zip(['audio', 'video', 'controls'], tab_rects, tab_labels)
        }
        
        # Setup options based on current section
        self._setup_section_options()
        
        # Back and Reset Buttons
        button_y = HEIGHT - 80
        self.back_button = {
            'rect': pygame.Rect(WIDTH//2 - 180, button_y, 170, 60),
            'label': 'Back',
            'hover': False
        }
        
        self.reset_button = {
            'rect': pygame.Rect(WIDTH//2 + 10, button_y, 200, 60),
            'label': 'Reset',
            'hover': False
        }
    
    def _setup_section_options(self):
        """Setup options for the current section."""
        self.options = []
        # Reset scroll when rebuilding the list (e.g., switching tabs)
        self.scroll_offset = 0
        start_y = max(tab['rect'].bottom for tab in self.tabs.values()) + 60
        
        if self.current_section == 'audio':
            # Music Volume Slider
            music_y = start_y
            self.options.append({
                'type': 'slider',
                'key': 'music_volume',
                'label': 'Music Volume',
                'rect': pygame.Rect(WIDTH//2 - 200, music_y, 400, 40),
                'slider_rect': pygame.Rect(WIDTH//2 - 150, music_y + 10, 300, 20),
                'label_rect': pygame.Rect(WIDTH//2 - 200, music_y - 30, 400, 25)
            })
            
            # Music Toggle
            mute_music_y = music_y + 70
            self.options.append({
                'type': 'toggle',
                'key': 'music_muted',
                'label': 'Music',
                'rect': pygame.Rect(WIDTH//2 - 100, mute_music_y, 200, 40),
                'label_rect': pygame.Rect(WIDTH//2 - 100, mute_music_y - 30, 200, 25)
            })
            
            # SFX Volume Slider
            sfx_y = mute_music_y + 80
            self.options.append({
                'type': 'slider',
                'key': 'sfx_volume',
                'label': 'SFX Volume',
                'rect': pygame.Rect(WIDTH//2 - 200, sfx_y, 400, 40),
                'slider_rect': pygame.Rect(WIDTH//2 - 150, sfx_y + 10, 300, 20),
                'label_rect': pygame.Rect(WIDTH//2 - 200, sfx_y - 30, 400, 25)
            })
            
            # SFX Toggle
            mute_sfx_y = sfx_y + 70
            self.options.append({
                'type': 'toggle',
                'key': 'sfx_muted',
                'label': 'SFX',
                'rect': pygame.Rect(WIDTH//2 - 100, mute_sfx_y, 200, 40),
                'label_rect': pygame.Rect(WIDTH//2 - 100, mute_sfx_y - 30, 200, 25)
            })
            
        elif self.current_section == 'video':
            # Screen Shake Toggle
            shake_y = start_y
            self.options.append({
                'type': 'toggle',
                'key': 'screen_shake',
                'label': 'Screen Shake',
                'rect': pygame.Rect(WIDTH//2 - 100, shake_y, 200, 40),
                'label_rect': pygame.Rect(WIDTH//2 - 100, shake_y - 30, 200, 25)
            })
            
            # Show FPS Toggle
            fps_y = shake_y + 80
            self.options.append({
                'type': 'toggle',
                'key': 'show_fps',
                'label': 'Show FPS',
                'rect': pygame.Rect(WIDTH//2 - 100, fps_y, 200, 40),
                'label_rect': pygame.Rect(WIDTH//2 - 100, fps_y - 30, 200, 25)
            })
            
        elif self.current_section == 'controls':
            # Control remapping buttons
            y_offset = start_y
            control_actions = [
                'bottom_paddle_left', 'bottom_paddle_right',
                'top_paddle_left', 'top_paddle_right',
                'left_paddle_up', 'left_paddle_down',
                'right_paddle_up', 'right_paddle_down',
                'bump_launch', 'pause_menu'
            ]
            
            for action in control_actions:
                self.options.append({
                    'type': 'control',
                    'key': action,
                    'label': CONTROL_DESCRIPTIONS[action],
                    'rect': pygame.Rect(WIDTH//2 - 200, y_offset, 400, 40),
                    'label_rect': pygame.Rect(WIDTH//2 - 200, y_offset - 25, 200, 25),
                    'key_rect': pygame.Rect(WIDTH//2 + 10, y_offset, 190, 40)
                })
                y_offset += 60

        # After rebuilding options, only reset nav_index if we were inside the list/buttons.
        if self.nav_index > 0:
            self.nav_index = 1  # first option row
            self.selected_option = 0

        # Recompute scrolling limits whenever the options list is (re)built.
        if hasattr(self, 'back_button'):
            self._update_scroll_limits()
            self._ensure_option_visible()

    # ---------------------------------------------------------------------
    # Scrolling helpers
    # ---------------------------------------------------------------------
    def _update_scroll_limits(self):
        """Recalculate max scroll based on content height in the controls section."""
        if self.current_section != 'controls' or not self.options:
            # No scrolling needed for other sections
            self.max_scroll = 0
            self.scroll_offset = 0
            return

        first_top = self.options[0]['rect'].top
        last_bottom = self.options[-1]['rect'].bottom

        # Visible vertical space between the options header and the Back button
        visible_top = max(tab['rect'].bottom for tab in self.tabs.values()) + 60
        if hasattr(self, 'back_button'):
            visible_bottom = self.back_button['rect'].top - 40
        else:
            visible_bottom = HEIGHT - 140  # Fallback prior to buttons being created

        visible_height = max(0, visible_bottom - visible_top)
        content_height = last_bottom - first_top
        self.max_scroll = max(0, content_height - visible_height)

        # Clamp current offset inside new range
        self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))

    def _ensure_option_visible(self):
        """Adjust scroll so the selected option remains within the visible window."""
        if self.current_section != 'controls':
            return

        # Only scroll when an actual option row (not tabs/back/reset) is selected
        if not (1 <= self.nav_index <= len(self.options)):
            return

        option = self.options[self.selected_option]
        option_top = option['rect'].top - self.scroll_offset
        option_bottom = option['rect'].bottom - self.scroll_offset

        visible_top = max(tab['rect'].bottom for tab in self.tabs.values()) + 60
        visible_bottom = self.back_button['rect'].top - 40

        if option_top < visible_top:
            # Scroll up
            self.scroll_offset = max(0, option['rect'].top - visible_top)
        elif option_bottom > visible_bottom:
            # Scroll down
            self.scroll_offset = min(self.max_scroll, option['rect'].bottom - visible_bottom)
    
    def open_options(self):
        """Open the options menu."""
        self.active = True
        self.selected_option = 0
        self.dragging_slider = None
        # Apply settings to ensure all volumes are up to date
        self._apply_settings()
        
        # Check if tutorial overlay (main menu) is active
        try:
            import sys
            _main = sys.modules['__main__']
            self.opened_from_main_menu = hasattr(_main, 'tutorial_overlay') and _main.tutorial_overlay.active
        except Exception as e:
            print("[OptionsMenu] Failed to check tutorial overlay state:", e)
            self.opened_from_main_menu = False
    
    def close_options(self):
        """Close the options menu and save settings."""
        self.active = False
        self._save_settings()
        self._apply_settings()
        
        # Return to appropriate menu based on where options was opened from
        try:
            import sys
            _main = sys.modules['__main__']
            
            if self.opened_from_main_menu:
                # Return to main menu (tutorial overlay)
                if hasattr(_main, 'tutorial_overlay'):
                    _main.tutorial_overlay.active = True
            else:
                # Return to pause menu during gameplay
                if hasattr(_main, 'pause_menu'):
                    _main.pause_menu.active = True
        except Exception as e:
            print("[OptionsMenu] Failed to return to appropriate menu:", e)
        
        # Reset the flag after using it
        self.opened_from_main_menu = False
    
    def reset_to_defaults(self):
        """Reset all settings to their default values."""
        if self.current_section == 'audio':
            self.settings['music_volume'] = 0.75
            self.settings['sfx_volume'] = 0.75
            self.settings['music_muted'] = False
            self.settings['sfx_muted'] = False
        elif self.current_section == 'video':
            self.settings['screen_shake'] = True
            self.settings['show_fps'] = False
        elif self.current_section == 'controls':
            # Reset control mappings
            for action, key in DEFAULT_CONTROLS.items():
                update_control_mapping(action, key)
            self.settings['controls'] = DEFAULT_CONTROLS.copy()
        
        self._apply_settings()
    
    def _apply_settings(self):
        """Apply current settings to the game systems."""
        # Apply music settings
        if self.settings['music_muted']:
            pygame.mixer.music.set_volume(0)
        else:
            pygame.mixer.music.set_volume(self.settings['music_volume'])
        
        # Apply SFX settings to all loaded sounds
        try:
            import sys
            main_module = sys.modules['__main__']
            if hasattr(main_module, 'sounds'):
                sfx_vol = 0 if self.settings['sfx_muted'] else self.settings['sfx_volume']
                for sound_name, sound in main_module.sounds.items():
                    if sound:  # Check if sound loaded successfully
                        # Apply 7% volume reduction to wall_break sound
                        if sound_name == 'wall_break':
                            adjusted_vol = sfx_vol * 0.93  # 7% quieter
                            sound.set_volume(adjusted_vol)
                        else:
                            sound.set_volume(sfx_vol)
            
            # Apply to coin sounds specifically
            if 'coin' in sys.modules:
                coin_module = sys.modules['coin']
                if hasattr(coin_module, 'update_coin_volumes'):
                    coin_module.update_coin_volumes()
            
            # Also apply to any other sound objects in various modules
            modules_to_check = ['heart', 'store', 'paddle_intro']
            for module_name in modules_to_check:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    # Look for sound attributes
                    for attr_name in dir(module):
                        if 'sound' in attr_name.lower():
                            attr = getattr(module, attr_name)
                            if hasattr(attr, 'set_volume'):
                                attr.set_volume(sfx_vol)
        except Exception as e:
            print(f"[Options] Failed to apply SFX volume: {e}")
    
    def update(self, events):
        """Handle input events for the options menu."""
        if not self.active:
            return False
        
        mouse_pos = pygame.mouse.get_pos()
        mouse_clicked = False
        mouse_released = False
        consumed_event = False
        
        # Handle control remapping
        if self.remapping_control:
            for event in events:
                if event.type == pygame.KEYDOWN:
                    # Cancel remapping with ESC
                    if event.key == pygame.K_ESCAPE:
                        self.remapping_control = None
                        consumed_event = True
                    else:
                        # Check for conflicts
                        conflicts = []
                        for action, key in CURRENT_CONTROLS.items():
                            if key == event.key and action != self.remapping_control:
                                conflicts.append(action)
                        
                        if conflicts:
                            # Show warning but still allow the mapping
                            print(f"[Options] Warning: Key {get_key_name(event.key)} already mapped to {conflicts}")
                        
                        # Update the control mapping
                        update_control_mapping(self.remapping_control, event.key)
                        self.remapping_control = None
                        consumed_event = True
                        
                        # Save settings immediately
                        self._save_settings()
                        break
            
            # If we're remapping, consume all events
            return True
        
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_clicked = True
                self.mouse_held = True
                consumed_event = True  # Consume all mouse clicks when active
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                mouse_released = True
                self.mouse_held = False
                self.dragging_slider = None
                consumed_event = True  # Consume all mouse releases when active
            elif event.type == pygame.KEYDOWN:
                consumed_event = True  # Consume all key presses when active
                from config import get_control_key
                KEY_UP = get_control_key('right_paddle_up')
                KEY_DOWN = get_control_key('right_paddle_down')
                KEY_LEFT = get_control_key('bottom_paddle_left')
                KEY_RIGHT = get_control_key('bottom_paddle_right')

                if event.key == pygame.K_ESCAPE:
                    self.close_options()
                elif event.key == KEY_UP:
                    # Move selection up (tabs ← options ← back ← reset)
                    total_rows = len(self.options) + 3  # tabs + options + back + reset
                    self.nav_index = (self.nav_index - 1) % total_rows
                    if self.nav_index == 0:
                        # Highlight tabs but keep same current section
                        pass
                    elif 1 <= self.nav_index <= len(self.options):
                        self.selected_option = self.nav_index - 1
                    # Back/Reset handled by drawing
                elif event.key == KEY_DOWN:
                    total_rows = len(self.options) + 3
                    self.nav_index = (self.nav_index + 1) % total_rows
                    if 1 <= self.nav_index <= len(self.options):
                        self.selected_option = self.nav_index - 1
                elif event.key == KEY_LEFT:
                    if self.nav_index == 0:
                        # Move tab selection left
                        sections = ['audio', 'video', 'controls']
                        idx = sections.index(self.current_section)
                        self.current_section = sections[(idx - 1) % len(sections)]
                        self._setup_section_options()
                    elif 1 <= self.nav_index <= len(self.options):
                        option = self.options[self.selected_option]
                        if option['type'] == 'control':
                            # Start remapping
                            self.remapping_control = option['key']
                            self.remapping_start_time = pygame.time.get_ticks()
                        else:
                            self._handle_left_arrow()
                    else:
                        # Navigating between Back and Reset buttons
                        if self.nav_index == len(self.options) + 2:  # Currently on Reset
                            self.nav_index -= 1  # Move to Back
                        # If already on Back, no action
                elif event.key == KEY_RIGHT:
                    if self.nav_index == 0:
                        sections = ['audio', 'video', 'controls']
                        idx = sections.index(self.current_section)
                        self.current_section = sections[(idx + 1) % len(sections)]
                        self._setup_section_options()
                    elif 1 <= self.nav_index <= len(self.options):
                        option = self.options[self.selected_option]
                        if option['type'] == 'control':
                            # Start remapping
                            self.remapping_control = option['key']
                            self.remapping_start_time = pygame.time.get_ticks()
                        else:
                            self._handle_right_arrow()
                    else:
                        # Navigating between Back and Reset buttons
                        if self.nav_index == len(self.options) + 1:  # Currently on Back
                            self.nav_index += 1  # Move to Reset
                        # If already on Reset, no action
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.nav_index == 0:
                        # Nothing to activate on tabs
                        pass
                    elif 1 <= self.nav_index <= len(self.options):
                        option = self.options[self.selected_option]
                        if option['type'] == 'control':
                            # Start remapping
                            self.remapping_control = option['key']
                            self.remapping_start_time = pygame.time.get_ticks()
                        else:
                            self._activate_selected()
                    else:
                        self._activate_selected()
                elif event.key == pygame.K_TAB:
                    # Tab between sections
                    sections = ['audio', 'video', 'controls']
                    current_index = sections.index(self.current_section)
                    next_index = (current_index + 1) % len(sections)
                    self.current_section = sections[next_index]
                    self._setup_section_options()
                    self.selected_option = 0
        
        # Handle mouse interactions
        if mouse_clicked:
            self._handle_mouse_click(mouse_pos)
        elif mouse_released:
            self.dragging_slider = None
        
        # Handle slider dragging
        if self.dragging_slider is not None and self.mouse_held:
            self._handle_slider_drag(mouse_pos)
        
        # Update hover states
        self._update_hover_states(mouse_pos)

        # Keep selected option in view after input handling
        self._ensure_option_visible()
        
        return consumed_event

    def _handle_mouse_click(self, mouse_pos):
        """Handle mouse clicks on options."""
        consumed_event = False
        
        # Check back button
        if self.back_button['rect'].collidepoint(mouse_pos):
            self.close_options()
            return
        
        # Check reset button
        if self.reset_button['rect'].collidepoint(mouse_pos):
            self.reset_to_defaults()
            return
        
        # Check tabs
        for tab_name, tab_data in self.tabs.items():
            if tab_data['rect'].collidepoint(mouse_pos):
                self.current_section = tab_name
                self._setup_section_options()
                self.selected_option = 0
                break
        
        # Convert mouse position to content coordinates (account for scrolling)
        content_pos = (mouse_pos[0], mouse_pos[1] + self.scroll_offset)

        # Check options
        for i, option in enumerate(self.options):
            if option['rect'].collidepoint(content_pos):
                self.selected_option = i
                self.nav_index = i + 1  # Sync nav_index with clicked row
                if option['type'] == 'toggle':
                    self.settings[option['key']] = not self.settings[option['key']]
                    self._apply_settings()
                elif option['type'] == 'control':
                    self.remapping_control = option['key']
                    self.remapping_start_time = pygame.time.get_ticks()
                consumed_event = True

    def _handle_slider_drag(self, mouse_pos):
        """Handle slider dragging."""
        if self.dragging_slider is None:
            return
        
        option = self.options[self.dragging_slider]
        slider_rect = option['slider_rect']
        
        # Calculate new value based on mouse position
        relative_x = mouse_pos[0] - slider_rect.left
        relative_x = max(0, min(relative_x, slider_rect.width))
        new_value = relative_x / slider_rect.width
        
        self.settings[option['key']] = new_value
        self._apply_settings()

    def _handle_left_arrow(self):
        """Handle left arrow key press."""
        if self.selected_option < len(self.options):
            option = self.options[self.selected_option]
            if option['type'] == 'slider':
                self.settings[option['key']] = max(0.0, self.settings[option['key']] - 0.05)
                self._apply_settings()
            elif option['type'] == 'toggle':
                self.settings[option['key']] = not self.settings[option['key']]
                self._apply_settings()

    def _handle_right_arrow(self):
        """Handle right arrow key press."""
        if self.selected_option < len(self.options):
            option = self.options[self.selected_option]
            if option['type'] == 'slider':
                self.settings[option['key']] = min(1.0, self.settings[option['key']] + 0.05)
                self._apply_settings()
            elif option['type'] == 'toggle':
                self.settings[option['key']] = not self.settings[option['key']]
                self._apply_settings()

    def _activate_selected(self):
        """Activate the currently selected option."""
        # Determine action based on nav_index instead of selected_option so
        # Back / Reset are handled correctly even when they were never part of
        # the options list.
        if 1 <= self.nav_index <= len(self.options):
            option = self.options[self.selected_option]
            if option['type'] == 'toggle':
                self.settings[option['key']] = not self.settings[option['key']]
                self._apply_settings()
            elif option['type'] == 'control':
                self.remapping_control = option['key']
                self.remapping_start_time = pygame.time.get_ticks()
        elif self.nav_index == len(self.options) + 1:
            # Back button
            self.close_options()
        elif self.nav_index == len(self.options) + 2:
            # Reset button
            self.reset_to_defaults()

    def _update_hover_states(self, mouse_pos):
        """Update hover states for all interactive elements."""
        self.back_button['hover'] = self.back_button['rect'].collidepoint(mouse_pos)
        self.reset_button['hover'] = self.reset_button['rect'].collidepoint(mouse_pos)
        for tab_name, tab_data in self.tabs.items():
            tab_data['hover'] = tab_data['rect'].collidepoint(mouse_pos)

    def draw(self, surface):
        """Draw the options menu."""
        if not self.active:
            return
        
        surface.blit(self.bg, (0, 0))
        
        # Draw title with shadow
        shadow = self._render_outline("Options", self.title_font, (0, 0, 0), (0, 0, 0), 0)
        surface.blit(shadow, self.title_rect.move(3, 3))
        surface.blit(self.title_surf, self.title_rect)
        
        # Draw tabs
        for tab_name, tab_data in self.tabs.items():
            selected = (tab_name == self.current_section)
            hover = tab_data.get('hover', False)
            
            # Draw tab background
            if selected:
                bg_color = (80, 80, 80)
                border_color = YELLOW
                text_color = YELLOW
            elif hover:
                bg_color = (60, 60, 60)
                border_color = WHITE
                text_color = WHITE
            else:
                bg_color = (40, 40, 40)
                border_color = (100, 100, 100)
                text_color = WHITE
            
            # Draw tab background and border
            pygame.draw.rect(surface, bg_color, tab_data['rect'])
            pygame.draw.rect(surface, border_color, tab_data['rect'], 2)
            
            # Draw tab label
            tab_surf = self._render_outline(tab_data['label'], self.btn_font, text_color, (0, 0, 0), 1)
            tab_rect = tab_surf.get_rect(center=tab_data['rect'].center)
            surface.blit(tab_surf, tab_rect)
        
        # Draw options
        for i, option in enumerate(self.options):
            selected = (1 <= self.nav_index <= len(self.options) and (i == self.selected_option))
            self._draw_option(surface, option, selected)
        
        # Draw back and reset buttons
        self._draw_back_button(surface)
        self._draw_reset_button(surface)
        
        # Draw remapping indicator
        if self.remapping_control:
            elapsed = pygame.time.get_ticks() - self.remapping_start_time
            if elapsed < 3000:  # Show for 3 seconds
                text = f"Press a key for {CONTROL_DESCRIPTIONS[self.remapping_control]}..."
                if elapsed // 500 % 2:  # Blink every 500ms
                    text_surf = self._render_outline(text, self.label_font, YELLOW, (0, 0, 0), 1)
                    text_rect = text_surf.get_rect(center=(WIDTH // 2, HEIGHT - 150))
                    surface.blit(text_surf, text_rect)
            else:
                # Timeout - cancel remapping
                self.remapping_control = None

    def _draw_option(self, surface, option, selected):
        """Draw an individual option based on its type."""
        label_color = YELLOW if selected else WHITE

        # Apply vertical scroll offset so the list can scroll
        y_offset = -self.scroll_offset
 
        if option['type'] == 'slider':
            # Draw slider label
            label_surf = self._render_outline(option['label'], self.label_font, label_color, (0, 0, 0), 1)
            label_rect = label_surf.get_rect(center=(WIDTH // 2, option['label_rect'].centery + y_offset))
            surface.blit(label_surf, label_rect)
            
            # Draw slider
            slider_rect = option['slider_rect'].copy()
            slider_rect.y += y_offset
            self._draw_slider(surface, option, selected, slider_rect)
        elif option['type'] == 'toggle':
            # Draw toggle label
            label_surf = self._render_outline(option['label'], self.label_font, label_color, (0, 0, 0), 1)
            label_rect = label_surf.get_rect(center=(WIDTH // 2, option['label_rect'].centery + y_offset))
            surface.blit(label_surf, label_rect)
            
            # Draw toggle
            toggle_rect = option['rect'].copy()
            toggle_rect.centerx = WIDTH // 2
            toggle_rect.y += y_offset
            self._draw_toggle(surface, option, selected, toggle_rect)
        elif option['type'] == 'control':
            # Draw control label
            control_label_surf = self._render_outline(option['label'], self.label_font, label_color, (0, 0, 0), 1)
            label_col_x = WIDTH // 2 - 260
            control_label_rect = control_label_surf.get_rect(midleft=(label_col_x, option['label_rect'].centery + y_offset))
            surface.blit(control_label_surf, control_label_rect)
            
            # Draw key display
            from config import get_control_key
            key_code = get_control_key(option['key'])
            key_name = get_key_name(key_code)
            
            # Highlight if being remapped
            if self.remapping_control == option['key']:
                key_color = YELLOW
                key_name = "Press key..."
            else:
                key_color = WHITE
            
            key_surf = self._render_outline(key_name, self.key_font, key_color, (0, 0, 0), 1)
            key_box_width = key_surf.get_width() + 30
            key_rect = key_surf.get_rect()
            key_rect.midright = (WIDTH // 2 + 260, option['rect'].centery + y_offset)
            bg_rect = pygame.Rect(0, 0, key_box_width, key_rect.height + 10)
            bg_rect.center = key_rect.center
            
            # Draw key background
            pygame.draw.rect(surface, (40, 40, 40), bg_rect)
            pygame.draw.rect(surface, YELLOW if selected else WHITE, bg_rect, 2)
            
            surface.blit(key_surf, key_rect)

    def _draw_slider(self, surface, option, selected, slider_rect=None):
        """Draw a volume slider, centered if slider_rect is provided."""
        if slider_rect is None:
            slider_rect = option['slider_rect']
        value = self.settings[option['key']]
        track_color = YELLOW if selected else (100, 100, 100)
        pygame.draw.rect(surface, track_color, slider_rect, 2)
        fill_width = int(slider_rect.width * value)
        fill_rect = pygame.Rect(slider_rect.left, slider_rect.top, fill_width, slider_rect.height)
        fill_color = YELLOW if selected else (150, 150, 150)
        pygame.draw.rect(surface, fill_color, fill_rect)
        handle_x = slider_rect.left + fill_width
        handle_rect = pygame.Rect(handle_x - 5, slider_rect.top - 3, 10, slider_rect.height + 6)
        handle_color = YELLOW if selected else WHITE
        pygame.draw.rect(surface, handle_color, handle_rect)
        pygame.draw.rect(surface, (0, 0, 0), handle_rect, 2)
        percent_text = f"{int(value * 100)}%"
        percent_surf = self.btn_font.render(percent_text, True, WHITE)
        percent_rect = percent_surf.get_rect(midleft=(slider_rect.right + 10, slider_rect.centery))
        surface.blit(percent_surf, percent_rect)

    def _draw_toggle(self, surface, option, selected, toggle_rect=None):
        """Draw a toggle button as two separate ON/OFF buttons, centered if toggle_rect is provided."""
        if toggle_rect is None:
            toggle_rect = option['rect']
        value = self.settings[option['key']]
        button_width = toggle_rect.width // 2
        on_rect = pygame.Rect(toggle_rect.left, toggle_rect.top, button_width, toggle_rect.height)
        off_rect = pygame.Rect(toggle_rect.left + button_width, toggle_rect.top, button_width, toggle_rect.height)
        GREY_BG = (60, 60, 60)
        LIGHT_GREY_TEXT = (220, 220, 220)
        YELLOW_BG = YELLOW
        BLACK_TEXT = (0, 0, 0)
        # Determine logic inversion by key
        inverted_keys = {'music_muted', 'sfx_muted'}
        if option['key'] in inverted_keys:
            # Inverted logic: True (muted) = OFF yellow, False = ON yellow
            if value:
                on_bg_color = GREY_BG
                on_text_color = LIGHT_GREY_TEXT
                off_bg_color = YELLOW_BG
                off_text_color = BLACK_TEXT
            else:
                on_bg_color = YELLOW_BG
                on_text_color = BLACK_TEXT
                off_bg_color = GREY_BG
                off_text_color = LIGHT_GREY_TEXT
        else:
            # Normal logic: True = ON yellow, False = OFF yellow
            if value:
                on_bg_color = YELLOW_BG
                on_text_color = BLACK_TEXT
                off_bg_color = GREY_BG
                off_text_color = LIGHT_GREY_TEXT
            else:
                on_bg_color = GREY_BG
                on_text_color = LIGHT_GREY_TEXT
                off_bg_color = YELLOW_BG
                off_text_color = BLACK_TEXT
        # Draw ON button
        pygame.draw.rect(surface, on_bg_color, on_rect)
        pygame.draw.rect(surface, (0, 0, 0), on_rect, 2)
        on_text_surf = self._render_outline("ON", self.btn_font, on_text_color, (0, 0, 0), 1)
        on_text_rect = on_text_surf.get_rect(center=on_rect.center)
        surface.blit(on_text_surf, on_text_rect)
        # Draw OFF button
        pygame.draw.rect(surface, off_bg_color, off_rect)
        pygame.draw.rect(surface, (0, 0, 0), off_rect, 2)
        off_text_surf = self._render_outline("OFF", self.btn_font, off_text_color, (0, 0, 0), 1)
        off_text_rect = off_text_surf.get_rect(center=off_rect.center)
        surface.blit(off_text_surf, off_text_rect)
    
    def _draw_back_button(self, surface):
        """Draw the back button."""
        button = self.back_button
        selected = (self.nav_index == len(self.options) + 1)
        
        # Colors
        bg_color = (110, 110, 110) if (button['hover'] or selected) else (60, 60, 60)
        border_color = YELLOW if selected else (0, 0, 0)
        text_color = YELLOW if (button['hover'] or selected) else WHITE
        
        # Draw button
        pygame.draw.rect(surface, bg_color, button['rect'])
        pygame.draw.rect(surface, border_color, button['rect'], 2)
        
        # Draw button text
        text_surf = self._render_outline(button['label'], self.btn_font, text_color, (0, 0, 0), 1)
        text_rect = text_surf.get_rect(center=button['rect'].center)
        surface.blit(text_surf, text_rect)
    
    def _draw_reset_button(self, surface):
        """Draw the reset button."""
        button = self.reset_button
        selected = (self.nav_index == len(self.options) + 2)  # Reset is after back button
        
        # Colors
        bg_color = (110, 110, 110) if (button['hover'] or selected) else (60, 60, 60)
        border_color = YELLOW if selected else (0, 0, 0)
        text_color = YELLOW if (button['hover'] or selected) else WHITE
        
        # Draw button
        pygame.draw.rect(surface, bg_color, button['rect'])
        pygame.draw.rect(surface, border_color, button['rect'], 2)
        
        # Draw button text
        text_surf = self._render_outline(button['label'], self.btn_font, text_color, (0, 0, 0), 1)
        text_rect = text_surf.get_rect(center=button['rect'].center)
        surface.blit(text_surf, text_rect)
    
    def _render_outline(self, text, font, fg, outline, px=1):
        """Render text with outline."""
        base = font.render(text, True, fg)
        w, h = base.get_size()
        surf = pygame.Surface((w + px * 2, h + px * 2), pygame.SRCALPHA)
        for dx in range(-px, px + 1):
            for dy in range(-px, px + 1):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(font.render(text, True, outline), (dx + px, dy + px))
        surf.blit(base, (px, px))
        return surf
    
    def _load_pixel_font(self, size):
        """Load pixel font or fallback to system font."""
        pix_path = 'PressStart2P-Regular.ttf'
        if os.path.isfile(pix_path):
            try:
                return pygame.font.Font(pix_path, size)
            except Exception:
                pass
        return pygame.font.SysFont('Courier New', size, bold=True)
    
    def get_setting(self, key, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)