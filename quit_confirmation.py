import pygame
from config import WIDTH, HEIGHT, WHITE, YELLOW, RED, get_control_key

class QuitConfirmationDialog:
    """Confirmation dialog to prevent accidental quits during gameplay."""
    
    def __init__(self):
        self.active = False
        self.selected_option = 0  # 0 = Cancel, 1 = Quit
        
        # Semi-transparent overlay
        self.overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 200))
        
        # Load fonts
        self.title_font = self._load_pixel_font(40)
        self.subtitle_font = self._load_pixel_font(20)
        self.btn_font = self._load_pixel_font(28)
        
        # Dialog box dimensions
        self.dialog_width = 650
        self.dialog_height = 300
        self.dialog_rect = pygame.Rect(
            (WIDTH - self.dialog_width) // 2,
            (HEIGHT - self.dialog_height) // 2,
            self.dialog_width,
            self.dialog_height
        )
        
        # Button options
        self.buttons = [
            ("Cancel", self._cancel),
            ("Quit", self._quit)
        ]
        
        self._layout_buttons()
        
    def _load_pixel_font(self, size):
        """Load bundled PressStart2P font or fallback to monospace."""
        from utils import load_font
        return load_font('PressStart2P-Regular.ttf', size)
    
    def _render_outline(self, text: str, font: pygame.font.Font, fg, outline, px: int = 1):
        """Render text with a pixel outline."""
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
    
    def _layout_buttons(self):
        """Precompute button rectangles."""
        self.btn_rects = []
        button_width = 180
        button_height = 50
        gap = 60
        
        total_width = len(self.buttons) * button_width + (len(self.buttons) - 1) * gap
        start_x = self.dialog_rect.centerx - total_width // 2
        button_y = self.dialog_rect.bottom - 80
        
        for i, (label, _) in enumerate(self.buttons):
            x = start_x + i * (button_width + gap)
            rect = pygame.Rect(x, button_y, button_width, button_height)
            self.btn_rects.append(rect)
    
    def show(self):
        """Show the confirmation dialog."""
        self.active = True
        self.selected_option = 0  # Default to Cancel
    
    def hide(self):
        """Hide the confirmation dialog."""
        self.active = False
    
    def _cancel(self):
        """Cancel the quit operation."""
        self.hide()
        return "cancel"
    
    def _quit(self):
        """Quit the game."""
        self.hide()
        return "quit"
    
    def update(self, events):
        """Handle input events. Returns None, 'cancel', or 'quit'."""
        if not self.active:
            return None
        
        result = None
        consumed_event = False
        
        # Handle keyboard navigation
        for e in events:
            if e.type == pygame.KEYDOWN:
                consumed_event = True
                if e.key == get_control_key('right_paddle_up') or e.key == pygame.K_LEFT:
                    self.selected_option = (self.selected_option - 1) % len(self.buttons)
                elif e.key == get_control_key('right_paddle_down') or e.key == pygame.K_RIGHT:
                    self.selected_option = (self.selected_option + 1) % len(self.buttons)
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    # Activate the currently selected button
                    _, callback = self.buttons[self.selected_option]
                    result = callback()
                elif e.key == pygame.K_ESCAPE:
                    # ESC cancels the quit
                    result = self._cancel()
        
        # Handle mouse input
        mouse_pos = pygame.mouse.get_pos()
        clicked = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        if clicked:
            consumed_event = True
        
        for i, (btn_rect, (label, callback)) in enumerate(zip(self.btn_rects, self.buttons)):
            if btn_rect.collidepoint(mouse_pos):
                self.selected_option = i
                if clicked:
                    result = callback()
        
        return result if consumed_event else None
    
    def draw(self, surface):
        """Draw the confirmation dialog."""
        if not self.active:
            return
        
        # Draw overlay
        surface.blit(self.overlay, (0, 0))
        
        # Draw dialog box background
        pygame.draw.rect(surface, (40, 40, 40), self.dialog_rect)
        pygame.draw.rect(surface, WHITE, self.dialog_rect, 3)
        
        # Draw title
        title_surf = self._render_outline("Quit Game?", self.title_font, RED, (0, 0, 0), 2)
        title_rect = title_surf.get_rect(centerx=self.dialog_rect.centerx, 
                                        y=self.dialog_rect.y + 50)
        surface.blit(title_surf, title_rect)
        
        # Draw warning text - make it shorter and ensure it fits
        warning_text = "Current progress will be lost!"
        warning_surf = self._render_outline(warning_text, self.subtitle_font, YELLOW, (0, 0, 0), 1)
        warning_rect = warning_surf.get_rect(centerx=self.dialog_rect.centerx, 
                                           y=title_rect.bottom + 45)
        
        # Ensure the warning text fits within dialog bounds
        if warning_rect.right > self.dialog_rect.right - 20:
            # If text is too wide, make it even shorter
            warning_text = "Progress will be lost!"
            warning_surf = self._render_outline(warning_text, self.subtitle_font, YELLOW, (0, 0, 0), 1)
            warning_rect = warning_surf.get_rect(centerx=self.dialog_rect.centerx, 
                                               y=title_rect.bottom + 45)
        
        surface.blit(warning_surf, warning_rect)
        
        # Draw buttons
        for i, (btn_rect, (label, _)) in enumerate(zip(self.btn_rects, self.buttons)):
            # Button colors
            is_selected = (i == self.selected_option)
            bg_color = (80, 80, 80) if is_selected else (60, 60, 60)
            text_color = YELLOW if is_selected else WHITE
            
            # Draw button background
            pygame.draw.rect(surface, bg_color, btn_rect)
            pygame.draw.rect(surface, WHITE, btn_rect, 2)
            
            # Draw button bevel
            if is_selected:
                pygame.draw.rect(surface, YELLOW, btn_rect, 3)
            else:
                # Light bevel
                pygame.draw.line(surface, (200, 200, 200), btn_rect.topleft, 
                               (btn_rect.topright[0]-1, btn_rect.topright[1]))
                pygame.draw.line(surface, (200, 200, 200), btn_rect.topleft, 
                               (btn_rect.topleft[0], btn_rect.bottomleft[1]-1))
                # Dark bevel
                pygame.draw.line(surface, (30, 30, 30), 
                               (btn_rect.left, btn_rect.bottom-1), 
                               (btn_rect.right-1, btn_rect.bottom-1))
                pygame.draw.line(surface, (30, 30, 30), 
                               (btn_rect.right-1, btn_rect.top), 
                               (btn_rect.right-1, btn_rect.bottom))
            
            # Draw button text
            text_surf = self._render_outline(label, self.btn_font, text_color, (0, 0, 0), 1)
            text_rect = text_surf.get_rect(center=btn_rect.center)
            surface.blit(text_surf, text_rect)
