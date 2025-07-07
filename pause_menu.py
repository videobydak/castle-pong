import pygame, sys, os
from config import WIDTH, HEIGHT, WHITE, YELLOW

class PauseMenu:
    """Simple in-game pause interface activated with ESC."""

    def __init__(self):
        self.active = False
        self.bg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.bg.fill((0, 0, 0, 180))

        # ----------------------------------------------------------------
        # Pixel-style fonts & graphics (shared with TutorialOverlay) ------
        # ----------------------------------------------------------------
        self.title_font = self._load_pixel_font(96)
        self.btn_font   = self._load_pixel_font(40)

        self.title_surf = self._render_outline("Paused", self.title_font, YELLOW, (0, 0, 0), 2)
        self.title_rect = self.title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 3))

        # Button definitions: label, callback
        self.buttons = [
            ("Resume", self._resume),
            ("Options", self._options),
            ("Store", self._store),
            ("Exit", self._exit),
        ]
        self._layout_buttons()

        # Track hover state separately so we can rebuild button surfaces on demand
        self._hover_states = [False] * len(self.buttons)

        # Keyboard navigation – index of currently selected button
        self.selected_index: int = 0
        # Ensure first button shows as selected when menu opens
        if self._hover_states:
            self._hover_states[self.selected_index] = True

    def _layout_buttons(self):
        """Precompute button rectangles and text surfaces."""
        gap = 24
        start_y = self.title_rect.bottom + 60

        self.btn_surfs = []
        self.btn_rects = []

        for i, (label, _) in enumerate(self.buttons):
            txt_surf = self._render_outline(label, self.btn_font, WHITE, (0, 0, 0), 1)
            txt_rect = txt_surf.get_rect()
            width  = txt_rect.width  + 40
            height = txt_rect.height + 20
            box_rect = pygame.Rect(0, 0, width, height)
            box_rect.center = (WIDTH // 2, start_y + i * (height + gap))

            # Store tuple of (text surface, text_rect (relative), box_rect)
            self.btn_surfs.append(txt_surf)
            self.btn_rects.append(box_rect)

    # ---------------- callbacks -------------------
    def _resume(self):
        self.active = False
    def _options(self):
        """Open the options menu."""
        try:
            import sys
            _main = sys.modules['__main__']
            if hasattr(_main, 'options_menu'):
                self.active = False  # Close pause menu
                _main.options_menu.open_options()
        except Exception as e:
            print("[PauseMenu] Failed to open options:", e)
    def _store(self):
        """Close pause menu and open the Armory store."""
        try:
            import sys
            _main = sys.modules['__main__']
            if hasattr(_main, 'store'):
                # Close pause menu first
                self.active = False
                current_wave = getattr(_main, 'wave', 1)
                _main.store.open_store(current_wave)
        except Exception as e:
            print("[PauseMenu] Failed to open store:", e)
    def _exit(self):
        """Return to the main menu and pause the game."""
        import sys
        import pygame
        try:
            _main = sys.modules['__main__']
            self.active = False
            if hasattr(_main, 'options_menu'):
                _main.options_menu.active = False
            if hasattr(_main, 'store'):
                _main.store.close_store()
            # Just show the main menu - the game should pause automatically
            if hasattr(_main, 'tutorial_overlay'):
                _main.tutorial_overlay.active = True
                _main.tutorial_overlay.loading = False
                _main.tutorial_overlay.selected_index = 0
                # Reset button hover states to prevent accidental clicks
                for btn in _main.tutorial_overlay.buttons:
                    btn['hover'] = False
                # Clear any pending keyboard state to prevent spacebar from 
                # immediately triggering the Play button
                pygame.event.clear(pygame.KEYDOWN)
                pygame.event.clear(pygame.KEYUP)
            # Switch to menu music
            pygame.mixer.music.fadeout(400)
            try:
                pygame.mixer.music.load(_main.MUSIC_PATH)
                pygame.mixer.music.set_volume(0.6)
                pygame.mixer.music.play(-1)
            except Exception as e:
                print(f"[Audio] Failed to restart tutorial music: {e}")
        except Exception as e:
            print("[PauseMenu] Failed to return to main menu:", e)
            pygame.quit()
            sys.exit()

    # ------------------------------------------------
    def toggle(self):
        # Toggle visibility and reset keyboard navigation state when opened
        self.active = not self.active
        if self.active:
            # Reset selection to first button on open
            self.selected_index = 0
            self._hover_states = [i == 0 for i in range(len(self.buttons))]

    def update(self, events):
        if not self.active:
            return False
        
        consumed_event = False
        # --- Handle keyboard navigation ---
        key_nav = False
        for e in events:
            if e.type == pygame.KEYDOWN:
                consumed_event = True
                if e.key == pygame.K_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.buttons)
                    key_nav = True
                elif e.key == pygame.K_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.buttons)
                    key_nav = True
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    # Activate the currently selected button
                    _, cb = self.buttons[self.selected_index]
                    cb()
                    key_nav = True

        mouse = pygame.mouse.get_pos()
        clicked = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        if clicked:
            consumed_event = True

        for idx, ((label, cb), box) in enumerate(zip(self.buttons, self.btn_rects)):
            # If keyboard navigation was used this frame, rely solely on selected_index for hover state.
            if key_nav:
                hover = (idx == self.selected_index)
            else:
                hover = box.collidepoint(mouse)
                # If mouse moved, update selection highlight to hover
                if hover:
                    self.selected_index = idx
            self._hover_states[idx] = hover
            if hover and clicked:
                cb()
        
        return consumed_event

    def draw(self, surface):
        if not self.active:
            return
        surface.blit(self.bg, (0, 0))

        # Title with drop shadow for depth
        shadow = self.title_surf.copy()
        shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow, self.title_rect.move(3, 3))
        surface.blit(self.title_surf, self.title_rect)

        # Draw each button box with pixel-art bevel and hover effect
        for idx, ((label, _), txt_surf, box_rect, hover) in enumerate(zip(self.buttons, self.btn_surfs, self.btn_rects, self._hover_states)):
            # Treat button as hovered if it is selected via keyboard
            hover_or_selected = hover or (idx == self.selected_index)

            base_col  = (60, 60, 60)
            hover_col = (110, 110, 110)

            # Background
            pygame.draw.rect(surface, hover_col if hover_or_selected else base_col, box_rect)
            # Border (2 px)
            pygame.draw.rect(surface, (0, 0, 0), box_rect, 2)
            # Bevel effect
            pygame.draw.line(surface, (200, 200, 200), box_rect.topleft, (box_rect.topright[0]-1, box_rect.topright[1]))
            pygame.draw.line(surface, (200, 200, 200), box_rect.topleft, (box_rect.topleft[0], box_rect.bottomleft[1]-1))
            pygame.draw.line(surface, (30, 30, 30), (box_rect.left, box_rect.bottom-1), (box_rect.right-1, box_rect.bottom-1))
            pygame.draw.line(surface, (30, 30, 30), (box_rect.right-1, box_rect.top), (box_rect.right-1, box_rect.bottom))

            # Center text inside box
            txt_rect = txt_surf.get_rect(center=box_rect.center)
            # Replace text surface color when hovering
            if hover_or_selected:
                txt_surf = self._render_outline(label, self.btn_font, YELLOW, (0, 0, 0), 1)
            surface.blit(txt_surf, txt_rect)

            # Extra yellow border for selected button (keyboard navigation)
            if idx == self.selected_index:
                pygame.draw.rect(surface, YELLOW, box_rect, 4)

    # ----------------------------------------------------------------
    # Helper methods (copied from TutorialOverlay for consistency) ----
    # ----------------------------------------------------------------
    def _render_outline(self, text: str, font: pygame.font.Font, fg, outline, px: int = 1):
        """Render *text* with a pixel outline of *px* thickness."""
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
        """Load bundled PressStart2P font or fallback to monospace."""
        pix_path = 'PressStart2P-Regular.ttf'
        if os.path.isfile(pix_path):
            try:
                return pygame.font.Font(pix_path, size)
            except Exception:
                pass
        return pygame.font.SysFont('Courier New', size, bold=True) 