import pygame
import random
import math
import os

from config import WIDTH, HEIGHT, PADDLE_THICK
from paddle import Paddle
from utils import Particle, load_font

class PaddleIntro:
    """Handles introductory animation when a new paddle is unlocked."""
    def __init__(self, side: str, sounds: dict, load_sound_func, intro_font, silent_preload=False):
        self.side = side
        self.silent_preload = silent_preload  # If True, don't play sound or show animation
        
        # Calculate paddle dimensions directly from constants to avoid temporary paddle creation
        from config import PADDLE_LEN, PADDLE_MARGIN, BOTTOM_PADDLE_MARGIN
        self.pad_len = PADDLE_LEN
        self.thickness = PADDLE_THICK

        # Starting position just outside the screen depending on side
        if side == 'top':
            self.start_pos = pygame.Vector2(WIDTH // 2, -self.thickness - 20)
        elif side == 'bottom':
            self.start_pos = pygame.Vector2(WIDTH // 2, HEIGHT + self.thickness + 20)
        elif side == 'left':
            self.start_pos = pygame.Vector2(-self.thickness - 20, HEIGHT // 2)
        else:  # right
            self.start_pos = pygame.Vector2(WIDTH + self.thickness + 20, HEIGHT // 2)

        # Centre and final positions
        self.center_pos = pygame.Vector2(WIDTH // 2, HEIGHT // 2)
        # Calculate final position directly without temporary paddle
        if side in ('top', 'bottom'):
            if side == 'top':
                final_y = PADDLE_MARGIN + self.thickness // 2
            else:  # bottom
                final_y = HEIGHT - self.thickness - BOTTOM_PADDLE_MARGIN + self.thickness // 2
            self.final_pos = pygame.Vector2(WIDTH // 2, final_y)
        else:  # left or right
            final_x = PADDLE_MARGIN + self.thickness // 2 if side == 'left' else WIDTH - self.thickness - PADDLE_MARGIN + self.thickness // 2
            self.final_pos = pygame.Vector2(final_x, HEIGHT // 2)

        # Animation parameters
        self.phase = 'fly_in'  # fly_in -> spin -> fly_out
        self.timer = 0  # ms within current phase
        self.angle = 0.0
        
        # CRITICAL FIX: Initialize position immediately to prevent flickering
        self.pos = self.start_pos.copy()

        # Pre-render NEW PADDLE text
        self.text_surf = intro_font.render("NEW PADDLE!", True, (200, 30, 200))
        self.text_rect = self.text_surf.get_rect(center=(WIDTH // 2, HEIGHT // 3))

        # Cache paddle surface to avoid recreation every frame
        if self.side in ('top', 'bottom'):
            w, h = self.pad_len, self.thickness
        else:
            w, h = self.thickness, self.pad_len
        self._paddle_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        self._paddle_surf.fill((176, 96, 32))  # wooden colour

        # --- particle streak background ---
        # Remove streaks - using only purple swirling circle effect
        # one-off radial burst particles (purple swirling)
        self.burst = []   # list[Particle]
        self._burst_spawned = False  # flag to ensure single spawn per intro

        # ---------------------------------------------------------
        #  Play celebratory chime when the intro begins (unless silent preload)
        # ---------------------------------------------------------
        self._sound_played = False
        self._sounds = sounds
        self._load_sound_func = load_sound_func

        # If this is a silent preload, immediately complete the animation
        if silent_preload:
            self.phase = 'completed'
            self.timer = 0
            self.pos = self.final_pos.copy()
            self.angle = self._FINAL_ANGLE.get(self.side, 0)
    
    def _update_sound_volume(self):
        """Update paddle intro sound volume based on current settings."""
        try:
            if 'paddle_intro' in self._sounds:
                import sys
                if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'options_menu'):
                    options_menu = sys.modules['__main__'].options_menu
                    if hasattr(options_menu, 'settings'):
                        if options_menu.settings.get('sfx_muted', False):
                            self._sounds['paddle_intro'].set_volume(0)
                        else:
                            sfx_vol = options_menu.settings.get('sfx_volume', 0.75)
                            self._sounds['paddle_intro'].set_volume(sfx_vol)
        except Exception as e:
            print(f"[PaddleIntro] Failed to update sound volume: {e}")

    # durations (ms)
    FLY_TIME  = 1000   # was 700 – slower so players can track it
    SPIN_TIME = 1800   # duration of full spin phase
    EXIT_TIME = 900    # fly-out duration

    # total rotation (deg) before settling – 1.5 turns feels dynamic without over-spinning
    SPIN_DEG = 540

    # Helper – desired resting angle for each paddle side
    _FINAL_ANGLE = {
        'top':    0,
        'bottom': 0,
        'left':   0,   # vertical rectangle already drawn upright
        'right':  0,
    }

    # easing helpers
    @staticmethod
    def _ease_out_cubic(t):
        return 1 - (1 - t) ** 3

    @staticmethod
    def _ease_out_back(t, s=1.70158):
        t -= 1
        return 1 + (s + 1) * t ** 3 + s * t ** 2

    def update(self, dt_ms):
        # Silent preloads are already completed
        if self.silent_preload:
            return True  # immediately finished
            
        # EDGE CASE FIX: Ensure minimum delta time to prevent animation issues
        dt_ms = max(dt_ms, 1)  # Minimum 1ms to prevent division by zero or stalling
        
        self.timer += dt_ms

        # Play sound after 1 second delay
        if not self.silent_preload and not self._sound_played and self.timer >= 1000:
            try:
                if 'paddle_intro' not in self._sounds:
                    self._sounds['paddle_intro'] = self._load_sound_func('Sound Response - 8 Bit Jingles - Glide up Win')
                    # Volume will be set by options menu
                # Update volume before playing
                self._update_sound_volume()
                self._sounds['paddle_intro'].play()
            except Exception as _aud_err:
                print('[Audio] Paddle intro sound error:', _aud_err)
            self._sound_played = True

        if self.phase == 'fly_in':
            t = min(1.0, self.timer / max(1, self.FLY_TIME))  # Prevent division by zero
            self.pos = self.start_pos.lerp(self.center_pos, PaddleIntro._ease_out_cubic(t))
            if t >= 1.0:
                self.phase = 'spin'
                self.timer = 0
                # trigger radial burst once at the start of spin
                if not self._burst_spawned:
                    self._spawn_burst()
                    self._burst_spawned = True
        elif self.phase == 'spin':
            t = min(1.0, self.timer / max(1, self.SPIN_TIME))
            self.pos = self.center_pos
            # Smooth spin – accelerate then decelerate
            ease = PaddleIntro._ease_out_cubic(t)
            self.angle = PaddleIntro.SPIN_DEG * ease

            if t >= 1.0:
                # Snap exactly to the final orientation required in gameplay
                self.angle = PaddleIntro._FINAL_ANGLE.get(self.side, 0)
                self.phase = 'fly_out'
                self.timer = 0
        elif self.phase == 'fly_out':
            t = min(1.0, self.timer / max(1, self.EXIT_TIME))
            self.pos = self.center_pos.lerp(self.final_pos, PaddleIntro._ease_out_cubic(t))
            # Keep angle fixed at final orientation during fly-out
            self.angle = PaddleIntro._FINAL_ANGLE.get(self.side, 0)
            # Fade burst particles faster during exit for a clean finish
            for p in self.burst:
                p.fade = True
            # Only finish once particles have fully dissipated
            if t >= 1.0 and not self.burst:
                return True  # finished (animation + FX complete)

        # update radial burst particles (purple swirling)
        for p in self.burst[:]:
            p.update()
            # Add flutter effect as particles age
            if p.life < 30:  # Last half of life
                p.vel.x += random.uniform(-0.1, 0.1)
                p.vel.y += random.uniform(-0.1, 0.1)
                # Add slight gravity for flutter
                p.vel.y += 0.02
            if p.life <= 0:
                self.burst.remove(p)

        return False

    def _spawn_burst(self):
        """Create a multi-layered purple burst with streaks and super particles."""
        center = self.center_pos
        purple_shades = [
            (128, 0, 128), (148, 0, 211), (138, 43, 226), 
            (147, 112, 219), (186, 85, 211), (221, 160, 221)
        ]
        # --- Inner ring: dense, slow, small ---
        num_inner = 32
        for i in range(num_inner):
            angle = (2 * math.pi * i) / num_inner
            radius = random.uniform(18, 28)
            dir_vec = pygame.Vector2(math.cos(angle), math.sin(angle))
            pos = center + dir_vec * radius
            tangent_angle = angle + math.pi/2
            tangent_vel = pygame.Vector2(math.cos(tangent_angle), math.sin(tangent_angle)) * 1.2
            outward_vel = dir_vec * 0.5
            vel = tangent_vel + outward_vel
            color = random.choice(purple_shades)
            size = random.randint(2, 4)
            self.burst.append(Particle(pos.x, pos.y, vel, color, life=70, size=size, fade=True))
        # --- Middle ring: medium speed, medium size ---
        num_middle = 36
        for i in range(num_middle):
            angle = (2 * math.pi * i) / num_middle
            radius = random.uniform(30, 45)
            dir_vec = pygame.Vector2(math.cos(angle), math.sin(angle))
            pos = center + dir_vec * radius
            tangent_angle = angle + math.pi/2
            tangent_vel = pygame.Vector2(math.cos(tangent_angle), math.sin(tangent_angle)) * 2.2
            outward_vel = dir_vec * 1.2
            vel = tangent_vel + outward_vel
            color = random.choice(purple_shades)
            size = random.randint(3, 6)
            self.burst.append(Particle(pos.x, pos.y, vel, color, life=90, size=size, fade=True))
        # --- Outer ring: fast, large, streaky ---
        num_outer = 24
        for i in range(num_outer):
            angle = (2 * math.pi * i) / num_outer
            radius = random.uniform(40, 60)
            dir_vec = pygame.Vector2(math.cos(angle), math.sin(angle))
            pos = center + dir_vec * radius
            tangent_angle = angle + math.pi/2
            tangent_vel = pygame.Vector2(math.cos(tangent_angle), math.sin(tangent_angle)) * 3.5
            outward_vel = dir_vec * 3.5
            vel = tangent_vel + outward_vel
            color = random.choice(purple_shades)
            size = random.randint(5, 8)
            self.burst.append(Particle(pos.x, pos.y, vel, color, life=110, size=size, fade=True))
        # --- Super particles: extra large, fast, bright ---
        num_super = 6
        for i in range(num_super):
            angle = random.uniform(0, 2 * math.pi)
            dir_vec = pygame.Vector2(math.cos(angle), math.sin(angle))
            pos = center + dir_vec * random.uniform(10, 20)
            vel = dir_vec * random.uniform(7, 10)
            color = (255, 200, 255)  # bright magenta
            size = random.randint(10, 14)
            self.burst.append(Particle(pos.x, pos.y, vel, color, life=120, size=size, fade=True))

    def _get_instruction_text(self):
        # Returns the correct instruction string and key icons for this paddle
        if self.side == 'bottom':
            return "Use ← and → to move your paddle. Spacebar to 'bump'."
        elif self.side == 'top':
            return "Use A and D to move your paddle. Spacebar to 'bump'."
        elif self.side == 'left':
            return "Use W and S to move your paddle. Spacebar to 'bump'."
        else:  # right
            return "Use ↑ and ↓ to move your paddle. Spacebar to 'bump'."

    def _draw_speech_bubble(self, surf, text, pos, alpha=255):
        # Draws a pixel-art style speech bubble with the given text at pos (center bottom of bubble)
        # pos: (x, y) tuple for the tip of the bubble tail
        font = load_font('PressStart2P-Regular.ttf', 18)
        lines = text.split(". ")  # Split into lines for better fit
        rendered = [font.render(line, True, (0,0,0)) for line in lines]
        w = max(r.get_width() for r in rendered) + 24
        h = sum(r.get_height() for r in rendered) + 24
        bubble = pygame.Surface((w, h), pygame.SRCALPHA)
        # White fill, black border
        pygame.draw.rect(bubble, (255,255,255,int(alpha)), (0,0,w,h), border_radius=8)
        pygame.draw.rect(bubble, (0,0,0,int(alpha)), (0,0,w,h), 3, border_radius=8)
        # Draw text
        y = 12
        for r in rendered:
            r.set_alpha(alpha)
            bubble.blit(r, ((w - r.get_width())//2, y))
            y += r.get_height() + 2
        # Draw tail (triangle)
        tail = pygame.Surface((20, 16), pygame.SRCALPHA)
        pygame.draw.polygon(tail, (255,255,255,int(alpha)), [(10,0),(0,16),(20,16)])
        pygame.draw.polygon(tail, (0,0,0,int(alpha)), [(10,0),(0,16),(20,16)], 2)
        # Position bubble and tail
        bx, by = int(pos[0] - w//2), int(pos[1])
        surf.blit(bubble, (bx, by))
        surf.blit(tail, (pos[0]-10, by+h-2))

    def draw(self, surf):
        # Skip drawing for silent preloads
        if self.silent_preload:
            return
            
        # EDGE CASE FIX: Ensure position is valid before drawing
        if not hasattr(self, 'pos') or self.pos is None:
            return

        # Use cached paddle surface instead of creating new one every frame
        try:
            rot_surf = pygame.transform.rotate(self._paddle_surf, self.angle)
            rot_rect = rot_surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        except (ValueError, OverflowError):
            # Handle potential rotation errors on first frame
            rot_surf = self._paddle_surf
            rot_rect = rot_surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))

        # draw radial burst particles (purple swirling and fluttering)
        for p in self.burst:
            p.draw(surf)

        surf.blit(rot_surf, rot_rect)

        # Flash NEW PADDLE text during spin phase and fade out on exit
        if self.phase in ('spin', 'fly_out'):  # still show text during exit, but banner only in spin
            phase_t = (min(1.0, self.timer / max(1, self.SPIN_TIME)) if self.phase=='spin'
                        else min(1.0, self.timer / max(1, self.EXIT_TIME)))

            if self.phase == 'spin':
                # pulsing alpha
                alpha = int(200 + 55 * math.sin(self.timer / 100))
            else:  # fly_out – fade
                alpha = int(255 * (1 - phase_t))

            # --- sweeping white banner behind text (spin phase only) ---
            banner_height = self.text_rect.height + 14
            if self.phase == 'spin':
                # --- sweeping white banner behind text (spin phase only) ---
                if phase_t < 0.2:  # sweep in
                    sweep_t = phase_t / 0.2
                    banner_x = -WIDTH + sweep_t * WIDTH
                elif phase_t > 0.8:  # sweep out
                    sweep_t = (phase_t - 0.8) / 0.2
                    banner_x = sweep_t * WIDTH
                else:  # hold
                    banner_x = 0

                banner_rect = pygame.Rect(int(banner_x), self.text_rect.centery - banner_height//2, WIDTH, banner_height)
                banner_surf = pygame.Surface((banner_rect.width, banner_rect.height), pygame.SRCALPHA)
                # add subtle alpha for streaky look
                banner_surf.fill((255,255,255,230))
                surf.blit(banner_surf, banner_rect)

            # EDGE CASE FIX: Safer text surface handling
            try:
                txt = self.text_surf.copy().convert_alpha()
                txt.set_alpha(max(0, min(255, alpha)))  # Clamp alpha to valid range
                surf.blit(txt, self.text_rect)
            except (pygame.error, ValueError):
                # Fallback: draw text without alpha if copy fails
                surf.blit(self.text_surf, self.text_rect)

            # (Speech bubble removed – handled by PaddleTooltip in main loop)

        return

    def _draw_speech_bubble(self, surf, text, pos, alpha=255):
        # Draws a pixel-art style speech bubble with the given text at pos (center bottom of bubble)
        # pos: (x, y) tuple for the tip of the bubble tail
        font = load_font('PressStart2P-Regular.ttf', 18)
        lines = text.split(". ")  # Split into lines for better fit
        rendered = [font.render(line, True, (0,0,0)) for line in lines]
        w = max(r.get_width() for r in rendered) + 24
        h = sum(r.get_height() for r in rendered) + 24
        bubble = pygame.Surface((w, h), pygame.SRCALPHA)
        # White fill, black border
        pygame.draw.rect(bubble, (255,255,255,int(alpha)), (0,0,w,h), border_radius=8)
        pygame.draw.rect(bubble, (0,0,0,int(alpha)), (0,0,w,h), 3, border_radius=8)
        # Draw text
        y = 12
        for r in rendered:
            r.set_alpha(alpha)
            bubble.blit(r, ((w - r.get_width())//2, y))
            y += r.get_height() + 2
        # Draw tail (triangle)
        tail = pygame.Surface((20, 16), pygame.SRCALPHA)
        pygame.draw.polygon(tail, (255,255,255,int(alpha)), [(10,0),(0,16),(20,16)])
        pygame.draw.polygon(tail, (0,0,0,int(alpha)), [(10,0),(0,16),(20,16)], 2)
        # Position bubble and tail
        bx, by = int(pos[0] - w//2), int(pos[1])
        surf.blit(bubble, (bx, by))
        surf.blit(tail, (pos[0]-10, by+h-2))

    def draw(self, surf):
        # Skip drawing for silent preloads
        if self.silent_preload:
            return
            
        # EDGE CASE FIX: Ensure position is valid before drawing
        if not hasattr(self, 'pos') or self.pos is None:
            return

        # Use cached paddle surface instead of creating new one every frame
        try:
            rot_surf = pygame.transform.rotate(self._paddle_surf, self.angle)
            rot_rect = rot_surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        except (ValueError, OverflowError):
            # Handle potential rotation errors on first frame
            rot_surf = self._paddle_surf
            rot_rect = rot_surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))

        # draw radial burst particles (purple swirling and fluttering)
        for p in self.burst:
            p.draw(surf)

        surf.blit(rot_surf, rot_rect)

        # Flash NEW PADDLE text during spin phase and fade out on exit
        if self.phase in ('spin', 'fly_out'):  # still show text during exit, but banner only in spin
            phase_t = (min(1.0, self.timer / max(1, self.SPIN_TIME)) if self.phase=='spin'
                        else min(1.0, self.timer / max(1, self.EXIT_TIME)))

            if self.phase == 'spin':
                # pulsing alpha
                alpha = int(200 + 55 * math.sin(self.timer / 100))
            else:  # fly_out – fade
                alpha = int(255 * (1 - phase_t))

            # --- sweeping white banner behind text (spin phase only) ---
            banner_height = self.text_rect.height + 14
            if self.phase == 'spin':
                # --- sweeping white banner behind text (spin phase only) ---
                if phase_t < 0.2:  # sweep in
                    sweep_t = phase_t / 0.2
                    banner_x = -WIDTH + sweep_t * WIDTH
                elif phase_t > 0.8:  # sweep out
                    sweep_t = (phase_t - 0.8) / 0.2
                    banner_x = sweep_t * WIDTH
                else:  # hold
                    banner_x = 0

                banner_rect = pygame.Rect(int(banner_x), self.text_rect.centery - banner_height//2, WIDTH, banner_height)
                banner_surf = pygame.Surface((banner_rect.width, banner_rect.height), pygame.SRCALPHA)
                # add subtle alpha for streaky look
                banner_surf.fill((255,255,255,230))
                surf.blit(banner_surf, banner_rect)

            # EDGE CASE FIX: Safer text surface handling
            try:
                txt = self.text_surf.copy().convert_alpha()
                txt.set_alpha(max(0, min(255, alpha)))  # Clamp alpha to valid range
                surf.blit(txt, self.text_rect)
            except (pygame.error, ValueError):
                # Fallback: draw text without alpha if copy fails
                surf.blit(self.text_surf, self.text_rect)

            # (Speech bubble removed – handled by PaddleTooltip in main loop)

        return 