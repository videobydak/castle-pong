import pygame, sys
from config import WIDTH, HEIGHT, WHITE, YELLOW

class PauseMenu:
    """Simple in-game pause interface activated with ESC."""

    def __init__(self):
        self.active = False
        self.bg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.bg.fill((0, 0, 0, 180))
        self.font_title = pygame.font.SysFont(None, 96, bold=True)
        self.font_btn   = pygame.font.SysFont(None, 48, bold=True)
        self.title_surf = self.font_title.render("Paused", True, YELLOW)
        self.title_rect = self.title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 3))
        # Button definitions: label, callback stub
        self.buttons = [
            ("Resume", self._resume),
            ("Options", self._options),
            ("Store", self._store),
            ("Exit", self._exit),
        ]
        self._layout_buttons()

    def _layout_buttons(self):
        gap = 20
        btn_h = self.font_btn.get_height()
        start_y = self.title_rect.bottom + 40
        self.btn_surfs = []
        self.btn_rects = []
        for i, (label, _) in enumerate(self.buttons):
            surf = self.font_btn.render(label, True, WHITE)
            rect = surf.get_rect(center=(WIDTH // 2, start_y + i * (btn_h + gap)))
            self.btn_surfs.append(surf)
            self.btn_rects.append(rect)

    # ---------------- callbacks -------------------
    def _resume(self):
        self.active = False
    def _options(self):
        pass  # placeholder
    def _store(self):
        pass  # placeholder
    def _exit(self):
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
        for (label, cb), surf, rect in zip(self.buttons, self.btn_surfs, self.btn_rects):
            if rect.collidepoint(mouse) and clicked:
                cb()

    def draw(self, surface):
        if not self.active:
            return
        surface.blit(self.bg, (0, 0))
        surface.blit(self.title_surf, self.title_rect)
        mouse = pygame.mouse.get_pos()
        for (label, _), surf, rect in zip(self.buttons, self.btn_surfs, self.btn_rects):
            # recolor on hover
            if rect.collidepoint(mouse):
                surf = self.font_btn.render(label, True, YELLOW)
            else:
                surf = self.font_btn.render(label, True, WHITE)
            surface.blit(surf, rect) 