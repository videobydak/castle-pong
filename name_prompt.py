import pygame
from config import WIDTH, HEIGHT, WHITE, YELLOW
from utils import load_font


class NamePrompt:
    """Overlay to enter (and confirm) the player's leaderboard name."""

    MAX_LEN = 12

    def __init__(self, initial_name: str = ""):
        self.active = True  # Input allowed
        self.done = False   # Finished & confirmed
        self.canceled = False  # User pressed Esc during edit stage

        self.name = initial_name[: self.MAX_LEN]

        # Two-stage workflow: 'edit' → 'confirm'
        self.stage = "edit"

        px_font = load_font("PressStart2P-Regular.ttf", 32)
        self.font_big = px_font
        self.font_small = load_font("PressStart2P-Regular.ttf", 16)

    # -------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        if event.type == pygame.KEYDOWN:
            if self.stage == "edit":
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    # Move to confirm stage
                    self.stage = "confirm"
                    return True
                if event.key == pygame.K_ESCAPE:
                    self.canceled = True
                    self.active = False
                    return True
                if event.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                    return True
                if event.key == pygame.K_SPACE and len(self.name) < self.MAX_LEN:
                    self.name += " "
                    return True
                ch = event.unicode
                if ch.isprintable() and len(self.name) < self.MAX_LEN and ch not in "\t\n\r":
                    self.name += ch
                    return True

            elif self.stage == "confirm":
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    # Accept name
                    self.done = True
                    self.active = False
                    return True
                if event.key == pygame.K_ESCAPE:
                    # Back to edit
                    self.stage = "edit"
                    return True
        return False

    # -------------------------------------------------------------
    def draw(self, surface: pygame.Surface):
        if not (self.active or self.done or self.canceled):
            return

        # Dim background
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(220)
        surface.blit(overlay, (0, 0))

        if self.stage == "edit":
            self._draw_edit(surface)
        else:
            self._draw_confirm(surface)

    # -------------------------------------------------------------
    def _draw_edit(self, surface):
        prompt = self.font_big.render("ENTER NAME", True, YELLOW)
        surface.blit(prompt, prompt.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 70)))

        text = self.font_big.render(self.name or "_", True, WHITE)
        box = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        pygame.draw.rect(surface, (80, 80, 80), box.inflate(30, 26))
        pygame.draw.rect(surface, WHITE, box.inflate(30, 26), 3)
        surface.blit(text, box)

        hint = self.font_small.render("ENTER = next  •  ESC = cancel  •  SPACE allowed", True, WHITE)
        surface.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 70)))

    def _draw_confirm(self, surface):
        msg = f"Submit as '{self.name or 'Anonymous'}'?"
        txt = self.font_big.render(msg.upper(), True, YELLOW)
        surface.blit(txt, txt.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))

        hint = self.font_small.render("ENTER = confirm  •  ESC = edit", True, WHITE)
        surface.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40))) 