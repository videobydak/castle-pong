import pygame
import math
import random
import os
from config import WIDTH, HEIGHT, WHITE, SCALE, YELLOW, get_control_key
from typing import Optional, Dict, Any
from coin import get_coin_count


class EndOfWaveScreen:
    """
    End of Wave Screen that displays animated scoring breakdown.
    
    Shows:
    - SCORE (score at end of round)
    - TIME BONUS (1x-6x multiplier based on completion time)
    - TOTAL SCORE (SCORE * TIME BONUS)
    - COINS COLLECTED (coins collected during round)
    - SCORE BONUS (0.1x for every 100 points earned)
    - TOTAL COINS (COINS COLLECTED * SCORE BONUS)
    """
    
    def __init__(self):
        self.active = False
        self.state = 'idle'  # idle, animating, complete
        self.timer = 0
        self.sequence_step = 0
        
        # Data for display
        self.score = 0
        self.time_bonus_multiplier = 1.0
        self.total_score = 0
        self.coins_collected = 0
        self.score_bonus_multiplier = 1.0
        self.total_coins = 0
        
        # Animation data
        self.animated_values = {
            'score': {'current': 0, 'target': 0, 'speed': 0, 'complete': False, 'sound_started': False},
            'time_bonus': {'current': 0, 'target': 0, 'speed': 0, 'complete': False, 'sound_started': False},
            'total_score': {'current': 0, 'target': 0, 'speed': 0, 'complete': False, 'sound_started': False},
            'coins_collected': {'current': 0, 'target': 0, 'speed': 0, 'complete': False, 'sound_started': False},
            'score_bonus': {'current': 0, 'target': 0, 'speed': 0, 'complete': False, 'sound_started': False},
            'total_coins': {'current': 0, 'target': 0, 'speed': 0, 'complete': False, 'sound_started': False}
        }
        
        # UI elements
        self.headings = ['SCORE', 'TIME BONUS', 'TOTAL SCORE', 'COINS COLLECTED', 'SCORE BONUS', 'TOTAL COINS']
        self.heading_alpha = [0] * len(self.headings)
        self.current_heading = 0
        
        # Sound control
        self.sounds = {}
        self.sound_channels = {}
        self.scoring_sound_playing = False
        self.current_sound_animation = None  # Track which animation is currently playing sound
        
        # Font setup
        self.pixel_font_large = self._load_pixel_font(48)
        self.pixel_font_medium = self._load_pixel_font(36)
        self.pixel_font_small = self._load_pixel_font(24)
        
        # Animation timings (in ms)
        self.HEADING_FADE_TIME = 500
        self.HEADING_DELAY = 200
        self.COUNT_ANIMATION_BASE_TIME = 500  # Reduced from 1000 for faster animations
        self.COUNT_ANIMATION_MAX_TIME = 1500  # Reduced from 3000 for faster animations
        self.PAUSE_BETWEEN_SECTIONS = 800
        
        # Sequence steps - now based on animation completion rather than fixed timing
        self.sequence_steps = [
            'show_score',
            'show_time_bonus', 
            'show_total_score',
            'show_coins_collected',
            'show_score_bonus',
            'show_total_coins',
            'show_all_complete'
        ]
        
        # Current step in sequence
        self.current_sequence_step = 0
        self.sequence_step_started = False
        self.initial_delay_timer = 0  # Small delay before first step
        self.INITIAL_DELAY = 200  # 200ms delay before starting
        
        # Background surface - create once and reuse
        self.background = None
        self._create_background()
        
        self.completion_time = 0
        
        # Buttons
        self.continue_button = None
        self.shop_button = None
        self.button_width = 200
        self.button_height = 50
        self.button_spacing = 20
        self.selected_action = None  # 'continue' or 'shop'
        self.selected_button = 0  # 0 = continue, 1 = shop
        
    def _create_background(self):
        """Create a stable background surface."""
        # Two-layer background: an opaque black surface ensures that
        # underlying frame buffers never bleed through, while a secondary
        # semi-transparent overlay provides the desired darkening effect
        # without introducing on-going flicker.
        self.background = pygame.Surface((WIDTH, HEIGHT))
        self.background.fill((0, 0, 0))  # Solid black base
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))      # Semi-transparent dark overlay
        self.background.blit(overlay, (0, 0))
        
    def _load_pixel_font(self, size: int) -> pygame.font.Font:
        """Load pixel font with fallback."""
        try:
            if os.path.isfile('PressStart2P-Regular.ttf'):
                return pygame.font.Font('PressStart2P-Regular.ttf', size)
        except:
            pass
        return pygame.font.SysFont('Courier New', size, bold=True)
    
    def _get_time_bonus_multiplier(self, completion_time_seconds: float) -> float:
        """Calculate time bonus multiplier based on completion time."""
        if completion_time_seconds <= 10:
            return 6.0
        elif completion_time_seconds <= 20:
            return 5.0
        elif completion_time_seconds <= 30:
            return 4.0
        elif completion_time_seconds <= 40:
            return 3.0
        elif completion_time_seconds <= 50:
            return 2.0
        else:
            return 1.0  # Always minimum 1.0 to avoid zero total score
    
    def _get_score_bonus_multiplier(self, score: int) -> float:
        """Calculate score bonus multiplier: 0.1x for every 100 points."""
        return 1.0 + (score // 100) * 0.1
    
    def _calculate_animation_speed(self, target_value: int) -> float:
        """Calculate animation speed for counting up through each digit."""
        if target_value == 0:
            return 0
        
        # Calculate increment rate (increments per second)
        # We want to count through each number visibly
        if target_value <= 10:
            increments_per_second = 15  # Very fast for single digits
        elif target_value <= 50:
            increments_per_second = 25  # Fast for small values
        elif target_value <= 100:
            increments_per_second = 35  # Still fast for medium values
        elif target_value <= 500:
            increments_per_second = 50  # Reasonable for larger values
        elif target_value <= 1000:
            increments_per_second = 80  # Moderate for large values
        elif target_value <= 10000:
            increments_per_second = 120  # Fast for very large values
        else:
            increments_per_second = 200  # Very fast for huge values
            
        # Convert to increments per millisecond
        return increments_per_second / 1000.0
    
    def _play_sound_with_volume(self, sound_name: str, loop: bool = False) -> Optional[pygame.mixer.Channel]:
        """Play sound with volume control."""
        if sound_name not in self.sounds:
            return None
            
        sound = self.sounds[sound_name]
        if not sound:
            return None
            
        # Update volume based on current settings
        try:
            import sys
            if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'options_menu'):
                options_menu = sys.modules['__main__'].options_menu
                if hasattr(options_menu, 'settings'):
                    if options_menu.settings.get('sfx_muted', False):
                        sound.set_volume(0)
                    else:
                        sfx_vol = options_menu.settings.get('sfx_volume', 0.75)
                        # Reduce volume for scoring sounds to 25% of the selected SFX level
                        if sound_name in ('eos_scoring_normal', 'eos_scoring_high'):
                            sfx_vol *= 0.25
                        sound.set_volume(sfx_vol)
        except:
            pass
            
        if loop:
            return sound.play(-1)
        else:
            return sound.play()
    
    def _stop_sound(self, sound_name: str):
        """Stop a sound if it's playing."""
        if sound_name in self.sound_channels and self.sound_channels[sound_name]:
            try:
                self.sound_channels[sound_name].stop()
            except:
                pass  # Channel might already be stopped or invalid
            self.sound_channels[sound_name] = None
    
    def _stop_all_sounds(self):
        """Stop all sounds that might be playing."""
        for sound_name in ['eos_scoring_normal', 'eos_scoring_high', 'eos_new_ui_item', 'eos_no_bonus', 'eos_yes_bonus']:
            self._stop_sound(sound_name)
        self.scoring_sound_playing = False
        self.current_sound_animation = None
    
    def _create_buttons(self):
        """Create button rectangles for Continue and Shop."""
        # Calculate button positions
        total_width = self.button_width * 2 + self.button_spacing
        start_x = (WIDTH - total_width) // 2
        button_y = HEIGHT - 120  # 120 pixels from bottom
        
        self.continue_button = pygame.Rect(start_x, button_y, self.button_width, self.button_height)
        self.shop_button = pygame.Rect(start_x + self.button_width + self.button_spacing, button_y, self.button_width, self.button_height)
    
    def _draw_buttons(self, screen: pygame.Surface):
        """Draw the Continue and Shop buttons with highlighting."""
        if self.state != 'waiting_for_input':
            return
        
        if not self.continue_button:
            self._create_buttons()
        
        # Draw Continue button
        continue_selected = (self.selected_button == 0)
        continue_bg_color = (150, 150, 150) if continue_selected else (100, 100, 100)
        continue_border_color = (255, 255, 0) if continue_selected else WHITE
        continue_text_color = (255, 255, 0) if continue_selected else WHITE
        
        pygame.draw.rect(screen, continue_bg_color, self.continue_button)
        pygame.draw.rect(screen, continue_border_color, self.continue_button, 3 if continue_selected else 2)
        
        continue_text = self.pixel_font_small.render("CONTINUE", True, continue_text_color)
        continue_rect = continue_text.get_rect(center=self.continue_button.center)
        screen.blit(continue_text, continue_rect)
        
        # Draw Shop button
        shop_selected = (self.selected_button == 1)
        shop_bg_color = (150, 150, 150) if shop_selected else (100, 100, 100)
        shop_border_color = (255, 255, 0) if shop_selected else WHITE
        shop_text_color = (255, 255, 0) if shop_selected else WHITE
        
        pygame.draw.rect(screen, shop_bg_color, self.shop_button)
        pygame.draw.rect(screen, shop_border_color, self.shop_button, 3 if shop_selected else 2)
        
        shop_text = self.pixel_font_small.render("SHOP", True, shop_text_color)
        shop_rect = shop_text.get_rect(center=self.shop_button.center)
        screen.blit(shop_text, shop_rect)
    
    def show(self, score: int, wave_completion_time_ms: int, coins_at_wave_start: int):
        """Show the End of Wave Screen with given data."""
        self.active = True
        self.state = 'animating'
        self.timer = 0
        self.current_sequence_step = 0
        self.sequence_step_started = False
        self.initial_delay_timer = 0
        self.selected_button = 0  # Reset to Continue button
        
        # Ensure we have a fresh background
        self._create_background()
        
        # Store data
        self.score = score
        self.completion_time = wave_completion_time_ms / 1000.0  # Convert to seconds
        self.time_bonus_multiplier = self._get_time_bonus_multiplier(self.completion_time)
        self.total_score = int(score * self.time_bonus_multiplier)
        
        current_coins = get_coin_count()
        self.coins_collected = max(0, current_coins - coins_at_wave_start)
        self.score_bonus_multiplier = self._get_score_bonus_multiplier(score)
        self.total_coins = int(self.coins_collected * self.score_bonus_multiplier)
        
        # Setup animations
        self.animated_values['score']['target'] = self.score
        self.animated_values['score']['speed'] = self._calculate_animation_speed(self.score)
        
        self.animated_values['time_bonus']['target'] = int(self.time_bonus_multiplier * 10)  # For x.x display
        self.animated_values['time_bonus']['speed'] = self._calculate_animation_speed(int(self.time_bonus_multiplier * 10))
        
        self.animated_values['total_score']['target'] = self.total_score
        self.animated_values['total_score']['speed'] = self._calculate_animation_speed(self.total_score)
        
        self.animated_values['coins_collected']['target'] = self.coins_collected
        self.animated_values['coins_collected']['speed'] = self._calculate_animation_speed(self.coins_collected)
        
        self.animated_values['score_bonus']['target'] = int(self.score_bonus_multiplier * 10)  # For x.x display
        self.animated_values['score_bonus']['speed'] = self._calculate_animation_speed(int(self.score_bonus_multiplier * 10))
        
        self.animated_values['total_coins']['target'] = self.total_coins
        self.animated_values['total_coins']['speed'] = self._calculate_animation_speed(self.total_coins)
        
        # Boost counting speed (excluding bonus multipliers) by 40%
        for fast_key in ['score', 'total_score', 'coins_collected', 'total_coins']:
            self.animated_values[fast_key]['speed'] *= 1.4
        
        # Reset animation state
        for key in self.animated_values:
            self.animated_values[key]['current'] = 0
            self.animated_values[key]['last_increment_time'] = 0
            self.animated_values[key]['complete'] = False
            self.animated_values[key]['sound_started'] = False
            
        self.heading_alpha = [0] * len(self.headings)
        self.current_heading = 0
        self.scoring_sound_playing = False
        self.current_sound_animation = None
        
        # Load sounds from main module
        try:
            import sys
            main_module = sys.modules['__main__']
            if hasattr(main_module, 'sounds'):
                self.sounds = main_module.sounds
        except:
            pass
    
    def hide(self):
        """Hide the End of Wave Screen."""
        self.active = False
        self.state = 'idle'
        self.selected_action = None
        self.selected_button = 0
        self.current_sequence_step = 0
        self.sequence_step_started = False
        self.initial_delay_timer = 0
        self.timer = 0
        self._stop_all_sounds()
        
        # Ensure all animation states are reset
        for key in self.animated_values:
            self.animated_values[key]['current'] = 0
            self.animated_values[key]['complete'] = False
            self.animated_values[key]['sound_started'] = False
            self.animated_values[key]['last_increment_time'] = 0
        
        # Reset heading alphas
        self.heading_alpha = [0] * len(self.headings)
        self.current_heading = 0
        self.scoring_sound_playing = False
        self.current_sound_animation = None
    
    def is_complete(self) -> bool:
        """Check if the animation is complete."""
        return self.state == 'complete'
    
    def get_selected_action(self) -> str:
        """Get the selected action ('continue' or 'shop'). Defaults to 'continue'."""
        return self.selected_action or 'continue'
    
    def update(self, dt_ms: int):
        """Update the End of Wave Screen animation."""
        if not self.active or self.state == 'complete':
            return
            
        self.timer += dt_ms
        
        # Handle initial delay
        if self.current_sequence_step == 0 and not self.sequence_step_started:
            self.initial_delay_timer += dt_ms
            if self.initial_delay_timer >= self.INITIAL_DELAY:
                self.sequence_step_started = True
                self._process_sequence_step(self.sequence_steps[self.current_sequence_step])
        
        # Process sequence steps based on animation completion
        elif self.sequence_step_started and self.current_sequence_step < len(self.sequence_steps) - 1:
            # Check if current step is complete
            if self._is_current_step_complete():
                # Move to next step
                self.current_sequence_step += 1
                if self.current_sequence_step < len(self.sequence_steps):
                    self._process_sequence_step(self.sequence_steps[self.current_sequence_step])
        
        # Update animations
        self._update_animations(dt_ms)
        
        # Update heading fade-ins
        self._update_heading_animations(dt_ms)
    
    def _is_current_step_complete(self) -> bool:
        """Check if the current sequence step is complete."""
        step_name = self.sequence_steps[self.current_sequence_step]
        
        # Map step names to animation keys
        step_to_key = {
            'show_score': 'score',
            'show_time_bonus': 'time_bonus',
            'show_total_score': 'total_score',
            'show_coins_collected': 'coins_collected',
            'show_score_bonus': 'score_bonus',
            'show_total_coins': 'total_coins'
        }
        
        if step_name in step_to_key:
            key = step_to_key[step_name]
            return self.animated_values[key]['complete']
        
        return True  # For steps that don't have animations
    
    def _process_sequence_step(self, step_name: str):
        """Process a sequence step."""
        if step_name == 'show_score':
            self._show_heading_and_animate('SCORE', 'score')
        elif step_name == 'show_time_bonus':
            self._show_heading_and_animate('TIME BONUS', 'time_bonus')
        elif step_name == 'show_total_score':
            self._show_heading_and_animate('TOTAL SCORE', 'total_score')
        elif step_name == 'show_coins_collected':
            self._show_heading_and_animate('COINS COLLECTED', 'coins_collected')
        elif step_name == 'show_score_bonus':
            self._show_heading_and_animate('SCORE BONUS', 'score_bonus')
        elif step_name == 'show_total_coins':
            self._show_heading_and_animate('TOTAL COINS', 'total_coins')
        elif step_name == 'show_all_complete':
            # All sections are now shown, stop sounds but don't set state to complete
            # The user must interact to complete the screen
            self._stop_all_sounds()
            self.state = 'waiting_for_input'
            # Create buttons for user interaction and reset selection
            self.selected_button = 0
            self._create_buttons()
    
    def _show_heading_and_animate(self, heading: str, value_key: str):
        """Show a heading and start animating its value."""
        # Stop any currently playing scoring sounds before starting new ones
        self._stop_sound('eos_scoring_normal')
        self._stop_sound('eos_scoring_high')
        self.scoring_sound_playing = False
        self.current_sound_animation = None
        
        # Play new UI item sound
        self._play_sound_with_volume('eos_new_ui_item')
        
        # Start heading fade-in
        heading_index = self.headings.index(heading)
        self.current_heading = heading_index
        
        # Start value animation - ensure it starts from 0
        if value_key in self.animated_values:
            target = self.animated_values[value_key]['target']
            # Reset current value to 0 to ensure animation starts from beginning
            self.animated_values[value_key]['current'] = 0
            self.animated_values[value_key]['last_increment_time'] = 0
            self.animated_values[value_key]['complete'] = False
            self.animated_values[value_key]['sound_started'] = False  # Track if sound has started
            
            if target == 0:
                # Play no bonus sound for zero values
                if value_key in ['time_bonus', 'score_bonus']:
                    self._play_sound_with_volume('eos_no_bonus')
            # Note: For non-zero values, sound will start when first increment happens
    
    def _update_animations(self, dt_ms: int):
        """Update value animations with integer counting and frame-perfect sound sync."""
        for key, data in self.animated_values.items():
            if data['speed'] > 0 and data['current'] < data['target']:
                # Calculate how much time has passed since last increment
                if 'last_increment_time' not in data:
                    data['last_increment_time'] = 0
                
                data['last_increment_time'] += dt_ms
                
                # Calculate time between increments (milliseconds per increment)
                ms_per_increment = 1.0 / data['speed'] if data['speed'] > 0 else 1000
                
                # Count up by integers when enough time has passed
                if data['last_increment_time'] >= ms_per_increment:
                    # Calculate how many increments we should do
                    increments_to_do = int(data['last_increment_time'] / ms_per_increment)
                    old_current = int(data['current'])
                    
                    # Update current value by integer increments
                    new_current = min(data['target'], old_current + increments_to_do)
                    data['current'] = new_current
                    
                    # Start sound exactly when first increment happens (0→1)
                    if old_current == 0 and new_current > 0 and not data.get('sound_started', False) and data['target'] > 0:
                        # Stop any currently playing scoring sounds
                        self._stop_sound('eos_scoring_normal')
                        self._stop_sound('eos_scoring_high')
                        
                        # Start new sound for this animation
                        is_high_value = key in ['total_score', 'total_coins']
                        sound_name = 'eos_scoring_high' if is_high_value else 'eos_scoring_normal'
                        channel = self._play_sound_with_volume(sound_name, loop=True)
                        if channel:
                            self.sound_channels[sound_name] = channel
                            self.scoring_sound_playing = True
                            self.current_sound_animation = key  # Track which animation owns this sound
                        data['sound_started'] = True
                    
                    # Stop sound exactly when target is reached
                    if new_current >= data['target'] and data.get('sound_started', False) and self.current_sound_animation == key:
                        # Stop sound immediately - no delay
                        if self.scoring_sound_playing:
                            self._stop_sound('eos_scoring_normal')
                            self._stop_sound('eos_scoring_high')
                            self.scoring_sound_playing = False
                            self.current_sound_animation = None
                        
                        # Play bonus sound if applicable
                        if key in ['time_bonus', 'score_bonus'] and data['target'] > 10:  # > 1.0x
                            self._play_sound_with_volume('eos_yes_bonus')
                        
                        data['complete'] = True
                    
                    # Reset timer, keeping remainder for smooth timing
                    data['last_increment_time'] = data['last_increment_time'] % ms_per_increment
    
    def _update_heading_animations(self, dt_ms: int):
        """Update heading fade-in animations."""
        for i in range(len(self.heading_alpha)):
            if i <= self.current_heading:
                # Fade in current and previous headings
                target_alpha = 255
                if self.heading_alpha[i] < target_alpha:
                    self.heading_alpha[i] = min(target_alpha, self.heading_alpha[i] + (255 * dt_ms / self.HEADING_FADE_TIME))
    
    def draw(self, screen: pygame.Surface):
        """Draw the End of Wave Screen."""
        if not self.active or self.state == 'complete':
            return
            
        # Ensure background exists and draw it
        if self.background is None:
            self._create_background()
        screen.blit(self.background, (0, 0))
        
        # Draw content
        y_offset = 80
        line_height = 110
        
        for i, heading in enumerate(self.headings):
            if self.heading_alpha[i] > 0:
                # Draw heading
                alpha = int(self.heading_alpha[i])
                heading_surf = self.pixel_font_medium.render(heading, True, (255, 255, 255))
                heading_surf.set_alpha(alpha)
                heading_rect = heading_surf.get_rect(center=(WIDTH // 2, y_offset))
                screen.blit(heading_surf, heading_rect)
                
                # Draw value
                value_text = self._get_value_text(i)
                if value_text:
                    value_surf = self.pixel_font_large.render(value_text, True, (255, 255, 0))
                    value_surf.set_alpha(alpha)
                    value_rect = value_surf.get_rect(center=(WIDTH // 2, y_offset + 40))
                    screen.blit(value_surf, value_rect)
                
                y_offset += line_height
        
        # Draw buttons
        self._draw_buttons(screen)
    
    def _get_value_text(self, heading_index: int) -> str:
        """Get the formatted value text for a heading."""
        heading = self.headings[heading_index]
        
        if heading == 'SCORE':
            return f"{int(self.animated_values['score']['current'])}"
        elif heading == 'TIME BONUS':
            value = self.animated_values['time_bonus']['current'] / 10.0
            return f"{value:.1f}x"
        elif heading == 'TOTAL SCORE':
            return f"{int(self.animated_values['total_score']['current'])}"
        elif heading == 'COINS COLLECTED':
            return f"{int(self.animated_values['coins_collected']['current'])}"
        elif heading == 'SCORE BONUS':
            value = self.animated_values['score_bonus']['current'] / 10.0
            return f"{value:.1f}x"
        elif heading == 'TOTAL COINS':
            return f"{int(self.animated_values['total_coins']['current'])}"
        
        return ""
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events. Returns True if event was consumed."""
        if not self.active:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                if self.state == 'waiting_for_input':
                    if not self.continue_button:
                        self._create_buttons()
                    
                    if self.continue_button.collidepoint(event.pos):
                        self.selected_action = 'continue'
                        self.state = 'complete'
                        self._stop_all_sounds()  # Stop sounds immediately on selection
                        return True
                    elif self.shop_button.collidepoint(event.pos):
                        self.selected_action = 'shop'
                        self.state = 'complete'
                        self._stop_all_sounds()  # Stop sounds immediately on selection
                        return True
            
        if event.type == pygame.KEYDOWN:
            if event.key == get_control_key('bottom_paddle_left') or event.key == get_control_key('bottom_paddle_right'):
                if self.state == 'waiting_for_input':
                    # Navigate between buttons
                    self.selected_button = 1 - self.selected_button  # Toggle between 0 and 1
                    return True
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                if self.state == 'waiting_for_input':
                    # Select current button
                    self.selected_action = 'continue' if self.selected_button == 0 else 'shop'
                    self.state = 'complete'
                    self._stop_all_sounds()  # Stop sounds immediately on selection
                    return True
                elif self.state == 'complete':
                    self.hide()
                    return True
                else:
                    # Skip to waiting for input
                    self.state = 'waiting_for_input'
                    self.current_sequence_step = len(self.sequence_steps) - 1
                    self.sequence_step_started = True
                    self.selected_button = 0  # Reset to Continue button
                    
                    # Complete all animations
                    for key in self.animated_values:
                        self.animated_values[key]['current'] = self.animated_values[key]['target']
                        self.animated_values[key]['last_increment_time'] = 0
                        self.animated_values[key]['complete'] = True
                        self.animated_values[key]['sound_started'] = True
                    
                    # Show all headings
                    for i in range(len(self.heading_alpha)):
                        self.heading_alpha[i] = 255
                    
                    self._stop_all_sounds()
                    self._create_buttons()  # Ensure buttons are created for interaction
                    
                    return True
        
        return False 