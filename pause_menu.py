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
        """Return to main menu instead of quitting the game."""
        try:
            import sys
            _main = sys.modules['__main__']
            if hasattr(_main, 'tutorial_overlay'):
                # Close pause menu and activate main menu
                self.active = False
                # Reset the tutorial overlay to show main menu
                _main.tutorial_overlay.active = True
                _main.tutorial_overlay.loading = False
                # Stop current music and restart tutorial music
                pygame.mixer.music.fadeout(400)
                try:
                    pygame.mixer.music.load(_main.MUSIC_PATH)
                    pygame.mixer.music.set_volume(0.6)
                    pygame.mixer.music.play(-1)
                except Exception as e:
                    print(f"[Audio] Failed to restart tutorial music: {e}")
        except Exception as e:
            print("[PauseMenu] Failed to return to main menu:", e)
            # Fallback to quit if we can't return to main menu
            pygame.quit()
            sys.exit()

    # ------------------------------------------------
    def toggle(self):
        self.active = not self.active

    def update(self, events):
        if not self.active:
            return
        mouse = pygame.mouse.get_pos()
        clicked = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        for idx, ((label, cb), box) in enumerate(zip(self.buttons, self.btn_rects)):
            hover = box.collidepoint(mouse)
            self._hover_states[idx] = hover
            if hover and clicked:
                cb()

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
        for (label, _), txt_surf, box_rect, hover in zip(self.buttons, self.btn_surfs, self.btn_rects, self._hover_states):
            base_col  = (60, 60, 60)
            hover_col = (110, 110, 110)

            # Background
            pygame.draw.rect(surface, hover_col if hover else base_col, box_rect)
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
            if hover:
                txt_surf = self._render_outline(label, self.btn_font, YELLOW, (0, 0, 0), 1)
            surface.blit(txt_surf, txt_rect)

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