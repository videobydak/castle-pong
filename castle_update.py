import pygame, random, math
from config import *
from cannon import Cannon

# Constants moved from castle.py
REPAIR_DELAY = 3000   # wait before repair starts (ms)
REPAIR_TIME  = 15000  # duration of rebuild animation (ms)
MAX_DEBRIS_COUNT = 1000  # tuned to keep performance reasonable
CANNON_SLIDE_SPEED = 0.18  # px / ms – tuned for readable but still threatening movement
CANNON_EASE_DISTANCE = 4.0  # pixels – begin ease-in when within this many pixels of waypoint
_EASE_MIN = 0.25
# Dynamic wall shot probability - starts low (favoring paddles), increases per wave
def get_wall_shot_prob(wave_level):
    """
    Calculate wall shot probability based on wave level.
    Wave 1: 20% wall shots (80% paddle shots)
    Each wave: 10% relative reduction in paddle targeting
    So paddle shots: 80% -> 72% -> 64.8% -> 58.32% etc.
    Wall shots: 20% -> 28% -> 35.2% -> 41.68% etc.
    """
    base_paddle_prob = 0.8  # 80% paddle shots in wave 1
    reduction_factor = 0.9  # 10% relative reduction per wave
    current_paddle_prob = base_paddle_prob * (reduction_factor ** (wave_level - 1))
    # Cap paddle probability at minimum 10% so there's always some paddle targeting
    current_paddle_prob = max(0.1, current_paddle_prob)
    wall_shot_prob = 1.0 - current_paddle_prob
    return wall_shot_prob

def get_wall_targeting_area(wave_level):
    """
    Calculate the targeting area for player wall based on wave level.
    Wave 1: 40% of middle area
    Each wave: 10% relative increase in area
    So area: 40% -> 44% -> 48.4% -> 53.24% etc.
    By wave 10: should cover nearly 100% (actually ~95.5%)
    """
    base_area = 0.4  # 40% of wall width in wave 1
    growth_factor = 1.1  # 10% relative increase per wave
    current_area = base_area * (growth_factor ** (wave_level - 1))
    # Cap at 95% to ensure we don't exceed wall bounds
    return min(0.95, current_area)
_CANNON_MOVE_SHRINK_MS = 600  # shrink/spin-up phase duration (slowed)
_CANNON_MOVE_GROW_MS   = 600  # grow/spin-down phase duration (slowed)
_CANNON_MOVE_TRAVEL_MS = 900  # travel phase duration (new)

def update_castle(castle, dt_ms, player_score=0, paddles=None, player_wall=None, balls=None):
    # Normalise *paddles* input ---------------------------------------
    #  Accepts either a dict of Paddle objects (preferred) or legacy
    #  list/tuple of side strings for backward–compatibility.
    if isinstance(paddles, dict):
        paddle_sides = list(paddles.keys())
        paddle_objs  = paddles
    else:
        paddle_sides = paddles or []
        paddle_objs  = {}

    castle._new_balls.clear()
    # Difficulty factors --------------------------------------------------
    wave_factor  = 0.95 ** (max(1, castle.level) - 1)  # 5 % faster think/charge per wave
    think_factor = 1.0 - 0.5 * castle._scale('think', player_score)  # score-based (0→1)
    # ------------------------------------------------------------------
    #  Global ammo reservation flags (created lazily)
    # ------------------------------------------------------------------
    if not hasattr(castle, 'fireball_reserved'):
        castle.fireball_reserved = False
    if not hasattr(castle, 'potion_reserved'):
        castle.potion_reserved = False
    # Refresh reservation flags based on existing projectiles so state persists
    if balls is not None:
        # Active red fireballs
        castle.fireball_reserved = any(getattr(b, 'color', None) == RED for b in balls) if castle.level < 10 else False
        # Active potion (yellow power-ups)
        castle.potion_reserved = any(getattr(b, 'is_power', False) for b in balls)
    # --- smarter cannon behaviour with showmanship ---
    for c in castle.cannons:
        # --- Animate preview icon growth ---
        c.preview_scale = min(1.0, c.preview_scale + dt_ms / 300.0)

        # --------- Sprout growth control ---------
        if c.sprout_delay > 0:
            c.sprout_delay -= dt_ms
            if c.sprout_delay < 0:
                c.sprout_delay = 0
            growth = max(0, 300 - c.sprout_delay)
            c.sprout_scale = min(1.0, growth / 300.0)
            # Start pop animation when sprout begins
            if c.born < 0 and c.sprout_scale > 0.0:
                c.born = pygame.time.get_ticks() - int((1.0 - c.sprout_scale) * 400)
            c.can_shoot = False
        else:
            c.sprout_scale = 1.0
            if not c.can_shoot:
                # first time becoming active – small think delay
                c.idle_timer = int(random.randint(200, 500) * wave_factor * think_factor)
            c.can_shoot = True

        # Allow cannons to start thinking almost immediately after creation so
        # they are already active by the time they become visible. We only
        # skip completely invisible cannons (<0.05 scale).
        if c.sprout_scale < 0.05:
            continue

        # Skip cannons that are still in the pop-in animation phase
        if pygame.time.get_ticks() - c.born < castle.POP_DURATION:
            continue  # not active yet

        # --- Block charging and firing if shooting is disabled ---
        if not castle.shooting_enabled:
            # Cannons should still aim, move and charge while the tutorial
            # overlay is visible.  Actual projectile spawning is suppressed
            # inside _spawn_ball(), so we don't do any additional handling
            # here – simply allow the state machine to proceed.
            pass

        # Handle initial decision after spawn (random delay)
        if c.initial_decision_pending and c.idle_timer <= 0:
            # Force a decision: aim at a target or move
            paddle_sides = list(paddles.keys()) if isinstance(paddles, dict) else paddles or []
            made_decision = False
            if paddle_sides:
                # Prefer paddle targeting
                c.target_paddle = paddles[paddle_sides[0]] if isinstance(paddles, dict) else None
                if c.target_paddle:
                    pad = c.target_paddle
                    target_vec = pygame.Vector2(pad.rect.centerx, pad.rect.centery) - c.pos
                    desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                    c.pending_target_angle = desired
                    c.aim_transition = True
                    c.aim_at_wall = False
                    made_decision = True
            if not made_decision and player_wall and player_wall.blocks:
                block = min(player_wall.blocks, key=lambda b: (b.centerx-c.pos.x)**2 + (b.centery-c.pos.y)**2)
                c.target_block = block
                target_vec = pygame.Vector2(block.centerx, block.centery) - c.pos
                desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                c.pending_target_angle = desired
                c.aim_transition = True
                c.aim_at_wall = True
                made_decision = True
            if not made_decision:
                scan_range = 90
                base = random.uniform(-scan_range, scan_range)
                c.scan_target_angle = base
                c.pending_target_angle = base
                c.aim_transition = True
                c.aim_at_wall = False
            # Set initial angle and target_angle to match the first decision
            if c.angle is None:
                if c.pending_target_angle is not None:
                    c.angle = c.pending_target_angle
                    c.target_angle = c.pending_target_angle
                elif c.scan_target_angle is not None:
                    c.angle = c.scan_target_angle
                    c.target_angle = c.scan_target_angle
            # Do NOT snap c.angle to the target; let the smooth transition animate it
            c.initial_decision_pending = False
            # After this, idle_timer resumes normal behavior
            continue

        # -----------------------------------------------------------
        #  Handle animated teleport move ---------------------------
        # -----------------------------------------------------------
        if _update_move_anim(c, dt_ms):
            # If animation is active, skip further AI for this cannon this frame
            continue

        # If a new destination was scheduled *and* we are not yet animating,
        # initialise the animation now.
        if c.dest_pos and c.state != 'moving_anim':
            c.state = 'moving_anim'
            c.move_anim_phase = 0
            c.move_anim_timer = 0
            # Ensure animation durations are up-to-date in case they were tuned externally
            c.move_anim_total_shrink = _CANNON_MOVE_SHRINK_MS
            c.move_anim_total_grow   = _CANNON_MOVE_GROW_MS
            # Begin with full size
            c.sprout_scale = 1.0
            # Skip rest of logic this frame – animation update will run next pass
            continue

        # --- ACTION THROTTLING -----------------------------------------------
        # Limit major decisions to once every 250ms to prevent spazzy behavior
        now = pygame.time.get_ticks()
        last_action = c.last_action_time
        can_make_decision = (now - last_action >= 1200)  # 1200ms cooldown (more deliberate)
        # -----------------------------------------------------------------------
        
        # Get cannon side early to avoid UnboundLocalError
        side = c.side
        
        # --- ANTI-OSCILLATION DETECTION -------------------------------------
        # Track recent positions to detect left-right oscillation
        current_rail_idx = c.rail_idx
        position_history = c.position_history
        
        # Add current position with timestamp
        position_history.append((current_rail_idx, now))
        
        # Keep only last 10 seconds of history
        c.position_history = [(idx, time) for idx, time in position_history if now - time <= 10000]
        
        # Check for oscillation: if we've been bouncing between a handful of
        # rail indices but *not* just idling at a single index. Require that
        # we have at least 12 samples (≈ 3 s) and that the cannon visited at
        # least **two** distinct indices but no more than three.
        if len(position_history) >= 12:  # 12 samples over ~3 seconds
            recent_positions = [idx for idx, _ in position_history[-12:]]
            unique_positions = set(recent_positions)

            # True oscillation ⇔ 2–3 distinct indices visited repeatedly.
            if 2 <= len(unique_positions) <= 3:
                # FORCE a long-distance move to break oscillation
                track_len = len(castle.rail_info.rail_points[c.rail_id]) if castle.rail_info.rail_points else 4
                if track_len > 4:
                    # Jump to opposite side of perimeter
                    opposite_idx = (current_rail_idx + track_len // 2) % track_len
                    c.path_queue = []
                    for i in range(1, track_len // 2 + 1):
                        c.path_queue.append((current_rail_idx + i) % track_len)
                    c.last_action_time = now
                    position_history.clear()  # Reset history after forced move
                    
                    # Display visible error to user
                    print(f"[CANNON AI ERROR] Cannon oscillation detected! Forcing corner traversal from idx {current_rail_idx} to {opposite_idx}")
        # -------------------------------------------------------------------
            
        # --- STUCK DETECTION ------------------------------------------------
        # Disable stuck detection while a cannon is charging so that the
        # wind-up cannot be cancelled mid-way.  This prevents the freeze
        # / move bug where the charge ring almost completes then the
        # cannon decides to relocate instead of shoot.
        if c.state != 'charging' and can_make_decision:
            current_pos_key = (int(c.pos.x // 10), int(c.pos.y // 10))
            last_pos_key    = c.last_pos_key
            
            if current_pos_key == last_pos_key:
                c.stuck_timer += dt_ms
                if c.stuck_timer > 3000:  # 3 s in same 10-px cell
                    # Force aggressive movement to break free
                    c.stuck_timer = 0
                    c.path_queue  = []  # clear current path
                    castle._assign_new_target(c, paddle_sides, dest_idx=None, player_wall=player_wall)
                    c.last_action_time = now  # record action time
                    continue
            else:
                c.stuck_timer = 0
                c.last_pos_key = current_pos_key
        # -------------------------------------------------------------------

        # ----------------------------------------------------------------
        # Precise targeting – always pick a *real* objective instead of
        # guessing.  Preference order:
        #   1) Matching side paddle (very high priority)
        #   2) Reachable player wall block
        # Scanning sweep only happens if the above are not available.
        # ----------------------------------------------------------------

        # Only update target/aim when a new decision is made (idle_timer expired)
        if c.state != 'charging' and c.idle_timer <= 0 and can_make_decision:
            c.aim_transition = False
            c.pending_target_angle = None
            c.scan_target_angle = None
            c.target_paddle = None
            c.target_block = None
            # 1) Target local paddle if present
            if paddle_objs:
                shoot_wall = (
                    player_wall and player_wall.blocks and
                    random.random() < get_wall_shot_prob(castle.level)
                )
                if shoot_wall:
                    bottom_paddle = paddle_objs.get('bottom') if paddle_objs else None
                    unguarded_blocks = []
                    if bottom_paddle:
                        for b in player_wall.blocks:
                            if not bottom_paddle.rect.colliderect(b):
                                unguarded_blocks.append(b)
                    else:
                        unguarded_blocks = list(player_wall.blocks)
                    candidate_blocks = unguarded_blocks if unguarded_blocks else list(player_wall.blocks)
                    if candidate_blocks:
                        # Apply dynamic targeting area that grows with wave level
                        xs = [b.centerx for b in player_wall.blocks]
                        min_x, max_x = min(xs), max(xs)
                        wall_width = max_x - min_x
                        center_x = (min_x + max_x) / 2
                        
                        # Get targeting area percentage for current wave
                        targeting_area = get_wall_targeting_area(castle.level)
                        targeting_width = wall_width * targeting_area
                        targeting_min_x = center_x - targeting_width / 2
                        targeting_max_x = center_x + targeting_width / 2
                        
                        # Filter blocks within the targeting area
                        target_area_blocks = [b for b in candidate_blocks 
                                            if targeting_min_x <= b.centerx <= targeting_max_x]
                        
                        # If no blocks in target area, fallback to all candidate blocks
                        blocks_to_choose_from = target_area_blocks if target_area_blocks else candidate_blocks
                        chosen_block = random.choice(blocks_to_choose_from)
                    else:
                        chosen_block = min(
                            player_wall.blocks,
                            key=lambda b: (b.centerx - c.pos.x) ** 2 + (b.centery - c.pos.y) ** 2
                        )
                    c.target_block = chosen_block
                    c.aim_at_wall = True
                    # Set up smooth transition to new target
                    target_vec = pygame.Vector2(chosen_block.centerx, chosen_block.centery) - c.pos
                    desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                    c.pending_target_angle = desired
                    c.aim_transition = True
                else:
                    closest_paddle = None
                    closest_distance = float('inf')
                    for side, pad in paddle_objs.items():
                        paddle_pos = pygame.Vector2(pad.rect.centerx, pad.rect.centery)
                        distance = c.pos.distance_to(paddle_pos)
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_paddle = pad
                    if closest_paddle:
                        c.target_paddle = closest_paddle
                        c.aim_at_wall = False
                        # Set up smooth transition to new target
                        target_vec = pygame.Vector2(closest_paddle.rect.centerx, closest_paddle.rect.centery) - c.pos
                        desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                        c.pending_target_angle = desired
                        c.aim_transition = True
            else:
                if player_wall and player_wall.blocks:
                    if not c.target_block or c.target_block not in player_wall.blocks:
                        closest = min(player_wall.blocks,
                                        key=lambda b: (b.centerx-c.pos.x)**2 + (b.centery-c.pos.y)**2)
                        c.target_block = closest
                    c.aim_at_wall = True
                    # Set up smooth transition to new target
                    block = c.target_block
                    target_vec = pygame.Vector2(block.centerx, block.centery) - c.pos
                    desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                    c.pending_target_angle = desired
                    c.aim_transition = True
                # If no valid target, fallback to scan
                if not c.target_block and not c.target_paddle:
                    scan_range = 90
                    if c.scan_target_angle is None or abs(c.angle - c.scan_target_angle) < 2:
                        base = random.uniform(-scan_range, scan_range)
                        c.scan_target_angle = base
                    c.aim_transition = True
                    c.pending_target_angle = c.scan_target_angle
        # During idle, smoothly animate to pending target, then track
        if c.state != 'charging':
            # Smoothly animate to pending target if in transition
            if c.aim_transition and c.pending_target_angle is not None:
                if c.angle is None:
                    # Only snap if this is the very first frame
                    c.angle = c.pending_target_angle
                    c.target_angle = c.pending_target_angle
                    c.aim_transition = False
                    c.pending_target_angle = None
                else:
                    diff = c.pending_target_angle - c.angle
                    if diff > 180:
                        diff -= 360
                    elif diff < -180:
                        diff += 360
                    rate = c.aim_rate
                    step = diff * min(1.0, dt_ms * rate)
                    if abs(diff) < 1.0:
                        # Only finish the transition if it was already in progress
                        c.angle = c.pending_target_angle
                        c.aim_transition = False
                        c.pending_target_angle = None
                    else:
                        c.angle += step
                        if c.angle > 180:
                            c.angle -= 360
                        elif c.angle < -180:
                            c.angle += 360
            else:
                # If tracking a target, update target_angle to follow
                target_vec = None
                if c.aim_at_wall and c.target_block:
                    block = c.target_block
                    target_vec = pygame.Vector2(block.centerx, block.centery) - c.pos
                elif not c.aim_at_wall and c.target_paddle:
                    pad = c.target_paddle
                    target_vec = pygame.Vector2(pad.rect.centerx, pad.rect.centery) - c.pos
                # Ensure target_vec is always defined before use
            if 'target_vec' not in locals():
                target_vec = None
            if target_vec is not None and target_vec.length_squared():
                desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                # Smoothly animate toward the moving target (paddle or wall)
                if c.angle is None:
                    c.angle = desired
                    c.target_angle = desired
                else:
                    diff = desired - c.angle
                    if diff > 180:
                        diff -= 360
                    elif diff < -180:
                        diff += 360
                    rate = c.aim_rate
                    step = diff * min(1.0, dt_ms * rate)
                    # Always animate smoothly, never snap
                    c.angle += step
                    if c.angle > 180:
                        c.angle -= 360
                    elif c.angle < -180:
                        c.angle += 360
                c.target_angle = c.angle
            elif c.scan_target_angle is not None:
                diff = c.scan_target_angle - c.angle
                if diff > 180:
                    diff -= 360
                elif diff < -180:
                    diff += 360
                rate = c.aim_rate
                step = diff * min(1.0, dt_ms * rate)
                if abs(diff) < 1.0:
                    # Pick a new scan target
                    scan_range = 90
                    base = random.uniform(-scan_range, scan_range)
                    c.scan_target_angle = base
                else:
                    c.angle += step
                    if c.angle > 180:
                        c.angle -= 360
                    elif c.angle < -180:
                        c.angle += 360
                c.target_angle = c.angle

        # Smoothly rotate toward target only when charging; otherwise snap instantly
        if c.state == 'charging':
            if c.target_angle is not None and c.angle is not None:
                diff = c.target_angle - c.angle
                # Handle angle wrapping
                if diff > 180:
                    diff -= 360
                elif diff < -180:
                    diff += 360
                rate = c.aim_rate
                c.angle += diff * min(1.0, dt_ms * rate)
                # Keep angle in range
                if c.angle > 180:
                    c.angle -= 360
                elif c.angle < -180:
                    c.angle += 360
                # Always animate smoothly, never snap directly to target
            # If angle or target_angle is None, skip rotation this frame

        # --- Remove perimeter movement logic - cannons now teleport to new positions ---
        # No more sliding along rails - movement is instant when _assign_new_target is called

        state = c.state

        # -------- STATE MACHINE --------
        if state == 'idle':
            # handle preview cycling
            c.preview_timer -= dt_ms
            if c.preview_timer <= 0:
                # Much slower preview cycling in early game
                pscale = 1 - 0.8 * castle._scale('preview', player_score)  # more dramatic scaling
                pbase = int(random.randint(1500, 3000) * pscale)  # longer base time (1.5-3 seconds)
                c.preview_timer = pbase
                c.preview_idx = (c.preview_idx + 1) % len(castle._preview_types)
                # Reset preview animation scale
                c.preview_scale = 0.0
                # If next shot is a power-up, pre-select its potion type so preview matches
                if castle._preview_types[c.preview_idx] == 'power':
                    c.preview_power = get_random_potion_type()
                else:
                    c.preview_power = None

            # countdown idle
            c.idle_timer -= dt_ms
            if c.idle_timer <= 0 and can_make_decision:  # throttle decisions
                # Decide to shoot or move ---------------------------------
                prog = castle._shot_scale()  # 0..1 based on shots fired

                # --- Restrict movement for 1 or 2 cannons as per rules ---
                num_cannons = len(castle.cannons)
                num_balls = len(balls) if balls is not None else 0
                allow_move = True
                if num_cannons == 1:
                    allow_move = False
                elif num_cannons == 2 and num_balls == 0:
                    allow_move = False

                # --- Relocate? (5 % chance) ---
                if allow_move and random.random() < 0.05:
                    castle._assign_new_target(c, paddle_sides, dest_idx=None, player_wall=player_wall)
                    c.last_action_time = now
                    # brief pause before next decision once we arrive
                    base_idle = 1200 * (1 - 0.5*prog)
                    c.idle_timer = int(base_idle * wave_factor * think_factor)
                    c.state = 'idle'
                    continue

                # --- Otherwise: prepare to shoot ---
                # ------------------------------------------------------
                #  Choose ammo type with dynamic probabilities
                # ------------------------------------------------------
                score_ratio = min(max(player_score, 0), 1000) / 1000.0  # 0→1 up to 1000 pts
                fireball_prob = 0.05 + 0.35 * score_ratio  # 5 % → 40 %
                potion_prob   = POWERUP_CHANCE            # from config.py

                r = random.random()
                if r < fireball_prob and (not castle.fireball_reserved or castle.level >= 10):
                    chosen_type = 'red'
                    # Reserve fireball if waves < 10 to ensure only one in play
                    if castle.level < 10:
                        castle.fireball_reserved = True
                elif r < fireball_prob + potion_prob and not castle.potion_reserved:
                    chosen_type = 'power'
                    castle.potion_reserved = True
                else:
                    chosen_type = 'white'

                # Pick an index in the existing preview_type list that matches *chosen_type*
                indices = [i for i,t in enumerate(castle._preview_types) if t == chosen_type]
                if indices:
                    c.preview_idx = random.choice(indices)
                else:
                    # Fallback to first element if somehow missing
                    c.preview_idx = 0

                c.preview_scale = 0.0
                if chosen_type == 'power':
                    c.preview_power = get_random_potion_type()
                else:
                    c.preview_power = None

                # Charge duration shortens as more shots are fired
                base_charge = int(1800 * wave_factor)  # ms at start, scaled per wave
                charge_ms   = max(500, int(base_charge * (1 - 0.6*prog)))
                c.charge_timer = charge_ms
                c.ring_timer   = charge_ms
                c.ring_total   = charge_ms
                c.charge_safety = 0
                c.state = 'charging'
                c.last_action_time = now
        elif state == 'charging':
            c.charge_timer -= dt_ms
            c.ring_timer   = max(0, c.ring_timer - dt_ms)
            if c.charge_timer <= 0:
                # Fire!
                shot_type = castle._preview_types[c.preview_idx]
                ball = castle._spawn_ball(c, shot_type)
                if ball:
                    castle._new_balls.append(ball)
                    # muzzle smoke particles
                    for _ in range(25):
                        ang = random.uniform(0, 360)
                        spd = random.uniform(0.5, 2.0)
                        vel = pygame.Vector2(spd, 0).rotate(ang)
                        castle.smoke_particles.append({'pos': c.pos.copy(), 'vel': vel, 'life': 35})

                # After shooting, reset targeting preference and return to idle state
                c.aim_at_wall = None
                c.target_block = None
                c.state = 'idle'
                c.idle_timer = int(random.randint(1500, 3000) * wave_factor * think_factor)  # longer idle, scaled
                # --- Begin smooth transition to new target after shot ---
                c.aim_transition = False
                c.pending_target_angle = None
                c.scan_target_angle = None
                c.target_paddle = None
                c.target_block = None
                # 1) Target local paddle if present
                if paddle_objs:
                    shoot_wall = (
                        player_wall and player_wall.blocks and
                        random.random() < get_wall_shot_prob(castle.level)
                    )
                    if shoot_wall:
                        bottom_paddle = paddle_objs.get('bottom') if paddle_objs else None
                        unguarded_blocks = []
                        if bottom_paddle:
                            for b in player_wall.blocks:
                                if not bottom_paddle.rect.colliderect(b):
                                    unguarded_blocks.append(b)
                        else:
                            unguarded_blocks = list(player_wall.blocks)
                        candidate_blocks = unguarded_blocks if unguarded_blocks else list(player_wall.blocks)
                        if candidate_blocks:
                            # Apply dynamic targeting area that grows with wave level
                            xs = [b.centerx for b in player_wall.blocks]
                            min_x, max_x = min(xs), max(xs)
                            wall_width = max_x - min_x
                            center_x = (min_x + max_x) / 2
                            
                            # Get targeting area percentage for current wave
                            targeting_area = get_wall_targeting_area(castle.level)
                            targeting_width = wall_width * targeting_area
                            targeting_min_x = center_x - targeting_width / 2
                            targeting_max_x = center_x + targeting_width / 2
                            
                            # Filter blocks within the targeting area
                            target_area_blocks = [b for b in candidate_blocks 
                                                if targeting_min_x <= b.centerx <= targeting_max_x]
                            
                            # If no blocks in target area, fallback to all candidate blocks
                            blocks_to_choose_from = target_area_blocks if target_area_blocks else candidate_blocks
                            chosen_block = random.choice(blocks_to_choose_from)
                        else:
                            chosen_block = min(
                                player_wall.blocks,
                                key=lambda b: (b.centerx - c.pos.x) ** 2 + (b.centery - c.pos.y) ** 2
                            )
                        c.target_block = chosen_block
                        c.aim_at_wall = True
                        # Set up smooth transition to new target
                        target_vec = pygame.Vector2(chosen_block.centerx, chosen_block.centery) - c.pos
                        desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                        c.pending_target_angle = desired
                        c.aim_transition = True
                    else:
                        closest_paddle = None
                        closest_distance = float('inf')
                        for side, pad in paddle_objs.items():
                            paddle_pos = pygame.Vector2(pad.rect.centerx, pad.rect.centery)
                            distance = c.pos.distance_to(paddle_pos)
                            if distance < closest_distance:
                                closest_distance = distance
                                closest_paddle = pad
                        if closest_paddle:
                            c.target_paddle = closest_paddle
                            c.aim_at_wall = False
                            # Set up smooth transition to new target
                            target_vec = pygame.Vector2(closest_paddle.rect.centerx, closest_paddle.rect.centery) - c.pos
                            desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                            c.pending_target_angle = desired
                            c.aim_transition = True
                else:
                    if player_wall and player_wall.blocks:
                        if not c.target_block or c.target_block not in player_wall.blocks:
                            closest = min(player_wall.blocks,
                                            key=lambda b: (b.centerx-c.pos.x)**2 + (b.centery-c.pos.y)**2)
                            c.target_block = closest
                        c.aim_at_wall = True
                        # Set up smooth transition to new target
                        block = c.target_block
                        target_vec = pygame.Vector2(block.centerx, block.centery) - c.pos
                        desired = math.degrees(math.atan2(target_vec.y, target_vec.x))
                        c.pending_target_angle = desired
                        c.aim_transition = True
                    # If no valid target, fallback to scan
                    if not c.target_block and not c.target_paddle:
                        scan_range = 90
                        if c.scan_target_angle is None or abs(c.angle - c.scan_target_angle) < 2:
                            base = random.uniform(-scan_range, scan_range)
                            c.scan_target_angle = base
                        c.aim_transition = True
                        c.pending_target_angle = c.scan_target_angle
            # Safeguard: if charging takes too long, force exit
            c.charge_safety += dt_ms
            if c.charge_safety > 5000:  # 5 seconds max charge time (longer)
                c.charge_safety = 0
                c.state = 'idle'
                c.idle_timer = int(random.randint(1500, 3000) * wave_factor * think_factor)

        # Debug: Log when cannons change direction or get stuck
        if hasattr(c, '_debug_last_pos'):
            if c.pos.distance_to(c._debug_last_pos) < 0.1:
                c._debug_stuck_frames = getattr(c, '_debug_stuck_frames', 0) + 1
                if c._debug_stuck_frames > 60:  # 1 second at 60fps
                    pass  # Debug log disabled
            else:
                c._debug_stuck_frames = 0
        c._debug_last_pos = c.pos.copy()

    # --- update smoke particles ---
    for s in castle.smoke_particles[:]:
        s['pos'] += s['vel']
        s['life'] -= 1
        if s['life'] <= 0:
            castle.smoke_particles.remove(s)

    # --- update debris ---
    # Pause debris movement while paddle intro animations are active (castle._pause_rebuild flag)
    if not getattr(castle, '_pause_rebuild', False):
        for d in castle.debris:
            d['pos'] += d['vel']
            # simple friction to slow down
            d['vel'] *= d.get('friction', 0.985)

            # Handle optional shrinking for old pieces that are being phased out
            if d.get('_shrinking'):
                # Smoothly reduce the size until it disappears
                d['size'] -= d.get('_shrink_speed', 0.1)
                if d['size'] <= 0.2:
                    d['size'] = 0

    # decay shake counter for rebuilding blocks
    for rec in castle.destroyed_blocks.values():
        if rec.get('shake',0) > 0:
            rec['shake'] -= 1

    # Enforce debris limit: if we exceed the cap, start shrinking the oldest pieces
    if len(castle.debris) > MAX_DEBRIS_COUNT:
        # Number of pieces that need to be phased out
        excess = len(castle.debris) - MAX_DEBRIS_COUNT
        # Oldest pieces are at the front of the list (they were appended first)
        for d in castle.debris[:excess]:
            if not d.get('_shrinking'):
                d['_shrinking'] = True
                # Shrink over roughly one second worth of frames (@60fps)
                d['_shrink_speed'] = max(0.05, d['size'] / 60)

    # Finally, purge any debris whose size has reached zero
    castle.debris = [d for d in castle.debris if d.get('size', 1) > 0]

    # --- Repair speed multiplier for rebuild animation ---
    # If no balls, ramp up speed; if balls, ramp down to normal
    if not hasattr(castle, '_repair_speed_mult'):
        castle._repair_speed_mult = 1.0
    REPAIR_SPEED_MAX = 5.0
    REPAIR_SPEED_MIN = 1.0
    REPAIR_SPEED_SMOOTH_TC = 0.25  # seconds
    has_balls = balls is not None and len(balls) > 0
    has_cannons = hasattr(castle, 'cannons') and len(castle.cannons) > 0
    # Only ramp up if there are NO balls AND NO cannons
    target_repair_mult = REPAIR_SPEED_MIN if (has_balls or has_cannons) else REPAIR_SPEED_MAX
    alpha_repair = 1 - math.exp(-dt_ms/1000 / REPAIR_SPEED_SMOOTH_TC)
    castle._repair_speed_mult += (target_repair_mult - castle._repair_speed_mult) * alpha_repair

    # Repair blocks – allow pausing during paddle intro animations
    if getattr(castle, '_pause_rebuild', False):
        # Offset destroyed block timestamps so their progress does not advance
        for rec in castle.destroyed_blocks.values():
            rec['time'] += dt_ms  # push start time forward by the paused duration
    else:
        now = pygame.time.get_ticks()
        for pos, destroyed_at in list(castle.destroyed_blocks.items()):
            elapsed = now - destroyed_at['time']
            if elapsed < REPAIR_DELAY:
                continue  # delay period – nothing drawn yet
            # --- Apply repair speed multiplier ---
            repair_time = REPAIR_TIME / castle._repair_speed_mult
            progress = (elapsed - REPAIR_DELAY) / repair_time
            if progress >= 1.0:
                new_block = pygame.Rect(pos[0], pos[1], castle.block_size, castle.block_size)
                key = (new_block.x, new_block.y)
                # Always set block_tiers for every rebuilt block
                tier = getattr(castle, 'block_tiers', {}).get(key, 2)
                castle.block_tiers[key] = tier
                # Set health based on tier
                extra = 0 if tier == 2 else (1 if tier == 3 else 2)
                castle.block_health[key] = 1 + extra
                castle.set_block_color_by_strength(key, tier)
                castle.block_shapes[key] = 'wall'
                castle.blocks.append(new_block)
                del castle.destroyed_blocks[pos]
                # start pop animation
                castle.pop_anims.append({'rect': new_block, 'start': now})

                # Layout changed – rebuild perimeter tracks
                castle._build_perimeter_track()

                # Rebuild all cannons that were attached to this block
                for cinfo in destroyed_at.get('had_cannons', []):
                    side = cinfo['side']

                    # determine cannon position and direction based on side
                    if side == 'top':
                        cpos = pygame.Vector2(new_block.centerx, new_block.top - CANNON_GAP)
                        bdir = pygame.Vector2(0,-1)
                    elif side == 'bottom':
                        cpos = pygame.Vector2(new_block.centerx, new_block.bottom + CANNON_GAP)
                        bdir = pygame.Vector2(0,1)
                    elif side == 'left':
                        cpos = pygame.Vector2(new_block.left - CANNON_GAP, new_block.centery)
                        bdir = pygame.Vector2(-1,0)
                    else:  # right
                        cpos = pygame.Vector2(new_block.right + CANNON_GAP, new_block.centery)
                        bdir = pygame.Vector2(1,0)

                    new_cannon = Cannon(
                        block=new_block,
                        side=side,
                        pos=cpos,
                        rail_info=castle.rail_info,
                        total_shots_ref=lambda: castle.total_shots,
                        shooting_enabled_ref=lambda: castle.shooting_enabled,
                        smoke_particles_ref=castle.smoke_particles,
                        level=castle.level
                    )
                    new_cannon.base_dir = bdir
                    new_cannon.preview_idx = cinfo.get('preview_idx', random.randint(0,2))
                    new_cannon.born = now
                    new_cannon.initial_decision_pending = True
                    
                    castle.cannons.append(new_cannon)
                    new_cannon.rail_id, new_cannon.rail_idx = castle.rail_info.nearest_node((new_block.x, new_block.y))

    # Remove finished pop animations
    castle.pop_anims = [p for p in castle.pop_anims if now - p['start'] < castle.POP_DURATION]

    # Handle deferred shooting enable after castle build animation
    if not castle.shooting_enabled and hasattr(castle, '_shoot_enable_at'):
        if pygame.time.get_ticks() >= castle._shoot_enable_at:
            castle.shooting_enabled = True
            delattr(castle, '_shoot_enable_at')

    # return list of balls created this frame so the main loop can own them
    return castle._new_balls 

def _update_move_anim(c, dt_ms):
    """Animate the three-phase move (shrink+spin, travel, grow+spin-down) for *c* and return True while active."""
    if c.state != 'moving_anim':
        return False  # not in animation state

    c.move_anim_timer += dt_ms

    if c.move_anim_phase == 0:
        # SHRINK + SPIN-UP
        t = min(1.0, c.move_anim_timer / c.move_anim_total_shrink)
        ease = 1 - (1 - t) ** 3
        c.sprout_scale = max(0.05, 1.0 - ease)
        spin_rate = c.move_spin_speed_base * ease
        c.angle += spin_rate * dt_ms / 1000.0
        if c.move_anim_timer >= c.move_anim_total_shrink:
            # Start travel phase
            c.move_anim_phase = 1
            c.move_anim_timer = 0
            # Store travel start/end for interpolation
            c._move_travel_start = c.pos.copy()
            c._move_travel_end = c.dest_pos.copy() if c.dest_pos is not None else c.pos.copy()
            c._move_travel_block = c.dest_block
            c._move_travel_side = c.dest_side
    elif c.move_anim_phase == 1:
        # TRAVEL (ease in/out)
        t = min(1.0, c.move_anim_timer / _CANNON_MOVE_TRAVEL_MS)
        # Ease in/out (smoothstep)
        ease = t * t * (3 - 2 * t)
        if hasattr(c, '_move_travel_start') and hasattr(c, '_move_travel_end'):
            c.pos = c._move_travel_start.lerp(c._move_travel_end, ease)
        # Keep barrel shrunk during travel
        c.sprout_scale = 0.05
        # Spin at peak rate
        c.angle += c.move_spin_speed_base * dt_ms / 1000.0
        if c.move_anim_timer >= _CANNON_MOVE_TRAVEL_MS:
            # Snap to end, update block/side
            c.pos = c._move_travel_end
            c.block = c._move_travel_block
            c.side = c._move_travel_side
            # Re-compute outward base_dir
            centre = pygame.Vector2(WIDTH // 2, HEIGHT // 2)
            to_centre = centre - c.pos
            if to_centre.length_squared():
                c.base_dir = (-to_centre).normalize()
            # Clear destination
            c.dest_pos = None
            c.dest_block = None
            c.dest_side = None
            # Start grow phase
            c.move_anim_phase = 2
            c.move_anim_timer = 0
    else:
        # GROW + SPIN-DOWN
        t = min(1.0, c.move_anim_timer / c.move_anim_total_grow)
        ease = t ** 3 if t < 1.0 else 1.0
        c.sprout_scale = ease
        spin_rate = c.move_spin_speed_base * (1.0 - ease)
        c.angle += spin_rate * dt_ms / 1000.0
        if c.move_anim_timer >= c.move_anim_total_grow:
            c.sprout_scale = 1.0
            c.state = 'idle'
            c.move_anim_phase = None
            c.move_anim_timer = 0
            # Short idle
            c.idle_timer = random.randint(1000, 2000)
            # Clean up travel temp vars
            if hasattr(c, '_move_travel_start'):
                del c._move_travel_start
            if hasattr(c, '_move_travel_end'):
                del c._move_travel_end
            if hasattr(c, '_move_travel_block'):
                del c._move_travel_block
            if hasattr(c, '_move_travel_side'):
                del c._move_travel_side
    # Keep angle wrapped
    if c.angle > 180:
        c.angle -= 360
    elif c.angle < -180:
        c.angle += 360
    return True 