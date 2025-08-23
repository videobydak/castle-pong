import pygame, random, math
import config
from ball import Ball
from config import CANNON_ARC, CANNON_LEN, get_random_potion_type

class Cannon:
    def __init__(self, block, side, pos, rail_info, total_shots_ref, shooting_enabled_ref, smoke_particles_ref, level: int = 1):
        self.block = block
        self.side = side
        self.pos = pygame.Vector2(pos)
        self.rail_info = rail_info
        
        self.total_shots_ref = total_shots_ref # a function to get/increment total_shots
        self.shooting_enabled = shooting_enabled_ref # a function to check if shooting is enabled
        self.smoke_particles = smoke_particles_ref # ref to castle's smoke particle list
        
        # New independent random state
        self._rng = random.Random()
        # Store current wave/level so timers can scale with difficulty
        self.level = max(1, level)

        # Get initial rail position
        if self.rail_info is not None:
            self.rail_id, self.rail_idx = self.rail_info.nearest_node((self.block.x, self.block.y))
        else:
            self.rail_id, self.rail_idx = None, None
        
        # Set a sensible default orientation so the cannon is visible even
        # before its AI picks an explicit target.  We point the barrel
        # "downwards" – i.e., toward the player wall, somewhere in the middle 70% of the screen.
        screen_width = config.WIDTH
        min_x = screen_width * 0.15
        max_x = screen_width * 0.85
        target_x = self._rng.uniform(min_x, max_x)
        target_y = config.HEIGHT  # bottom of the screen
        target_vec = pygame.Vector2(target_x, target_y) - self.pos
        if target_vec.length_squared():
            self.base_dir = target_vec.normalize()
        else:
            self.base_dir = pygame.Vector2(0, 1)

        self.angle = math.degrees(math.atan2(self.base_dir.y, self.base_dir.x))
        self.target_angle = self.angle
        self.aim_rate = self._rng.uniform(0.0025, 0.006)
        
        # State machine: idle, charging, moving
        self.state = self._rng.choice(['idle', 'charging'])
        self.idle_timer = 0
        self.charge_timer = 0
        self.charge_total = 0 # store the total charge time for animation
        self.charge_safety = 0 # prevent shooting immediately after charge start
        
        # Movement
        self.dest_block = None
        self.dest_pos = None
        self.dest_side = None
        self.move_dir = 0
        self.path_queue = []

        # Sprout/appearance animation
        self.sprout_delay = self._rng.randint(200, 800)
        self.sprout_scale = 0.0
        self.born = -9999  # Will be set when sprout animation starts

        # Projectile preview
        self.preview_idx = self._rng.randint(0, 2)
        self.preview_scale = 1.0
        self.preview_timer = 0
        self.preview_power = None
        self.ring_timer = 0
        self.ring_total = 0

        self.can_shoot = False
        self.initial_decision_pending = True
        
        # -----------------------------------------------------------
        #  Difficulty-scaled think/charge timers
        # -----------------------------------------------------------
        wave_factor = 0.95 ** (self.level - 1)  # 5 % shorter each wave

        if self.state == 'idle':
            base_idle = self._rng.randint(0, 3000)
            self.idle_timer = int(base_idle * wave_factor)
        else:  # charging
            base_charge = int(1800 * wave_factor)
            prog = self._shot_scale()
            charge_ms = max(500, int(base_charge * (1 - 0.6 * prog)))
            self.charge_timer = self._rng.randint(0, charge_ms)
            self.charge_total = charge_ms
            self.ring_timer = self.charge_timer
            self.ring_total = charge_ms

        self.aim_transition = False
        self.pending_target_angle = None
        self.scan_target_angle = None
        
        # Attributes that are dynamically set in the update loop
        self.last_action_time = 0
        self.position_history = []
        self.stuck_timer = 0
        self.last_pos_key = None
        self.target_paddle = None
        self.target_block = None
        self.aim_at_wall = None

        # --- Animated movement (teleport jump) -------------------
        #  When the AI chooses to relocate, the cannon performs a two-phase
        #  animation: (1) spin-up while shrinking, then (2) spin-down while
        #  growing back after instantly "jumping" to the new spot.
        self.move_anim_phase     = None  # 0 = shrink+spin, 1 = grow+settle
        self.move_anim_timer     = 0     # ms elapsed in current phase
        self.move_anim_total_shrink = 300  # ms – tweak to taste
        self.move_anim_total_grow   = 300  # ms – tweak to taste
        self.move_spin_speed_base   = 720  # deg/s peak spin rate

    def _shot_scale(self):
        """Aggression helper – returns 0..1 based on total shots (cap at 30 shots)."""
        return min(1.0, self.total_shots_ref() * (1/30))

    def draw(self, screen, now, preview_types, _preview_col_map):
        if self.sprout_scale <= 0.01 and self.state != 'moving_anim':
            return

        if self.angle is None:
            return  # Do not draw if angle is not yet set

        draw_origin = self.pos

        # Ensure cannons remain visible during movement by using a minimum scale
        min_visible_scale = 0.3
        if self.state == 'moving_anim':
            scale = max(self.sprout_scale, min_visible_scale)
        else:
            scale = self.sprout_scale

        # scale based on pop animation age
        age = now - self.born
        scale_c = min(1.0, max(0.0, age / 400)) # 400 is Castle.POP_DURATION

        # --- Barrel scaling logic ---
        barrel_scale = 1.0
        if self.state == 'moving_anim' and self.move_anim_phase is not None:
            if self.move_anim_phase == 0:
                # SHRINK + SPIN-UP: barrel shrinks from 1 to 0
                t = min(1.0, self.move_anim_timer / self.move_anim_total_shrink)
                ease = 1 - (1 - t) ** 3
                barrel_scale = max(0.0, 1.0 - ease)
            elif self.move_anim_phase == 1:
                # TRAVEL: barrel is hidden
                barrel_scale = 0.0
            elif self.move_anim_phase == 2:
                # GROW + SPIN-DOWN: barrel grows from 0 to 1
                t = min(1.0, self.move_anim_timer / self.move_anim_total_grow)
                ease = t ** 3 if t < 1.0 else 1.0
                barrel_scale = ease

        # Use direct angle calculation for 360-degree rotation
        angle_rad = math.radians(self.angle)
        direction = pygame.Vector2(math.cos(angle_rad), math.sin(angle_rad))
        barrel_end = draw_origin + direction * (config.CANNON_LEN * scale_c * barrel_scale)

        # barrel and base (scaled)
        base_col = (140, 140, 140)
        highlight = (220, 220, 220)
        shadow = (60, 60, 60)

        width_px = int(6 * scale_c * scale * config.SCALE)
        radius = int(6 * scale_c * scale * config.SCALE)
        radius = max(radius, 3)
        width_px = max(width_px, 3)
        if radius <= 1:
            return

        # --- Barrel ---
        if barrel_scale > 0.01:
            perp = direction.rotate(90)
            if perp.length_squared() != 0:
                perp = perp.normalize()
            half = perp * (width_px / 2)
            p1 = draw_origin + half
            p2 = draw_origin - half
            p3 = barrel_end - half
            p4 = barrel_end + half
            pygame.draw.polygon(screen, base_col, [p1, p2, p3, p4])
            pygame.draw.line(screen, highlight, p1, p4, 1)
            pygame.draw.line(screen, shadow,   p2, p3, 1)

        # --- Base ---
        pygame.draw.circle(screen, shadow, draw_origin, radius)
        pygame.draw.circle(screen, base_col, draw_origin, max(1, radius - 1))
        if radius > 2:
            pygame.draw.circle(screen, highlight, draw_origin, max(1, radius - 2), 1)

        # --- Shrinking ring during charging ---
        if self.ring_timer > 0 and self.can_shoot:
            t = self.ring_timer / self.ring_total
            rad = int(20 * t * config.SCALE) + 2
            if rad > 2:
                pygame.draw.circle(screen, (200,200,200), draw_origin, rad, 2)

        # --- Preview projectile ---
        preview_type = preview_types[self.preview_idx]
        preview_scale = self.preview_scale * scale
        if preview_type == 'white':
            preview_ball = Ball(draw_origin.x, draw_origin.y, 0, 0, config.WHITE, spin=0, force_no_spin=True)
        elif preview_type == 'red':
            preview_ball = Ball(draw_origin.x, draw_origin.y, 0, 0, config.RED, spin=0, force_no_spin=True)
        else:
            ptype = self.preview_power or get_random_potion_type(self._rng)
            if ptype is None:
                # No potions unlocked, fall back to white cannonball
                preview_ball = Ball(draw_origin.x, draw_origin.y, 0, 0, config.WHITE, spin=0, force_no_spin=True)
            else:
                preview_ball = Ball(draw_origin.x, draw_origin.y, 0, 0, config.YELLOW, True, ptype, spin=0, force_no_spin=True)
        orig_radius = config.BALL_RADIUS
        config.BALL_RADIUS = max(2, int(orig_radius * preview_scale))
        preview_ball.draw(screen, None)
        config.BALL_RADIUS = orig_radius
    
    def spawn_ball(self, shot_type, _prepare_shot_sounds, _SHOT_SOUNDS):
        """Create and return a Ball fired from the cannon."""
        if not self.shooting_enabled():
            return None

        if self.angle is None:
            return None  # Cannot spawn a ball if angle is not set

        # Play appropriate shot SFX
        _prepare_shot_sounds()
        if _SHOT_SOUNDS:
            import random
            # Update volumes before playing
            import castle as castle_module
            castle_module._update_cannon_sound_volumes()
            # Ensure all required pitches exist in _SHOT_SOUNDS
            # (This is safe to call repeatedly; _prepare_shot_sounds will only build once)
            if shot_type == 'red':
                # Play normal sound first for fireballs
                _sfx_normal = _SHOT_SOUNDS.get('normal')
                if _sfx_normal:
                    _sfx_normal.play()
                
                # Schedule low pitch sound to play after a short delay
                _sfx_low = _SHOT_SOUNDS.get('0.1') or _SHOT_SOUNDS.get('normal')
                if _sfx_low:
                    # Add delayed sound to global list for processing
                    if not hasattr(pygame.time, '_delayed_sounds'):
                        pygame.time._delayed_sounds = []
                    delay_time = pygame.time.get_ticks() + 50  # 50ms delay
                    pygame.time._delayed_sounds.append((delay_time, _sfx_low))
            elif shot_type == 'power':
                _sfx = _SHOT_SOUNDS.get('1.9') or _SHOT_SOUNDS.get('normal')
                if _sfx:
                    _sfx.play()
            else:
                _sfx = _SHOT_SOUNDS.get('normal')
                if _sfx:
                    _sfx.play()

        angle_rad = math.radians(self.angle)
        direction = pygame.Vector2(math.cos(angle_rad), math.sin(angle_rad))
        start_pos = self.pos + direction * (config.CANNON_LEN + 8)

        vx, vy = direction.x * config.BALL_SPEED, direction.y * config.BALL_SPEED

        # Apply slight randomisation to speed for regular (white) and red cannonballs
        if shot_type in ('white', 'red'):
            speed_mult = random.uniform(0.85, 1.25)
            vx, vy = direction.x * config.BALL_SPEED * speed_mult, direction.y * config.BALL_SPEED * speed_mult

        # Give the projectile some initial spin, but clamp to a small value
        max_spin = 0.5  # radians per frame (tune as needed)
        spin = random.uniform(-max_spin, max_spin)

        if shot_type == 'white':
            b = Ball(start_pos.x, start_pos.y, vx, vy, config.WHITE, spin=spin)
        elif shot_type == 'red':
            b = Ball(start_pos.x, start_pos.y, vx, vy, config.RED, spin=spin)
        else:  # power-up
            ptype = self.preview_power or get_random_potion_type(self._rng)
            if ptype is None:
                # No potions unlocked, fall back to white cannonball
                b = Ball(start_pos.x, start_pos.y, vx, vy, config.WHITE, spin=spin)
            else:
                b = Ball(start_pos.x, start_pos.y, vx, vy, config.YELLOW, True, ptype, spin=spin)
        
        b.friendly = True # Should this be False if it's an enemy cannon? Assuming they are player-allied for now.
        
        # Add muzzle smoke
        for _ in range(self._rng.randint(6, 12)):
            vel = direction.rotate(self._rng.uniform(-45, 45)) * self._rng.uniform(0.5, 2.5)
            vel -= (direction * 1.5)
            p = {
                'pos': start_pos + direction * self._rng.uniform(2, 8),
                'vel': vel,
                'life': self._rng.randint(200, 400)
            }
            self.smoke_particles.append(p)
            
        return b 