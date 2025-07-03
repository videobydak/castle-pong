import pygame
from config import *
import math
from utils import make_wood

class Paddle:
    def __init__(self, side):
        self.side = side  # 'top','bottom','left','right'
        self.width = PADDLE_LEN
        self.logical_width = PADDLE_LEN  # The true intended width
        self.target_width = PADDLE_LEN  # For smooth animation
        self.width_anim_speed = 0.0     # Pixels per frame
        self.width_anim_time = 0.3      # Animation duration in seconds
        self._width_animating = False
        self._width_anim_start = None
        self._width_anim_from = None
        self._width_anim_to = None
        self._width_anim_total_frames = int(self.width_anim_time * FPS)
        self._width_anim_frame = 0
        self.flicker = False  # For blue flicker effect
        self.vel = 0  # current velocity along movement axis
        self.inward_vel = 0.0  # velocity for inward bump
        self.inward_offset = 0.0  # offset for inward bump
        # small visual offset for impact shake
        self.offset = pygame.Vector2(0,0)
        # --- bump (hit) mechanic ---
        self._bump_target   = 0.0   # 0 (retracted) or 1 (fully extended)
        self._bump_progress = 0.0   # smooth progress toward target
        self._bump_offset   = 0.0   # current pixel offset already applied to rect
        self.BUMP_DIST      = 20    # reduced inward distance for stability
        # factor used externally to boost ball speed when bouncing (was 1.7)
        self.bump_strength = 2.8
        # curvature radius for concave paddle
        self.curve_radius = 250
        # store instantaneous bump extension speed (pixels per frame)
        self._bump_speed   = 0.0
        self.widen_stack = 0
        self.widen_original_width = None
        self.reset()
        # Fireball immunity timestamp (ms) after sticky launch
        self.fireball_immunity_until = 0
        # Heal pulse effect timer (frames)
        self.heal_pulse_timer = 0
    def reset(self):
        # Called only on init; not after damage/powerups.
        if self.side in ('top','bottom'):
            if self.side == 'top':
                y = PADDLE_MARGIN
            else:
                y = HEIGHT - PADDLE_THICK - BOTTOM_PADDLE_MARGIN
            self.rect = pygame.Rect((WIDTH-self.width)//2,
                                    y,
                                    self.width, PADDLE_THICK)
        else:
            x = PADDLE_MARGIN if self.side=='left' else WIDTH - PADDLE_THICK - PADDLE_MARGIN
            self.rect = pygame.Rect(x,
                                    (HEIGHT-self.width)//2,
                                    PADDLE_THICK, self.width)
        self.dir = 0  # -1,0,+1
        self.base_len = PADDLE_LEN
        # Reset fireball immunity
        self.fireball_immunity_until = 0
        self.width = PADDLE_LEN
        self.logical_width = PADDLE_LEN
        self.target_width = PADDLE_LEN
        self._width_animating = False
        self.flicker = False
    def move(self):
        # Inertial movement with acceleration and friction (side-to-side or up/down)
        if self.side in ('top','bottom'):
            if self.dir != 0:
                self.vel += self.dir * PADDLE_ACCEL
                self.vel = max(-PADDLE_MAX_SPEED, min(PADDLE_MAX_SPEED, self.vel))
            else:
                self.vel *= PADDLE_FRICTION
                if abs(self.vel) < 0.1:
                    self.vel = 0
            self.rect.x += self.vel
            self.rect.x = max(PADDLE_MARGIN, min(WIDTH-self.rect.width-PADDLE_MARGIN, self.rect.x))
            if self.rect.x in (PADDLE_MARGIN, WIDTH-self.rect.width-PADDLE_MARGIN):
                self.vel = 0
        else:
            if self.dir != 0:
                self.vel += self.dir * PADDLE_ACCEL
                self.vel = max(-PADDLE_MAX_SPEED, min(PADDLE_MAX_SPEED, self.vel))
            else:
                self.vel *= PADDLE_FRICTION
                if abs(self.vel) < 0.1:
                    self.vel = 0
            self.rect.y += self.vel
            self.rect.y = max(PADDLE_MARGIN, min(HEIGHT-self.rect.height-PADDLE_MARGIN, self.rect.y))
            if self.rect.y in (PADDLE_MARGIN, HEIGHT-self.rect.height-PADDLE_MARGIN):
                self.vel = 0
        # --- Inward bump physics ---
        SPRING = 1.2  # spring force to return to base
        FRICTION = 0.85  # friction for inward motion
        # Update inward velocity and offset
        self.inward_vel -= self.inward_offset * SPRING * 0.1
        self.inward_vel *= FRICTION
        self.inward_offset += self.inward_vel
        # Clamp inward offset to reasonable range (e.g., max 24 px)
        max_inward = 24
        if self.inward_offset > max_inward:
            self.inward_offset = max_inward
            self.inward_vel = 0
        elif self.inward_offset < -max_inward:
            self.inward_offset = -max_inward
            self.inward_vel = 0
        # decay shake offset toward zero for nice easing
        self.offset *= 0.85
        if self.offset.length_squared() < 0.01:
            self.offset.xy = (0,0)

        # --- smooth bump extension/retraction ---
        # progress follows target; higher factor makes bump extend more quickly
        self._bump_progress += (self._bump_target - self._bump_progress) * 0.3

        desired_offset = self._bump_progress * self.BUMP_DIST
        delta = desired_offset - self._bump_offset  # signed pixel movement this frame
        # record absolute bump speed for collision boost logic
        self._bump_speed = abs(delta)

        if abs(delta) > 0.01:
            if self.side == 'top':
                self.rect.y += delta
            elif self.side == 'bottom':
                self.rect.y -= delta
            elif self.side == 'left':
                self.rect.x += delta
            else:  # right
                self.rect.x -= delta
            self._bump_offset = desired_offset
    def _arc_points(self, outer=True, segments=32):
        """Return list of points approximating the paddle arc (outer or inner)."""
        pts = []
        if self.side in ('top', 'bottom'):
            cx = self.rect.centerx
            if self.side == 'top':
                cy = self.rect.centery + self.curve_radius  # centre below paddle
                direction = -1  # arc faces downward toward castle
            else:
                cy = self.rect.centery - self.curve_radius  # centre above paddle
                direction = 1   # arc faces upward toward castle

            for i in range(segments + 1):
                t = i / segments
                x = self.rect.left + t * self.rect.width
                dx = x - cx
                try:
                    y_off = math.sqrt(self.curve_radius**2 - dx**2)
                except ValueError:
                    y_off = 0
                y = cy + direction * y_off
                if not outer:
                    y += direction * (self.rect.height)
                pts.append((x, y))
        else:  # left/right paddles (vertical arc)
            cy = self.rect.centery
            if self.side == 'left':
                cx = self.rect.centerx + self.curve_radius  # centre right of paddle
                direction = -1  # arc faces right toward castle
            else:
                cx = self.rect.centerx - self.curve_radius  # centre left of paddle
                direction = 1   # arc faces left toward castle

            for i in range(segments + 1):
                t = i / segments
                y = self.rect.top + t * self.rect.height
                dy = y - cy
                try:
                    x_off = math.sqrt(self.curve_radius**2 - dy**2)
                except ValueError:
                    x_off = 0
                x = cx + direction * x_off
                if not outer:
                    x += direction * (self.rect.width)
                pts.append((x, y))
        return pts

    def draw(self, screen, overlay_color=None):
        # Apply impact shake offset
        offset_vec = pygame.Vector2(int(self.offset.x), int(self.offset.y))
        # Add inward offset to rect for drawing
        draw_rect = self.rect.move(offset_vec)
        if self.side == 'bottom':
            draw_rect = draw_rect.move(0, -int(self.inward_offset))
        elif self.side == 'top':
            draw_rect = draw_rect.move(0, int(self.inward_offset))
        elif self.side == 'left':
            draw_rect = draw_rect.move(int(self.inward_offset), 0)
        elif self.side == 'right':
            draw_rect = draw_rect.move(-int(self.inward_offset), 0)

        # Build wood surface (cache per size)
        key = (draw_rect.width, draw_rect.height)
        if not hasattr(self, '_wood_cache'):
            self._wood_cache = {}
        if key not in self._wood_cache:
            tile = make_wood(8)
            surf = pygame.Surface((draw_rect.width, draw_rect.height))
            for y in range(0, draw_rect.height, 8):
                for x in range(0, draw_rect.width, 8):
                    surf.blit(tile, (x, y))
            self._wood_cache[key] = surf
        wood_surf = self._wood_cache[key]

        screen.blit(wood_surf, draw_rect)
        pygame.draw.rect(screen, (110, 60, 20), draw_rect, 2)

        # overlay (power-up tint)
        if overlay_color:
            # Flicker logic: if self.flicker is True, only draw overlay on even frames
            draw_overlay = True
            if self.flicker:
                # Flicker at ~8Hz (every 7-8 frames at 60-120 FPS)
                draw_overlay = (pygame.time.get_ticks() // 120) % 2 == 0
            if draw_overlay:
                mask = pygame.Surface((draw_rect.width, draw_rect.height), pygame.SRCALPHA)
                mask.fill((*overlay_color, 140))
                screen.blit(mask, draw_rect)

        # ---------------------------
        # Heal pulse visual feedback
        # ---------------------------
        if self.heal_pulse_timer > 0:
            # Pulsate alpha using a sine wave for a soft flash
            pulse_alpha = int(180 * abs(math.sin(self.heal_pulse_timer * 0.3)))
            pulse_surf = pygame.Surface((draw_rect.width, draw_rect.height), pygame.SRCALPHA)
            pulse_surf.fill((255, 0, 0, pulse_alpha))
            screen.blit(pulse_surf, draw_rect)
            # countdown
            self.heal_pulse_timer -= 1
    def shrink(self):
        # shorten by 20%, keep current centre position
        self.logical_width = max(20, int(self.logical_width*0.8))
        self._start_width_animation(self.logical_width)
    def widen(self):
        """Restore paddle to its base length. Decrement stack."""
        if self.widen_stack > 0:
            self.widen_stack -= 1
            if self.widen_stack == 0:
                self.logical_width = PADDLE_LEN
                self._start_width_animation(self.logical_width)
                self.widen_original_width = None
        # If stack > 0, do nothing (still widened)
    def enlarge(self):
        """Temporarily enlarge the paddle by 50 % per stack. Stacks with previous widens."""
        if self.widen_stack == 0 and self.widen_original_width is None:
            # Record the width before any widen
            self.widen_original_width = self.logical_width
        self.widen_stack += 1
        self.logical_width = min(WIDTH - 2*PADDLE_MARGIN, int(self.logical_width * 1.5)) if self.side in ('top','bottom') else min(HEIGHT - 2*PADDLE_MARGIN, int(self.logical_width * 1.5))
        self._start_width_animation(self.logical_width)
    def grow_on_hit(self, percent=0.1):
        """Increase paddle width by a percentage (default 10%) if widen is active."""
        if self.widen_stack > 0:
            self.logical_width = min(WIDTH - 2*PADDLE_MARGIN, int(self.logical_width * (1 + percent))) if self.side in ('top','bottom') else min(HEIGHT - 2*PADDLE_MARGIN, int(self.logical_width * (1 + percent)))
            self._start_width_animation(self.logical_width)
    def clear_widen(self):
        """Immediately restore the paddle to its base width and clear all widen effects."""
        if self.widen_stack > 0:
            self.logical_width = PADDLE_LEN
            self._start_width_animation(self.logical_width)
            self.widen_stack = 0
            self.widen_original_width = None
    def update(self):
        # Call this every frame to animate width
        if self._width_animating:
            self._width_anim_frame += 1
            t = self._width_anim_frame / max(1, self._width_anim_total_frames)
            t = min(1.0, t)
            # Ease in-out cubic
            ease = 3*t**2 - 2*t**3
            new_width = int(self._width_anim_from + (self._width_anim_to - self._width_anim_from) * ease)
            if self.side in ('top','bottom'):
                center = self.rect.centerx
                self.rect.width = new_width
                self.rect.x = max(PADDLE_MARGIN, min(WIDTH-self.rect.width-PADDLE_MARGIN, center - new_width//2))
            else:
                center = self.rect.centery
                self.rect.height = new_width
                self.rect.y = max(PADDLE_MARGIN, min(HEIGHT-self.rect.height-PADDLE_MARGIN, center - new_width//2))
            self.width = new_width
            if t >= 1.0:
                self._width_animating = False
    def _start_width_animation(self, to_width):
        self._width_anim_from = self.width
        self._width_anim_to = int(to_width)
        self._width_anim_frame = 0
        self._width_anim_total_frames = int(self.width_anim_time * FPS)
        self._width_animating = True

    # Interface ---------------------------------------------------
    def set_bump_pressed(self, pressed: bool):
        """Inform paddle whether space-bar is currently pressed."""
        self._bump_target = 1.0 if pressed else 0.0

    def is_bumping(self):
        """Return True when paddle is extended far enough to boost hits."""
        return self._bump_progress > 0.25 

    # ------------------------------------------------------------------
    # Physics helper
    # ------------------------------------------------------------------
    def get_bump_boost(self):
        """Return a multiplier ≥ 1 that depends on current bump speed.

        The boost scales up linearly from 1 × (no extra speed) when the
        paddle is stationary to *bump_strength* when the paddle is moving
        inward at its maximum design speed (Δ=BUMP_DIST per frame)."""
        # normalise 0..1 range using BUMP_DIST as the reference maximum
        ratio = min(1.0, self._bump_speed / self.BUMP_DIST)
        return 1.0 + (self.bump_strength - 1.0) * ratio 

    def bump(self):
        """Apply a strong, short-lived velocity impulse inward (toward the playfield)."""
        IMPULSE = 12  # Tune as needed for feel
        print(f"[DEBUG] bump() before: side={self.side}, vel={self.vel}, inward_vel={self.inward_vel}")
        if self.side == 'bottom':
            self.inward_vel -= IMPULSE  # up
        elif self.side == 'top':
            self.inward_vel += IMPULSE  # down
        elif self.side == 'left':
            self.inward_vel += IMPULSE  # right
        elif self.side == 'right':
            self.inward_vel -= IMPULSE  # left
        print(f"[DEBUG] bump() after: side={self.side}, vel={self.vel}, inward_vel={self.inward_vel}") 