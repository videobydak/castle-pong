import pygame
import sys
import math
from config import WIDTH, HEIGHT, WHITE, YELLOW, get_key_name, get_control_key
from utils import load_font


class EpilepsyWarning:
    """Epilepsy warning screen that appears before the main menu."""
    
    def __init__(self):
        self.active = True
        self.timer = 0
        self.min_display_time = 3000  # Minimum 3 seconds display
        self.fade_alpha = 0
        self.fade_in_duration = 1000  # 1 second fade in
        self.fade_out_duration = 500   # 0.5 second fade out
        self.fading_out = False
        
        # Load fonts
        self.title_font = self._load_pixel_font(48)
        self.warning_font = self._load_pixel_font(24)
        self.instruction_font = self._load_pixel_font(20)
        
        # Create warning text surfaces
        self.title_surf = self._render_outline("EPILEPSY WARNING", self.title_font, 
                                              (255, 255, 0), (0, 0, 0), 2)
        
        # Warning text lines
        warning_lines = [
            "This game contains flashing lights,",
            "rapid visual changes, and quick cuts",
            "that may trigger seizures in individuals",
            "with photosensitive epilepsy.",
            "",
            "Please consult with a doctor if you",
            "have a history of epilepsy or seizures.",
            "",
            "Player discretion is advised."
        ]
        
        self.warning_surfs = []
        for line in warning_lines:
            if line:  # Skip empty lines
                surf = self.warning_font.render(line, True, WHITE)
            else:
                surf = pygame.Surface((1, 30), pygame.SRCALPHA)  # Empty line spacer
            self.warning_surfs.append(surf)
        
        # Continue instruction
        self.continue_surf = self._render_outline("Press SPACE or ENTER to continue", 
                                                 self.instruction_font, 
                                                 (200, 200, 200), (0, 0, 0), 1)
        
        # Position elements
        self.title_rect = self.title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 4))
        
        # Position warning text
        self.warning_rects = []
        start_y = HEIGHT // 2 - 100
        for i, surf in enumerate(self.warning_surfs):
            rect = surf.get_rect(center=(WIDTH // 2, start_y + i * 35))
            self.warning_rects.append(rect)
        
        self.continue_rect = self.continue_surf.get_rect(center=(WIDTH // 2, HEIGHT - 80))
        
    def _load_pixel_font(self, size):
        """Load pixel font with fallback."""
        try:
            return load_font('PressStart2P-Regular.ttf', size)
        except:
            return pygame.font.SysFont('monospace', size)
    
    def _render_outline(self, text, font, color, outline_color, outline_width):
        """Render text with outline."""
        # First render the text to get its dimensions
        text_surf = font.render(text, True, color)
        text_w, text_h = text_surf.get_size()
        
        # Create outline surface sized to fit the text plus outline padding
        outline_w = text_w + 2 * outline_width
        outline_h = text_h + 2 * outline_width
        outline_surf = pygame.Surface((outline_w, outline_h), pygame.SRCALPHA)
        
        # Draw outline
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    outline_text = font.render(text, True, outline_color)
                    outline_surf.blit(outline_text, (dx + outline_width, dy + outline_width))
        
        # Draw main text
        outline_surf.blit(text_surf, (outline_width, outline_width))
        
        return outline_surf
    
    def update(self, events, dt):
        """Update the epilepsy warning screen."""
        if not self.active:
            return
        
        self.timer += dt
        
        # Handle fade in
        if not self.fading_out and self.timer < self.fade_in_duration:
            self.fade_alpha = int(255 * (self.timer / self.fade_in_duration))
        elif not self.fading_out:
            self.fade_alpha = 255
        
        # Handle input after minimum display time
        if self.timer >= self.min_display_time and not self.fading_out:
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE]:
                        self.fading_out = True
                        self.fade_timer = 0
                        break
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.fading_out = True
                    self.fade_timer = 0
                    break
        
        # Handle fade out
        if self.fading_out:
            if not hasattr(self, 'fade_timer'):
                self.fade_timer = 0
            self.fade_timer += dt
            
            if self.fade_timer >= self.fade_out_duration:
                self.active = False
            else:
                self.fade_alpha = int(255 * (1 - self.fade_timer / self.fade_out_duration))
    
    def draw(self, screen):
        """Draw the epilepsy warning screen."""
        if not self.active:
            return
        
        # Fill background with black
        screen.fill((0, 0, 0))
        
        # Create a surface for alpha blending
        if self.fade_alpha < 255:
            warning_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            warning_surface.set_alpha(self.fade_alpha)
        else:
            warning_surface = screen
        
        # Draw title
        if self.fade_alpha < 255:
            title_surf = self.title_surf.copy()
            title_surf.set_alpha(self.fade_alpha)
            warning_surface.blit(title_surf, self.title_rect)
        else:
            warning_surface.blit(self.title_surf, self.title_rect)
        
        # Draw warning text
        for surf, rect in zip(self.warning_surfs, self.warning_rects):
            if surf.get_width() > 1:  # Skip empty line spacers
                if self.fade_alpha < 255:
                    text_surf = surf.copy()
                    text_surf.set_alpha(self.fade_alpha)
                    warning_surface.blit(text_surf, rect)
                else:
                    warning_surface.blit(surf, rect)
        
        # Draw continue instruction (only after minimum time)
        if self.timer >= self.min_display_time:
            # Add blinking effect
            blink_alpha = int(127 + 128 * abs(math.sin(self.timer * 0.003)))
            if self.fade_alpha < 255:
                blink_alpha = int(blink_alpha * (self.fade_alpha / 255))
            
            continue_surf = self.continue_surf.copy()
            continue_surf.set_alpha(blink_alpha)
            warning_surface.blit(continue_surf, self.continue_rect)
        
        # Blit the warning surface to screen if we're using alpha blending
        if self.fade_alpha < 255:
            screen.blit(warning_surface, (0, 0)) 