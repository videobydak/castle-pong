import pygame
import sys
import os
import json
from config import WIDTH, HEIGHT, WHITE, YELLOW

class OptionsMenu:
    """Options screen with volume controls, mute toggles, and game settings."""
    
    def __init__(self):
        self.active = False
        self.bg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.bg.fill((0, 0, 0, 230))
        
        # Font setup
        self.title_font = self._load_pixel_font(96)
        self.btn_font = self._load_pixel_font(32)
        self.label_font = self._load_pixel_font(24)
        
        self.title_surf = self._render_outline("Options", self.title_font, YELLOW, (0, 0, 0), 2)
        self.title_rect = self.title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 4))
        
        # Settings storage
        self.settings = self._load_settings()
        
        # Control state
        self.selected_option = 0
        self.dragging_slider = None
        self.mouse_held = False
        
        # Setup UI elements
        self._setup_ui_elements()
    
    def _load_settings(self):
        """Load settings from file or create defaults."""
        default_settings = {
            'music_volume': 0.6,
            'sfx_volume': 0.4,
            'music_muted': False,
            'sfx_muted': False,
            'screen_shake': True,
            'show_fps': False
        }
        
        try:
            if os.path.exists('game_settings.json'):
                with open('game_settings.json', 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new settings
                    default_settings.update(loaded)
        except Exception as e:
            print(f"[Options] Failed to load settings: {e}")
        
        return default_settings
    
    def _save_settings(self):
        """Save current settings to file."""
        try:
            with open('game_settings.json', 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"[Options] Failed to save settings: {e}")
    
    def _setup_ui_elements(self):
        """Setup all UI elements with positions and rectangles."""
        start_y = self.title_rect.bottom + 60
        self.options = []
        
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
        
        # Music Mute Toggle
        mute_music_y = music_y + 70
        self.options.append({
            'type': 'toggle',
            'key': 'music_muted',
            'label': 'Mute Music',
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
        
        # SFX Mute Toggle
        mute_sfx_y = sfx_y + 70
        self.options.append({
            'type': 'toggle',
            'key': 'sfx_muted',
            'label': 'Mute SFX',
            'rect': pygame.Rect(WIDTH//2 - 100, mute_sfx_y, 200, 40),
            'label_rect': pygame.Rect(WIDTH//2 - 100, mute_sfx_y - 30, 200, 25)
        })
        
        # Screen Shake Toggle
        shake_y = mute_sfx_y + 80
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
        
        # Back Button
        back_y = fps_y + 100
        self.back_button = {
            'rect': pygame.Rect(WIDTH//2 - 75, back_y, 150, 50),
            'label': 'Back',
            'hover': False
        }
    
    def open_options(self):
        """Open the options menu."""
        self.active = True
        self.selected_option = 0
        self.dragging_slider = None
        # Apply settings to ensure all volumes are up to date
        self._apply_settings()
    
    def close_options(self):
        """Close the options menu and save settings."""
        self.active = False
        self._save_settings()
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
                for sound in main_module.sounds.values():
                    if sound:  # Check if sound loaded successfully
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
                if event.key == pygame.K_ESCAPE:
                    self.close_options()
                elif event.key == pygame.K_UP:
                    self.selected_option = (self.selected_option - 1) % (len(self.options) + 1)
                elif event.key == pygame.K_DOWN:
                    self.selected_option = (self.selected_option + 1) % (len(self.options) + 1)
                elif event.key == pygame.K_LEFT:
                    self._handle_left_arrow()
                elif event.key == pygame.K_RIGHT:
                    self._handle_right_arrow()
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    self._activate_selected()
        
        # Handle mouse interactions
        if mouse_clicked:
            self._handle_mouse_click(mouse_pos)
        
        # Handle slider dragging
        if self.mouse_held and self.dragging_slider is not None:
            self._handle_slider_drag(mouse_pos)
        
        # Update hover states
        self._update_hover_states(mouse_pos)
        
        return consumed_event
    
    def _handle_mouse_click(self, mouse_pos):
        """Handle mouse click events."""
        # Check back button
        if self.back_button['rect'].collidepoint(mouse_pos):
            self.close_options()
            return
        
        # Check options
        for i, option in enumerate(self.options):
            if option['rect'].collidepoint(mouse_pos):
                if option['type'] == 'toggle':
                    self.settings[option['key']] = not self.settings[option['key']]
                    self._apply_settings()
                elif option['type'] == 'slider':
                    self.dragging_slider = i
                    self._handle_slider_drag(mouse_pos)
    
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
        """Handle left arrow key - decrease slider values or toggle switches."""
        if self.selected_option < len(self.options):
            option = self.options[self.selected_option]
            if option['type'] == 'slider':
                # Decrease slider value by 5%
                current_value = self.settings[option['key']]
                new_value = max(0.0, current_value - 0.05)
                self.settings[option['key']] = new_value
                self._apply_settings()
            elif option['type'] == 'toggle':
                # Toggle the switch
                self.settings[option['key']] = not self.settings[option['key']]
                self._apply_settings()

    def _handle_right_arrow(self):
        """Handle right arrow key - increase slider values or toggle switches."""
        if self.selected_option < len(self.options):
            option = self.options[self.selected_option]
            if option['type'] == 'slider':
                # Increase slider value by 5%
                current_value = self.settings[option['key']]
                new_value = min(1.0, current_value + 0.05)
                self.settings[option['key']] = new_value
                self._apply_settings()
            elif option['type'] == 'toggle':
                # Toggle the switch
                self.settings[option['key']] = not self.settings[option['key']]
                self._apply_settings()

    def _activate_selected(self):
        """Activate the currently selected option with keyboard."""
        if self.selected_option == len(self.options):  # Back button
            self.close_options()
        elif self.selected_option < len(self.options):
            option = self.options[self.selected_option]
            if option['type'] == 'toggle':
                self.settings[option['key']] = not self.settings[option['key']]
                self._apply_settings()
    
    def _update_hover_states(self, mouse_pos):
        """Update hover states for UI elements."""
        self.back_button['hover'] = self.back_button['rect'].collidepoint(mouse_pos)
    
    def draw(self, surface):
        """Draw the options menu."""
        if not self.active:
            return
        
        # Draw background
        surface.blit(self.bg, (0, 0))
        
        # Draw title
        shadow = self.title_surf.copy()
        shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow, self.title_rect.move(3, 3))
        surface.blit(self.title_surf, self.title_rect)
        
        # Draw options
        for i, option in enumerate(self.options):
            selected = (i == self.selected_option)
            self._draw_option(surface, option, selected)
        
        # Draw back button
        self._draw_back_button(surface)
    
    def _draw_option(self, surface, option, selected):
        """Draw a single option element."""
        # Draw label
        label_color = YELLOW if selected else WHITE
        label_surf = self._render_outline(option['label'], self.label_font, label_color, (0, 0, 0), 1)
        surface.blit(label_surf, option['label_rect'])
        
        if option['type'] == 'slider':
            self._draw_slider(surface, option, selected)
        elif option['type'] == 'toggle':
            self._draw_toggle(surface, option, selected)
    
    def _draw_slider(self, surface, option, selected):
        """Draw a volume slider."""
        slider_rect = option['slider_rect']
        value = self.settings[option['key']]
        
        # Draw slider track
        track_color = YELLOW if selected else (100, 100, 100)
        pygame.draw.rect(surface, track_color, slider_rect, 2)
        
        # Draw slider fill
        fill_width = int(slider_rect.width * value)
        fill_rect = pygame.Rect(slider_rect.left, slider_rect.top, fill_width, slider_rect.height)
        fill_color = YELLOW if selected else (150, 150, 150)
        pygame.draw.rect(surface, fill_color, fill_rect)
        
        # Draw slider handle
        handle_x = slider_rect.left + fill_width
        handle_rect = pygame.Rect(handle_x - 5, slider_rect.top - 3, 10, slider_rect.height + 6)
        handle_color = YELLOW if selected else WHITE
        pygame.draw.rect(surface, handle_color, handle_rect)
        pygame.draw.rect(surface, (0, 0, 0), handle_rect, 2)
        
        # Draw percentage
        percent_text = f"{int(value * 100)}%"
        percent_surf = self.btn_font.render(percent_text, True, WHITE)
        percent_rect = percent_surf.get_rect(center=(slider_rect.right + 40, slider_rect.centery))
        surface.blit(percent_surf, percent_rect)
    
    def _draw_toggle(self, surface, option, selected):
        """Draw a toggle button as two separate ON/OFF buttons."""
        toggle_rect = option['rect']
        value = self.settings[option['key']]
        
        # Split the rect into two halves for ON and OFF
        button_width = toggle_rect.width // 2
        on_rect = pygame.Rect(toggle_rect.left, toggle_rect.top, button_width, toggle_rect.height)
        off_rect = pygame.Rect(toggle_rect.left + button_width, toggle_rect.top, button_width, toggle_rect.height)

        GREY_BG = (60, 60, 60)
        LIGHT_GREY_TEXT = (220, 220, 220)
        YELLOW_BG = YELLOW
        BLACK_TEXT = (0, 0, 0)

        # Corrected: When value is True, ON is yellow; when value is False, OFF is yellow
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
        selected = (self.selected_option == len(self.options))
        
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