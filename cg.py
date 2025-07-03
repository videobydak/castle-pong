import random
import numpy as np
from enum import Enum
import matplotlib.pyplot as plt
import time
import scipy.ndimage  # for label
from scipy.ndimage import label

class BlockType(Enum):
    EMPTY = 0      # Empty space
    GRASS = 1      # Grass / outside ground
    # --- Wall layers (aliases so BlockType.WALL maps to layer-1 for legacy code) ---
    WALL = 2       # Legacy alias for layer-1 walls
    WALL_L1 = 2    # First (darkest) reinforcement layer
    WALL_L2 = 3    # Second (medium tone) layer
    WALL_L3 = 4    # Third (lightest) layer
    FLOOR = 5      # Interior floors (shifted to avoid clashing with new wall values)

class CastleGenerator:
    def __init__(self, width=50, height=50, symmetry_mode=None):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=int)
        # Choose symmetry: 'vertical', 'horizontal', 'both', or 'none'
        if symmetry_mode is not None:
            self.symmetry_mode = symmetry_mode
        else:
            if width == height:
                self.symmetry_mode = 'both'  # 2-axis for square
            else:
                self.symmetry_mode = 'vertical'  # vertical for wide

    def generate_castle(self, difficulty=None):
        """Main generation function that orchestrates the castle creation, with difficulty-based bias."""
        max_attempts = 10
        for attempt in range(max_attempts):
            self.grid.fill(BlockType.GRASS.value)

            # If not provided, estimate difficulty from size (for demo)
            if difficulty is None:
                difficulty = 50

            # Difficulty-based layout bias
            if difficulty >= 70:
                # Always large central keep, plus side structures
                self._generate_concentric_rings()
                self._generate_main_keep()
                self._generate_side_structures(bias='sides')
                self._add_details()
            elif difficulty >= 40:
                # Mix: central keep, some small sub-castles, more likely on sides
                if random.random() < 0.6:
                    self._generate_concentric_rings()
                    self._generate_main_keep()
                if random.random() < 0.7:
                    self._generate_small_castles(bias='sides')
                self._add_details()
            elif difficulty >= 20:
                # Gradual migration: good chance of small central keep with side buildings
                if random.random() < 0.5:
                    self._generate_main_keep()
                    if random.random() < 0.6:
                        self._generate_side_structures(bias='sides')
                else:
                    self._generate_small_castles(bias='sides')
                self._add_details()
            else:
                # Very low difficulty: mostly small, scattered sub-castles
                if random.random() < 0.7:
                    self._generate_small_castles(bias='random')
                else:
                    self._generate_main_keep()
                self._add_details()

            self._enforce_symmetry()

            # Check for at least one wall
            if np.any(self.grid == BlockType.WALL.value):
                return self.grid
        # If all attempts fail, just force a single wall in the center
        self.grid[self.height // 2, self.width // 2] = BlockType.WALL.value
        return self.grid

    def _enforce_symmetry(self):
        """Mirror the grid according to the chosen symmetry mode."""
        h, w = self.height, self.width
        mode = self.symmetry_mode
        if mode == 'both':
            # 2-axis (vertical + horizontal)
            for y in range(h // 2):
                for x in range(w // 2):
                    val = self.grid[y, x]
                    self.grid[h-1-y, x] = val
                    self.grid[y, w-1-x] = val
                    self.grid[h-1-y, w-1-x] = val
        elif mode == 'vertical':
            # Mirror left/right
            for y in range(h):
                for x in range(w // 2):
                    val = self.grid[y, x]
                    self.grid[y, w-1-x] = val
        elif mode == 'horizontal':
            # Mirror top/bottom
            for y in range(h // 2):
                for x in range(w):
                    val = self.grid[y, x]
                    self.grid[h-1-y, x] = val
        # else: 'none' (no symmetry)

    def _generate_side_structures(self, bias='sides'):
        """Add small sub-castles or clusters to the left/right sides."""
        # Place 1-2 small structures on each side
        margin = 2
        h, w = self.height, self.width
        for side in ['left', 'right']:
            for _ in range(random.randint(1, 2)):
                wsize, hsize = random.choice([(3, 3), (4, 2), (2, 4), (5, 3)])
                y = random.randint(margin, h - hsize - margin)
                if side == 'left':
                    x = random.randint(margin, w//3 - wsize)
                else:
                    x = random.randint(w*2//3, w - wsize - margin)
                self._draw_rectangle(x, y, x + wsize - 1, y + hsize - 1, BlockType.WALL.value)
                if wsize > 2 and hsize > 2:
                    self._fill_rectangle(x + 1, y + 1, x + wsize - 2, y + hsize - 2, BlockType.FLOOR.value)

    def _generate_small_castles(self, bias='random'):
        """Randomly place several small sub-castles (3x3, 4x2, 1x3, etc.) in the grid, with optional bias."""
        small_castle_types = [
            (3, 3), (4, 2), (2, 4), (1, 3), (3, 1), (5, 5)
        ]
        num_castles = random.randint(2, 5)
        margin = 1
        h, w = self.height, self.width
        for _ in range(num_castles):
            wsize, hsize = random.choice(small_castle_types)
            if bias == 'sides':
                # Place more often on left/right thirds
                y_range = h - hsize - margin
                if y_range < margin:
                    continue  # skip if not enough vertical space
                y = random.randint(margin, y_range)
                left_x_max = w//3 - wsize
                right_x_min = w*2//3
                right_x_max = w - wsize - margin
                if random.random() < 0.5:
                    # Left side
                    if left_x_max < margin:
                        continue  # skip if not enough horizontal space
                    x = random.randint(margin, left_x_max)
                else:
                    # Right side
                    if right_x_max < right_x_min:
                        continue  # skip if not enough horizontal space
                    x = random.randint(right_x_min, right_x_max)
            else:
                max_x = w - wsize - margin
                max_y = h - hsize - margin
                if max_x < margin or max_y < margin:
                    continue
                x = random.randint(margin, max_x)
                y = random.randint(margin, max_y)
            self._draw_rectangle(x, y, x + wsize - 1, y + hsize - 1, BlockType.WALL.value)
            if wsize > 2 and hsize > 2:
                self._fill_rectangle(x + 1, y + 1, x + wsize - 2, y + hsize - 2, BlockType.FLOOR.value)

    def _generate_main_keep(self):
        """Generate the central keep structure"""
        # Main keep dimensions (roughly center, but allow some offset)
        keep_width = random.randint(8, 12)
        keep_height = random.randint(8, 12)
        
        center_x = self.width // 2 + random.randint(-3, 3)
        center_y = self.height // 2 + random.randint(-3, 3)
        
        # Ensure keep fits in bounds
        start_x = max(2, center_x - keep_width // 2)
        end_x = min(self.width - 2, start_x + keep_width)
        start_y = max(2, center_y - keep_height // 2)
        end_y = min(self.height - 2, start_y + keep_height)
        
        # Create keep outline
        self._draw_rectangle(start_x, start_y, end_x, end_y, BlockType.WALL.value)
        
        # Fill interior with floor
        self._fill_rectangle(start_x + 1, start_y + 1, end_x - 1, end_y - 1, BlockType.FLOOR.value)
        
        # Add some internal walls for rooms
        if keep_width > 6 and keep_height > 6:
            mid_x = (start_x + end_x) // 2
            mid_y = (start_y + end_y) // 2
            
            # Vertical divider
            for y in range(start_y + 1, end_y):
                if random.random() > 0.3:  # Leave some gaps for doors
                    self.grid[y, mid_x] = BlockType.WALL.value
            
            # Horizontal divider
            for x in range(start_x + 1, end_x):
                if random.random() > 0.3:
                    self.grid[mid_y, x] = BlockType.WALL.value
    
    def _generate_concentric_rings(self):
        """Add several concentric wall rings to the grid."""
        num_rings = random.randint(2, 4)
        min_margin = 1
        max_margin = min(self.width, self.height) // 2 - 1
        for i in range(num_rings):
            margin = min_margin + i * (max_margin // max(1, num_rings - 1))
            self._draw_rectangle(margin, margin, self.width - 1 - margin, self.height - 1 - margin, BlockType.WALL.value)
    
    def _generate_towers(self):
        """Add towers at strategic points"""
        # Find wall corners and add towers
        wall_positions = np.where(self.grid == BlockType.WALL.value)
        
        # Add corner towers
        corners = [
            (8, 8), (self.width - 8, 8),
            (self.width - 8, self.height - 8), (8, self.height - 8)
        ]
        
        for cx, cy in corners:
            if 3 < cx < self.width - 3 and 3 < cy < self.height - 3:
                self._add_tower(cx, cy)
    
    def _add_tower(self, cx, cy):
        """Add a circular tower at the given position"""
        radius = random.randint(2, 4)
        
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (0 <= x < self.width and 0 <= y < self.height and
                    (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2):
                    
                    if (x - cx) ** 2 + (y - cy) ** 2 == radius ** 2 or \
                       (x - cx) ** 2 + (y - cy) ** 2 == (radius - 1) ** 2:
                        self.grid[y, x] = BlockType.WALL.value
                    elif (x - cx) ** 2 + (y - cy) ** 2 < (radius - 1) ** 2:
                        self.grid[y, x] = BlockType.FLOOR.value
    
    def _add_details(self):
        """Add small decorative details"""
        # Add some scattered walls for ruins/details
        for _ in range(random.randint(5, 15)):
            x = random.randint(1, self.width - 2)
            y = random.randint(1, self.height - 2)
            
            if self.grid[y, x] == BlockType.GRASS.value:
                # Small chance to add isolated wall segments
                if random.random() > 0.8:
                    self.grid[y, x] = BlockType.WALL.value
    
    def _draw_rectangle(self, x1, y1, x2, y2, value):
        """Draw rectangle outline"""
        for x in range(x1, x2 + 1):
            self.grid[y1, x] = value
            self.grid[y2, x] = value
        for y in range(y1, y2 + 1):
            self.grid[y, x1] = value
            self.grid[y, x2] = value
    
    def _fill_rectangle(self, x1, y1, x2, y2, value):
        """Fill rectangle with value"""
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.grid[y, x] = value
    
    def _draw_line(self, x1, y1, x2, y2, value):
        """Draw line using Bresenham's algorithm"""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        x, y = x1, y1
        n = 1 + dx + dy
        x_inc = 1 if x2 > x1 else -1
        y_inc = 1 if y2 > y1 else -1
        error = dx - dy
        
        dx *= 2
        dy *= 2
        
        for _ in range(n):
            if 0 <= x < self.width and 0 <= y < self.height:
                self.grid[y, x] = value
            
            if error > 0:
                x += x_inc
                error -= dy
            else:
                y += y_inc
                error += dx
    
    def print_castle(self):
        """Print the castle layout with numbers"""
        print("Castle Layout:")
        print("0=Empty, 1=Grass, 2=Wall-L1, 3=Wall-L2, 4=Wall-L3, 5=Floor")
        print("-" * (self.width * 2))
        
        for row in self.grid:
            print(' '.join(str(cell) for cell in row))

    def compute_difficulty(self):
        """Compute a difficulty rating (0-100) based on wall density, corners, chambers, and footprint."""
        grid = self.grid
        total_tiles = self.width * self.height
        # Treat *any* wall layer (value ≥ 2) as a wall for difficulty purposes
        wall_mask = (grid >= BlockType.WALL.value)
        wall_count = (grid >= 2).sum()
        # 1. Wall density (more walls = harder)
        wall_density = wall_count / total_tiles

        # 2. Number of corners (a corner is a wall with 2 perpendicular wall neighbors)
        corners = 0
        for y in range(1, self.height-1):
            for x in range(1, self.width-1):
                if wall_mask[y, x]:
                    n = wall_mask[y-1, x]
                    s = wall_mask[y+1, x]
                    e = wall_mask[y, x+1]
                    w = wall_mask[y, x-1]
                    if (n and e) or (n and w) or (s and e) or (s and w):
                        if not ((n and s) or (e and w)):
                            corners += 1
        # 3. Number of chambers (connected regions of floor or grass inside walls)
        interior_mask = (grid != BlockType.WALL.value)
        chambers, num_chambers = label(interior_mask)
        # 4. Footprint (bounding box area of all wall tiles)
        wall_ys, wall_xs = np.where(wall_mask)
        if wall_ys.size > 0 and wall_xs.size > 0:
            min_x, max_x = wall_xs.min(), wall_xs.max()
            min_y, max_y = wall_ys.min(), wall_ys.max()
            footprint = (max_x - min_x + 1) * (max_y - min_y + 1)
        else:
            footprint = 0
        # Normalize features and combine for difficulty (weights can be tuned)
        density_score = wall_density
        corner_score = min(corners / 12, 1.0)  # 12+ corners is max
        chamber_score = min(num_chambers / 8, 1.0)  # 8+ chambers is max
        footprint_score = min(footprint / total_tiles, 1.0)
        # Weighted sum (tune as needed)
        difficulty = (
            0.4 * density_score +
            0.2 * corner_score +
            0.2 * chamber_score +
            0.2 * footprint_score
        )
        return int(round(difficulty * 100))

def center_mask(mask):
    """Return a new mask with the non-empty (structure) part centered in the grid."""
    # Consider any tile >= 2 (wall or higher) as structure
    structure = (mask >= 2)
    if not np.any(structure):
        return mask.copy()  # nothing to center
    ys, xs = np.where(structure)
    min_y, max_y = ys.min(), ys.max()
    min_x, max_x = xs.min(), xs.max()
    h, w = mask.shape
    box_h = max_y - min_y + 1
    box_w = max_x - min_x + 1
    # Target center
    center_y, center_x = h // 2, w // 2
    # Box center
    box_center_y = (min_y + max_y) // 2
    box_center_x = (min_x + max_x) // 2
    # Offset needed to move box center to grid center
    dy = center_y - box_center_y
    dx = center_x - box_center_x
    # Create new mask
    new_mask = np.zeros_like(mask)
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            ny = y + dy
            nx = x + dx
            if 0 <= ny < h and 0 <= nx < w:
                new_mask[ny, nx] = mask[y, x]
    return new_mask

def generate_mask_for_difficulty(width, height, target, tolerance=2, min_wall_blocks=4):
    """Generate a mask (grid) with difficulty within target ± tolerance. Retries until success and at least min_wall_blocks wall blocks."""
    while True:
        generator = CastleGenerator(width, height)
        mask = generator.generate_castle()
        # Center the structure before reinforcement
        mask = center_mask(mask)
        difficulty = generator.compute_difficulty()
        # Any wall layer counts – 2,3,4
        wall_count = (mask >= 2).sum()
        print(f"[DEBUG] generate_mask: target={target}, got={difficulty}, wall tiles={wall_count}")
        if abs(difficulty - target) <= tolerance and wall_count >= min_wall_blocks:
            # Once we have a valid base mask, upgrade to reinforced layers.
            # Use the *target* difficulty (wave design) rather than the
            # computed difficulty so reinforcement probabilities align with
            # the intended wave progression.
            from reinforced_blocks import apply_reinforcement_layers
            mask = apply_reinforcement_layers(mask, target)
            return mask

# Demo usage
if __name__ == "__main__":
    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots(figsize=(6.7, 5))
    img_display = ax.imshow(np.ones((15, 20), dtype=np.uint8) * 255, cmap='gray', vmin=0, vmax=255)
    plt.axis('off')
    title = ax.set_title('')
    fig.show()

    # Difficulty targets: 5, 10, 15, ..., 100
    targets = list(range(5, 101, 5))
    maps_per_target = 2
    tolerance = 2  # percent
    max_attempts = 100

    try:
        for target in targets:
            for _ in range(maps_per_target):
                for attempt in range(max_attempts):
                    # Use the same mask generation as the main game, which applies reinforcement
                    mask = generate_mask_for_difficulty(20, 15, target, tolerance)
                    # Compute difficulty for display
                    generator = CastleGenerator(20, 15)
                    generator.grid = mask.copy()
                    difficulty = generator.compute_difficulty()
                    img = np.ones((15, 20), dtype=np.uint8) * 255  # default: white
                    # Black for layer 1, mid grey for layer 2, light grey for layer 3
                    img[mask == BlockType.WALL_L1.value] = 0      # black
                    img[mask == BlockType.WALL_L2.value] = 128    # mid grey
                    img[mask == BlockType.WALL_L3.value] = 200    # light grey
                    img_display.set_data(img)
                    title.set_text(f'Castle Pattern (20x15) - Difficulty: {difficulty}% (Target: {target}%)')
                    fig.canvas.draw_idle()
                    plt.pause(3)
                    break
                else:
                    # Could not find a map in range after max_attempts
                    title.set_text(f'No map found for {target}% after {max_attempts} attempts')
                    fig.canvas.draw_idle()
                    plt.pause(2)
    except KeyboardInterrupt:
        pass