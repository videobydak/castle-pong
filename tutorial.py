import pygame, sys, os, random, math
from config import WIDTH, HEIGHT, WHITE, YELLOW, get_key_name, get_control_key
from utils import generate_grass


class TutorialOverlay:
    """Main menu overlay: minimalist pixel-art aesthetic with three buttons.

    This completely replaces the previous tutorial screen.  No balls, paddles
    or castle — just a clean title, buttons, and a gentle animated star-field
    background.  The rest of the game still references ``TutorialOverlay``, so
    we keep the same class name.
    """

    def __init__(self, auto_start_music=True):
        self.active: bool = True
        self.loading: bool = False  # New loading state
        self.loading_angle: float = 0.0  # For spinning loader
        self.loading_start_time: int = 0  # When loading started
        self.selected_index: int = 0  # Track which button is selected for keyboard nav

        # -------------------------------------------------------------
        # Background music – loop dedicated menu track
        # -------------------------------------------------------------
        self.MENU_MUSIC = "menu.mp3"
        if auto_start_music:
            try:
                pygame.mixer.music.load(self.MENU_MUSIC)
                pygame.mixer.music.set_volume(0.6)
                pygame.mixer.music.play(-1)
            except pygame.error as e:
                print(f"[Audio] Failed to load menu music '{self.MENU_MUSIC}':", e)

        # -------------------------------------------------------------
        # Fonts & static graphics
        # -------------------------------------------------------------
        self.title_font = self._load_pixel_font(96)
        self.btn_font   = self._load_pixel_font(40)

        self.title_surf = self._render_outline("Castle Pong", self.title_font,
                                             YELLOW, (0, 0, 0), 2)
        self.title_rect = self.title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 3))

        # Buttons configuration ------------------------------------------------
        self.buttons = [
            {"label": "Play",        "callback": self._on_play},
            {"label": "Leaderboard", "callback": self._on_leaderboard},
            {"label": "Options",     "callback": self._on_options},
            {"label": "Quit",        "callback": self._on_quit},
        ]
        self._layout_buttons()

        # Leaderboard mode state -------------------------------------
        self.mode = "menu"  # "menu" or "leaderboard"
        self.board_wave = 1
        self.board_rows = []  # Fetched leaderboard rows
        self.board_scroll = 0
        self.last_board_fetch = 0

        # ------------------------------------------------------------------
        # Scrolling grass background (re-uses game grass tile) -------------
        # ------------------------------------------------------------------
        self.grass      = generate_grass(WIDTH, HEIGHT)
        self.scroll_y   = 0.0   # current vertical offset (px)
        self.scroll_spd = 20.0  # pixels / second

        # Title bobbing animation phase & last-update timestamp
        self._title_phase = 0.0
        self._last_update = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _layout_buttons(self):
        """Prepare button metadata including pixel-style rectangles."""
        gap = 24
        start_y = self.title_rect.bottom + 60
        for i, btn in enumerate(self.buttons):
            txt_surf = self._render_outline(btn["label"], self.btn_font, WHITE, (0, 0, 0), 1)
            txt_rect = txt_surf.get_rect()
            # Padding around text
            width  = txt_rect.width  + 40
            height = txt_rect.height + 20
            box_rect = pygame.Rect(0, 0, width, height)
            box_rect.center = (WIDTH // 2, start_y + i * (height + gap))
            btn.update({
                "surf": txt_surf,
                "txt_rect": txt_rect,
                "box_rect": box_rect,
                "hover": False,
            })

    # ------------------------------------------------------------------
    # Public API expected by main loop
    # ------------------------------------------------------------------
    def update(self, events):
        if not self.active:
            return

        if self.mode == "leaderboard":
            # Handle simple back navigation
            for e in events:
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.mode = "menu"
                    return
            return  # Leaderboard mode doesn't update menu interactions
        
        # Update loading spinner if in loading state
        if self.loading:
            self.loading_angle += 8.0  # Degrees per frame for smooth rotation
            if self.loading_angle >= 360:
                self.loading_angle -= 360
            # Don't process button clicks while loading
            print(f"[DEBUG] Loading... angle={self.loading_angle:.1f}")
            return
        
        # Keyboard navigation
        key_nav = False
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == get_control_key('right_paddle_up'):
                    self.selected_index = (self.selected_index - 1) % len(self.buttons)
                    key_nav = True
                elif e.key == get_control_key('right_paddle_down'):
                    self.selected_index = (self.selected_index + 1) % len(self.buttons)
                    key_nav = True
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.buttons[self.selected_index]["callback"]()
                    key_nav = True
        
        mouse = pygame.mouse.get_pos()
        click = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        for i, btn in enumerate(self.buttons):
            # If keyboard nav was used, only highlight selected_index
            if key_nav:
                btn['hover'] = (i == self.selected_index)
            else:
                btn['hover'] = btn['box_rect'].collidepoint(mouse)
            if btn['hover'] and click and not self.loading:
                btn['callback']()

        # ---------------------------------------------------------
        # Use frame time Δt for smooth animation -----------------
        # ---------------------------------------------------------
        now = pygame.time.get_ticks()
        dt = (now - self._last_update) / 1000.0
        self._last_update = now

        # Scroll background downwards
        self.scroll_y = (self.scroll_y + self.scroll_spd * dt) % HEIGHT

        # Title bobbing phase ----------------------------------------
        self._title_phase = (self._title_phase + dt * 2.0) % (2 * math.pi)

    def draw(self, surface: pygame.Surface):
        if not self.active:
            return
        if self.mode == "leaderboard":
            self._draw_leaderboard(surface)
            return
        # ----------------------------------------------------------
        #  Scrolling grass background
        # ----------------------------------------------------------
        y_off = int(self.scroll_y)
        surface.blit(self.grass, (0, y_off - HEIGHT))
        surface.blit(self.grass, (0, y_off))

        # Title shadow + text
        self._draw_title(surface)

        # Buttons ------------------------------------------------------
        for i, btn in enumerate(self.buttons):
            box   = btn['box_rect']
            hover = btn['hover'] or (i == self.selected_index)
            
            # Grey out buttons during loading
            if self.loading:
                base_col = (40, 40, 40)
                hover_col = (40, 40, 40)
                text_col = (100, 100, 100)
            else:
                base_col = (60, 60, 60)
                hover_col = (110, 110, 110)
                text_col = WHITE
            
            # Background fill
            pygame.draw.rect(surface, hover_col if (hover and not self.loading) else base_col, box)
            # Border (2-pixel) with light top/left and dark bottom/right for depth
            pygame.draw.rect(surface, (0, 0, 0), box, 2)
            # Extra border for selected (keyboard) button
            if not self.loading and i == self.selected_index:
                pygame.draw.rect(surface, YELLOW, box, 4)
            # Bevel effect (only if not loading)
            if not self.loading:
                pygame.draw.line(surface, (200, 200, 200), box.topleft, (box.topright[0]-1, box.topright[1]))
                pygame.draw.line(surface, (200, 200, 200), box.topleft, (box.topleft[0], box.bottomleft[1]-1))
                pygame.draw.line(surface, (30, 30, 30), (box.left, box.bottom-1), (box.right-1, box.bottom-1))
                pygame.draw.line(surface, (30, 30, 30), (box.right-1, box.top), (box.right-1, box.bottom))
            
            # Text with appropriate color
            if self.loading and btn["label"] == "Play":
                # Render greyed out text
                txt_surf = self._render_outline(btn["label"], self.btn_font, text_col, (0, 0, 0), 1)
            else:
                # Use yellow text when hovered/selected (matching pause menu style)
                if hover and not self.loading:
                    txt_surf = self._render_outline(btn["label"], self.btn_font, YELLOW, (0, 0, 0), 1)
                else:
                    txt_surf = btn['surf'] if not self.loading else self._render_outline(btn["label"], self.btn_font, text_col, (0, 0, 0), 1)
            txt_rect = txt_surf.get_rect(center=box.center)
            surface.blit(txt_surf, txt_rect)
            
            # Draw loading spinner over Play button
            if self.loading and btn["label"] == "Play":
                print(f"[DEBUG] Drawing spinner at angle {self.loading_angle:.1f}")
                center_x, center_y = box.center
                radius = 15
                # Draw spinning circle segments with solid colors
                for j in range(8):
                    angle = math.radians(self.loading_angle + j * 45)
                    # Use different shades instead of alpha
                    brightness = 255 - (j * 25)
                    if brightness < 100:
                        brightness = 100
                    color = (brightness, brightness, 0)  # Yellow gradient
                    start_x = int(center_x + math.cos(angle) * (radius - 5))
                    start_y = int(center_y + math.sin(angle) * (radius - 5))
                    end_x = int(center_x + math.cos(angle) * radius)
                    end_y = int(center_y + math.sin(angle) * radius)
                    pygame.draw.line(surface, color, (start_x, start_y), (end_x, end_y), 3)

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def _render_outline(self, text: str, font: pygame.font.Font, fg, outline, px: int = 1):
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

    def _draw_title(self, surface):
        # Vertical bobbing offset produces a subtle floating effect
        bob = int(math.sin(self._title_phase) * 4)
        dest_rect = self.title_rect.move(0, bob)

        shadow = self.title_surf.copy()
        # Multiply RGB by 0 while preserving alpha -> transparent background, black glyphs only
        shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow, dest_rect.move(3, 3))
        surface.blit(self.title_surf, dest_rect)

    def _load_pixel_font(self, size):
        """Load a bundled TTF pixel font if available, else fallback to monospace."""
        from utils import load_font
        return load_font('PressStart2P-Regular.ttf', size)

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------
    def _on_play(self):
        print("[DEBUG] Play button clicked - entering loading state")
        # First reset all game state to start fresh
        import sys
        _main = sys.modules['__main__']
        if hasattr(_main, 'return_to_main_menu'):
            # Reset everything but don't show the menu again
            _main.return_to_main_menu(show_menu=False)
        # Enter loading state instead of immediately starting game
        self.loading = True
        self.loading_start_time = pygame.time.get_ticks()
        # Stop current menu music fadeout
        pygame.mixer.music.fadeout(400)
        # Inform main module that tutorial music should stop looping
        _main.tutorial_looping = False

    def _on_options(self):
        """Open the options menu."""
        try:
            import sys
            _main = sys.modules['__main__']
            if hasattr(_main, 'options_menu'):
                _main.options_menu.open_options()
        except Exception as e:
            print("[TutorialOverlay] Failed to open options:", e)

    def _on_quit(self):
        pygame.quit()
        sys.exit()

    def complete_loading(self):
        """Called by main loop when map generation is complete"""
        print("[DEBUG] Loading complete - starting game")
        pygame.mixer.music.fadeout(400)
        self.active = False
        self.loading = False
        # Start wave soundtrack like regular waves
        import sys
        _main = sys.modules['__main__']
        _main.tutorial_looping = False  # ensure tutorial music logic disables

        if getattr(_main, 'start_random_wave_music', None):
            _main.start_random_wave_music()

    def _on_leaderboard(self):
        """Activate leaderboard view."""
        self.mode = "leaderboard"
        self._refresh_board()

    def _refresh_board(self):
        import time, leaderboard as lb
        self.board_rows = lb.get_top_scores(limit=20)
        self.last_board_fetch = time.time()

    def _draw_leaderboard(self, surface: pygame.Surface):
        # Simple centered text list
        bg = pygame.Surface((WIDTH, HEIGHT))
        bg.fill((0, 0, 0))
        bg.set_alpha(200)
        surface.blit(bg, (0, 0))

        title = self._render_outline("Global Leaderboard", self.btn_font, YELLOW, (0, 0, 0), 2)
        rect = title.get_rect(center=(WIDTH // 2, 120))
        surface.blit(title, rect)

        # Define column widths and spacing for better layout
        column_widths = {
            'rank': 120,     # RANK column - wider for better spacing
            'name': 400,     # NAME column - much wider for longer names
            'wave': 150,     # WAVE column - wider for better spacing
            'time': 200,     # TIME column - wider for MM:SS format
            'score': 200     # SCORE column - wider for large numbers
        }
        
        # Calculate total width of all columns
        total_columns_width = sum(column_widths.values())
        
        # Calculate starting X position to center the entire column group
        start_x = (WIDTH - total_columns_width) // 2
        
        # Calculate X positions for each column
        column_positions = {}
        current_x = start_x
        for col_name, width in column_widths.items():
            column_positions[col_name] = current_x
            current_x += width

        # Draw column headers
        header_font = self._load_pixel_font(20)
        header_y = rect.bottom + 15
        
        rank_header = header_font.render("RANK", True, (200, 200, 200))
        name_header = header_font.render("NAME", True, (200, 200, 200))
        wave_header = header_font.render("WAVE", True, (200, 200, 200))
        time_header = header_font.render("TIME", True, (200, 200, 200))
        score_header = header_font.render("SCORE", True, (200, 200, 200))
        
        # Position headers using calculated positions
        surface.blit(rank_header, (column_positions['rank'], header_y))
        surface.blit(name_header, (column_positions['name'], header_y))
        surface.blit(wave_header, (column_positions['wave'], header_y))
        surface.blit(time_header, (column_positions['time'], header_y))
        surface.blit(score_header, (column_positions['score'], header_y))

        y = header_y + 35
        rank_font = self._load_pixel_font(28)
        for idx, row in enumerate(self.board_rows, 1):
            # Format duration as MM:SS
            duration_sec = row.get('duration', 0)
            minutes = int(duration_sec // 60)
            seconds = int(duration_sec % 60)
            time_str = f"{minutes}:{seconds:02d}"
            
            # Render each column
            rank_txt = rank_font.render(f"{idx}", True, WHITE)
            # Allow longer names to display (up to 20 characters instead of 10)
            name_txt = rank_font.render(f"{row['name'][:20]}", True, WHITE)
            wave_txt = rank_font.render(f"{row.get('wave', 1)}", True, WHITE)
            time_txt = rank_font.render(time_str, True, WHITE)
            score_txt = rank_font.render(f"{row.get('score', 0)}", True, WHITE)
            
            # Position each column using calculated positions
            surface.blit(rank_txt, (column_positions['rank'], y))
            surface.blit(name_txt, (column_positions['name'], y))
            surface.blit(wave_txt, (column_positions['wave'], y))
            surface.blit(time_txt, (column_positions['time'], y))
            surface.blit(score_txt, (column_positions['score'], y))
            y += 32

        hint_font = self._load_pixel_font(18)
        hint = hint_font.render("ESC to back", True, WHITE)
        hint_rect = hint.get_rect(center=(WIDTH // 2, HEIGHT - 60))
        surface.blit(hint, hint_rect)

    # --- Legacy gradient generator retained for reference, unused now ---
    def _create_background(self):
        return pygame.Surface((1, 1))  # placeholder (no longer used) 