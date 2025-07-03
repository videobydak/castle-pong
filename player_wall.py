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
    def __init__(self, rows: int = 2, block_size: int = BLOCK_SIZE):
        self.block_size = block_size
        self.rows = rows
        self.blocks = []  # list[pygame.Rect]
        self._textures = {}  # cache colour -> surface
        self._color_pair = BLOCK_COLOR_L1
        self.block_cracks = {}  # key -> CrackAnimator

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
        tex = self._get_texture()
        for b in self.blocks:
            # If this is a narrow final column block, clip the texture
            if b.width != self.block_size:
                clipped_tex = tex.subsurface((0, 0, b.width, b.height))
                surface.blit(clipped_tex, b.topleft)
            else:
                surface.blit(tex, b.topleft)
            # outline
            pygame.draw.rect(surface, (0, 0, 0), b, 1)
            # Draw cracks if present
            key = (b.x, b.y)
            if key in self.block_cracks:
                self.block_cracks[key].draw(surface, show_debug=False)

    # ------------------------------------------------------------------
    # Damage handling
    # ------------------------------------------------------------------
    def shatter_block(self, block: pygame.Rect, incoming_dir: pygame.Vector2, debris_list: list):
        """Remove *block* and spawn simple debris into *debris_list*."""
        if block not in self.blocks:
            return
        # --- Crack logic ---
        key = (block.x, block.y)
        # Only animate a crack if the block is not destroyed in one hit (i.e., if it has more than one hit point)
        # For this example, let's assume all wall blocks have 2 hits (customize as needed)
        if key not in self.block_cracks:
            self.block_cracks[key] = create_crack_animator(block)
        # Impact point: closest point on block to incoming direction (simulate as center for now)
        impact_x = max(block.left, min(block.centerx, block.right))
        impact_y = max(block.top, min(block.centery, block.bottom))
        impact_point = (int(impact_x), int(impact_y))
        impact_angle = math.atan2(incoming_dir.y, incoming_dir.x)
        self.block_cracks[key].add_crack(impact_point, impact_angle, debug=False)

        self.blocks.remove(block)
        if key in self.block_cracks:
            del self.block_cracks[key]

        # Generate a few debris rectangles for visual feedback
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