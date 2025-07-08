import pygame, random, math
from config import WIDTH, HEIGHT, PADDLE_THICK, PADDLE_MARGIN, WHITE, BLOCK_SIZE, SCALE, BLOCK_COLOR_L1
from utils import make_bricks
from crack_demo import create_crack_animator

class PlayerWall:
    """Bottom-edge wall that represents the player's health.

    The wall spans the full width of the screen and is *rows* blocks
    tall (default 2).  Each block can be destroyed by cannonballs.  When
    all blocks are gone the game is lost.  The wall persists across
    waves (it does **not** rebuild/reset).
    """
    POP_DURATION = 400  # ms - same as castle
    
    def __init__(self, rows: int = 2, block_size: int = BLOCK_SIZE):
        self.block_size = block_size
        self.rows = rows
        self.blocks = []  # list[pygame.Rect]
        self.block_health = {}  # key -> health (1-3)
        self.block_colors = {}  # key -> color_pair (for individual block colors)
        self._textures = {}  # cache colour -> surface
        self._color_pair = BLOCK_COLOR_L1
        self.block_cracks = {}  # key -> CrackAnimator
        self.pop_anims = []  # list of (rect, start_time) - for Stonemason's Kit and golem rebuilding only

        # Position wall so the bottom-most row sits right on the bottom
        # edge of the screen.  This may overlap the paddle slightly – that
        # is acceptable because paddle collision is processed first.
        start_y = HEIGHT - rows * block_size

        # Generate block rects so that the wall fully spans the screen width.
        # The final column may be narrower than *block_size* to exactly fit.
        full_cols = math.ceil(WIDTH / block_size)
        for row in range(rows):
            y = start_y + row * block_size
            for col in range(full_cols):
                x = col * block_size
                # Last column might exceed WIDTH – clamp its width to fit onscreen
                w = min(block_size, WIDTH - x)
                if w <= 0:
                    continue
                self.blocks.append(pygame.Rect(x, y, w, block_size))
                # Default health 1 (tier1). Will be upgraded by Fortified Walls.
                key = (x, y)
                self.block_health[key] = 1
                self.block_colors[key] = BLOCK_COLOR_L1

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _get_texture(self):
        # Cache texture by colour pair and block size for flexibility.
        key = (*self._color_pair, self.block_size)
        if key not in self._textures:
            self._textures[key] = make_bricks(self.block_size, *self._color_pair)
        return self._textures[key]

    def draw(self, surface):
        for b in self.blocks:
            key = (b.x, b.y)
            # Get the color for this specific block
            block_color = self.block_colors.get(key, self._color_pair)
            
            # Generate texture for this block's color
            tex_key = (*block_color, self.block_size)
            if tex_key not in self._textures:
                from utils import make_bricks
                self._textures[tex_key] = make_bricks(self.block_size, *block_color)
            tex = self._textures[tex_key]
            
            # If this is a narrow final column block, clip the texture
            if b.width != self.block_size:
                clipped_tex = tex.subsurface((0, 0, b.width, b.height))
                surface.blit(clipped_tex, b.topleft)
            else:
                surface.blit(tex, b.topleft)
            # outline
            pygame.draw.rect(surface, (0, 0, 0), b, 1)
            # Draw cracks if present
            if key in self.block_cracks:
                self.block_cracks[key].draw(surface, show_debug=False)

        # Draw tiered rebuilding progress
        if hasattr(self, 'rebuilding_blocks'):
            now = pygame.time.get_ticks()
            REBUILD_DELAY = 1000  # 1 second delay between tiers
            REBUILD_TIME = 3000   # 3 seconds for each tier rebuild
            
            for key, rebuild_info in self.rebuilding_blocks.items():
                elapsed = now - rebuild_info['time']
                if elapsed < REBUILD_DELAY:
                    continue  # Still in delay period
                
                progress = (elapsed - REBUILD_DELAY) / REBUILD_TIME
                if progress >= 1.0:
                    continue  # Will be handled in update soon
                
                block = rebuild_info['block']
                # Draw rebuilding progress (similar to castle rebuilding)
                # For now, just draw a simple progress indicator
                progress_width = int(block.width * progress)
                progress_rect = pygame.Rect(block.x, block.y, progress_width, block.height)
                pygame.draw.rect(surface, (100, 100, 100), progress_rect)
                pygame.draw.rect(surface, (0, 0, 0), progress_rect, 1)

        # Draw pop animations (for Stonemason's Kit and golem rebuilding)
        now = pygame.time.get_ticks()
        for p in self.pop_anims:
            age = now - p[1]  # p is (rect, start_time)
            t = age / self.POP_DURATION
            if t >= 1.0:
                continue  # Animation finished
                
            rect = p[0]
            scale = 1 + 0.3 * math.sin(math.pi * t)
            scaled_size = int(self.block_size * scale)
            
            # Get texture for this block
            key = (rect.x, rect.y)
            block_color = self.block_colors.get(key, self._color_pair)
            tex_key = (*block_color, self.block_size)
            if tex_key not in self._textures:
                from utils import make_bricks
                self._textures[tex_key] = make_bricks(self.block_size, *block_color)
            tex = self._textures[tex_key]
            
            # Scale the texture
            if rect.width != self.block_size:
                # Handle narrow final column blocks
                clipped_tex = tex.subsurface((0, 0, rect.width, rect.height))
                scaled_tex = pygame.transform.scale(clipped_tex, (int(rect.width * scale), int(rect.height * scale)))
            else:
                scaled_tex = pygame.transform.scale(tex, (scaled_size, scaled_size))
            
            draw_rect = scaled_tex.get_rect(center=rect.center)
            surface.blit(scaled_tex, draw_rect)

            # shockwave ring for pop animation
            shockwave_progress = t  # t goes from 0 to 1 over POP_DURATION
            max_radius = self.block_size * 2
            rad = int(max_radius * shockwave_progress)
            if 2 < rad < max_radius:
                pygame.draw.circle(surface, (255,255,255), rect.center, rad, 2)



    # ------------------------------------------------------------------
    # Damage handling
    # ------------------------------------------------------------------
    def shatter_block(self, block: pygame.Rect, incoming_dir: pygame.Vector2, debris_list: list):
        """Remove *block* and spawn simple debris into *debris_list*."""
        if block not in self.blocks:
            return

        key = (block.x, block.y)

        # Determine health remaining; default 1 if missing
        hp = self.block_health.get(key, 1)

        # Reduce health by 1 hit
        hp -= 1
        self.block_health[key] = hp
        
        # Update color based on remaining health
        if hp > 0:
            # Determine current tier based on block's original color
            current_tier = 1  # Default tier 1
            from config import BLOCK_COLOR_L1, BLOCK_COLOR_L2, BLOCK_COLOR_L3
            block_color = self.block_colors.get(key, BLOCK_COLOR_L1)
            if block_color == BLOCK_COLOR_L2:
                current_tier = 2
            elif block_color == BLOCK_COLOR_L3:
                current_tier = 3
            
            # Update color based on health and tier
            if current_tier == 3:  # Layer-3: 3→2→1→destroy
                if hp == 2:
                    self.block_colors[key] = BLOCK_COLOR_L3
                elif hp == 1:
                    self.block_colors[key] = BLOCK_COLOR_L2
            elif current_tier == 2:  # Layer-2: 2→1→destroy
                if hp == 1:
                    self.block_colors[key] = BLOCK_COLOR_L2
            
            # Clear texture cache so new color is generated
            if hasattr(self, '_textures'):
                self._textures = {}

        # --- Crack logic for multi-tier blocks ---
        if hp > 0:
            # Create or update crack animator
            if key not in self.block_cracks:
                self.block_cracks[key] = create_crack_animator(block)
            # Impact point: closest point on block to incoming direction (simulate as center for now)
            impact_x = max(block.left, min(block.centerx, block.right))
            impact_y = max(block.top, min(block.centery, block.bottom))
            impact_point = (int(impact_x), int(impact_y))
            impact_angle = math.atan2(incoming_dir.y, incoming_dir.x)
            self.block_cracks[key].add_crack(impact_point, impact_angle, debug=False)
            return  # Not destroyed yet

        # Fully destroyed – remove block and any remaining cracks
        self.blocks.remove(block)
        if key in self.block_health:
            del self.block_health[key]
        if key in self.block_cracks:
            del self.block_cracks[key]

        # Generate a few debris rectangles for visual feedback  
        # DEBRIS FIX: Try to detect if we're in a paddle intro by checking caller context
        should_create_debris = True
        try:
            import inspect
            frame = inspect.currentframe()
            if frame and frame.f_back and frame.f_back.f_locals:
                caller_locals = frame.f_back.f_locals
                should_create_debris = not caller_locals.get('intro_active', False)
        except:
            should_create_debris = True  # Default to creating debris if we can't determine
        
        if should_create_debris:
            for _ in range(10):
                ang = random.uniform(-40, 40)
                speed = random.uniform(1.5, 4.0) * SCALE
                vel = (-incoming_dir.normalize()).rotate(ang) * speed if incoming_dir.length_squared() else pygame.Vector2(0, -speed)
                size = int(random.randint(2, 4) * SCALE)
                color = random.choice(self._color_pair)
                deb = {'pos': pygame.Vector2(block.centerx, block.centery),
                       'vel': vel, 'color': color, 'size': size,
                       'friction': random.uniform(0.94, 0.985)}
                if random.random() < 0.3:
                    deb['dig_delay']  = random.randint(0, int(15 * SCALE))
                    deb['dig_frames'] = random.randint(int(15 * SCALE), int(90 * SCALE))
                debris_list.append(deb)

        # Do NOT add a pop animation here! (Fixes black square scaling bug)

    def update(self, dt_ms: int):
        """Update tiered rebuilding for player wall blocks."""
        if not hasattr(self, 'rebuilding_blocks'):
            return
        
        now = pygame.time.get_ticks()
        REBUILD_DELAY = 1000  # 1 second delay between tiers
        REBUILD_TIME = 3000   # 3 seconds for each tier rebuild
        
        for key, rebuild_info in list(self.rebuilding_blocks.items()):
            elapsed = now - rebuild_info['time']
            
            if elapsed < REBUILD_DELAY:
                continue  # Still in delay period
            
            progress = (elapsed - REBUILD_DELAY) / REBUILD_TIME
            if progress >= 1.0:
                # Current tier is complete, move to next tier
                current_tier = rebuild_info['current_tier']
                target_tier = rebuild_info['target_tier']
                
                if current_tier < target_tier:
                    # Upgrade to next tier
                    next_tier = current_tier + 1
                    self.block_health[key] = next_tier
                    
                    # Update color based on tier
                    from config import BLOCK_COLOR_L2, BLOCK_COLOR_L3
                    if next_tier == 2:
                        self._color_pair = BLOCK_COLOR_L2
                    elif next_tier == 3:
                        self._color_pair = BLOCK_COLOR_L3
                    
                    # Clear texture cache so new color is generated
                    if hasattr(self, '_textures'):
                        self._textures = {}
                    
                    # Update rebuild info for next tier
                    rebuild_info['current_tier'] = next_tier
                    rebuild_info['time'] = now
                    
                    # Player wall blocks don't use pop animations
                else:
                    # Reached target tier, remove from rebuilding queue
                    del self.rebuilding_blocks[key]
        
        # Clean up finished pop animations
        now = pygame.time.get_ticks()
        self.pop_anims = [p for p in self.pop_anims if now - p[1] < self.POP_DURATION] 