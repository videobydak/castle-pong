# Castle Pong Game - API Documentation

## Overview

Castle Pong is a Pygame-based arcade game that combines elements of Pong and tower defense. Players control paddles to bounce projectiles while defending against an enemy castle that fires back with cannons.

## Table of Contents

1. [Core Game Components](#core-game-components)
2. [Configuration System](#configuration-system)
3. [Utility Functions](#utility-functions)
4. [UI Components](#ui-components)
5. [Game Systems](#game-systems)
6. [Usage Examples](#usage-examples)

---

## Core Game Components

### Ball Class (`ball.py`)

The `Ball` class represents all projectiles in the game including cannonballs, fireballs, and power-up potions.

#### Constructor

```python
Ball(x, y, vx, vy, color, is_power=False, power_type=None, pierce=False, spin=0.0, force_no_spin=False)
```

**Parameters:**
- `x, y` (float): Initial position coordinates
- `vx, vy` (float): Initial velocity components
- `color` (tuple): RGB color tuple for rendering
- `is_power` (bool): Whether this is a power-up potion
- `power_type` (str): Type of power-up ('widen', 'sticky', 'through', 'barrier', 'pierce')
- `pierce` (bool): Whether ball passes through castle blocks
- `spin` (float): Angular velocity in radians per frame
- `force_no_spin` (bool): Disable rotation visual for previews

#### Public Methods

```python
def update(self, dt):
    """Update ball position, physics, and spin effects."""

def draw(self, screen, small_font):
    """Render the ball with appropriate visual style."""

def rect(self):
    """Return pygame.Rect for collision detection."""
```

#### Key Attributes

- `pos`: Current position (pygame.Vector2)
- `vel`: Current velocity (pygame.Vector2)
- `spin`: Angular velocity for Magnus effect
- `stuck_to`: Reference to paddle if ball is stuck
- `friendly`: Whether ball damages castle blocks
- `blocks_hit`: Counter for red ball progression

#### Example Usage

```python
# Create a basic cannonball
ball = Ball(100, 100, 5, -3, WHITE)

# Create a power-up potion
potion = Ball(200, 200, 2, -4, YELLOW, is_power=True, power_type='widen')

# Update and draw
ball.update(dt)
ball.draw(screen, font)
```

---

### Paddle Class (`paddle.py`)

Represents player-controlled paddles that can move, bump, and be modified by power-ups.

#### Constructor

```python
Paddle(side)
```

**Parameters:**
- `side` (str): Paddle position - 'top', 'bottom', 'left', or 'right'

#### Public Methods

```python
def move():
    """Update paddle position based on input and physics."""

def draw(self, screen, overlay_color=None):
    """Render paddle with optional power-up overlay."""

def shrink():
    """Reduce paddle size by 20%."""

def enlarge():
    """Increase paddle size by 50% (stackable)."""

def widen():
    """Restore paddle to base size, decrement widen stack."""

def clear_widen():
    """Immediately restore to base width."""

def grow_on_hit(self, percent=0.1):
    """Grow paddle when hitting balls (if widen active)."""

def set_bump_pressed(self, pressed: bool):
    """Set whether space bar is currently pressed."""

def is_bumping(self):
    """Return True if paddle is extended enough to boost hits."""

def get_bump_boost(self):
    """Return velocity multiplier based on bump speed."""

def bump():
    """Apply inward velocity impulse."""

def update():
    """Update animations and physics (call every frame)."""
```

#### Key Attributes

- `side`: Paddle position ('top', 'bottom', 'left', 'right')
- `rect`: Collision rectangle
- `vel`: Current movement velocity
- `dir`: Input direction (-1, 0, 1)
- `widen_stack`: Number of active widen effects
- `width`: Current paddle width
- `logical_width`: Target width for animations

#### Example Usage

```python
# Create paddles for all sides
paddles = {
    'bottom': Paddle('bottom'),
    'top': Paddle('top'),
    'left': Paddle('left'),
    'right': Paddle('right')
}

# Update paddle movement
keys = pygame.key.get_pressed()
paddles['bottom'].dir = -1 if keys[pygame.K_LEFT] else (1 if keys[pygame.K_RIGHT] else 0)
paddles['bottom'].set_bump_pressed(keys[pygame.K_SPACE])

# Update and draw
for paddle in paddles.values():
    paddle.move()
    paddle.update()
    paddle.draw(screen)
```

---

### Castle Class (`castle.py`)

The main antagonist structure that contains blocks, cannons, and manages enemy AI.

#### Constructor

```python
Castle(level=1, max_dim=None)
```

**Parameters:**
- `level` (int): Difficulty level affecting layout and cannon count
- `max_dim` (int): Maximum castle dimensions for size control

#### Class Methods

```python
@classmethod
def from_mask(cls, mask, block_size=None, level=1, staged_build=False, build_callback=None):
    """Create castle from a 2D numpy array mask."""
```

#### Public Methods

```python
def update(self, dt_ms, player_score=0, paddles=None, player_wall=None, balls=None):
    """Update castle logic, cannons, and return new projectiles."""

def draw(self, screen):
    """Render all castle blocks and effects."""

def hit_block(self, block, impact_point=None, impact_angle=None):
    """Damage a castle block."""

def shatter_block(self, block, incoming_dir):
    """Completely destroy a block and create debris."""

def get_block_texture(self, block):
    """Get cached texture for a block."""
```

#### Key Attributes

- `blocks`: List of pygame.Rect objects for castle structure
- `cannons`: List of Cannon objects
- `shooting_enabled`: Whether cannons can fire
- `block_health`: Health values for each block
- `block_colors`: Color mapping for blocks
- `debris`: List of debris particles
- `level`: Current difficulty level

#### Example Usage

```python
# Create castle for wave 3
castle = Castle(level=3)

# Update castle (returns new projectiles)
new_balls = castle.update(dt_ms, score, paddles, player_wall, existing_balls)
balls.extend(new_balls)

# Handle block collision
for ball in balls:
    for block in castle.blocks:
        if ball.rect().colliderect(block):
            castle.hit_block(block)
            break

# Draw castle
castle.draw(screen)
```

---

### Cannon Class (`cannon.py`)

Individual cannon entities that can move along the castle perimeter and fire projectiles.

#### Constructor

```python
Cannon(block, side, pos, rail_info, total_shots_ref, shooting_enabled_ref, smoke_particles_ref, level=1)
```

**Parameters:**
- `block`: Associated castle block
- `side`: Castle side ('top', 'bottom', 'left', 'right')
- `pos`: Initial position (pygame.Vector2)
- `rail_info`: Rail system for movement
- `total_shots_ref`: Function returning total shots fired
- `shooting_enabled_ref`: Function returning whether shooting is enabled
- `smoke_particles_ref`: Reference to smoke particle list
- `level`: Current wave level

#### Public Methods

```python
def draw(self, screen, now, preview_types, _preview_col_map):
    """Render cannon with barrel, base, and preview projectile."""

def spawn_ball(self, shot_type, _prepare_shot_sounds, _SHOT_SOUNDS):
    """Create and return a Ball fired from the cannon."""
```

#### Key Attributes

- `pos`: Current position
- `angle`: Barrel angle in degrees
- `state`: Current AI state ('idle', 'charging', 'moving')
- `sprout_scale`: Animation scale for appearance
- `can_shoot`: Whether cannon is ready to fire

#### Example Usage

```python
# Cannon is typically created by Castle class
# Drawing and updates are handled by Castle.update() and Castle.draw()

# Manual cannon creation (advanced usage)
cannon = Cannon(
    block=castle_block,
    side='top',
    pos=pygame.Vector2(x, y),
    rail_info=castle.rail_info,
    total_shots_ref=lambda: Castle.total_shots,
    shooting_enabled_ref=lambda: castle.shooting_enabled,
    smoke_particles_ref=castle.smoke_particles,
    level=current_level
)
```

---

## Configuration System

### config.py

Central configuration file containing all game constants and settings.

#### Display Settings

```python
WIDTH, HEIGHT = 1280, 900
FPS = 120
```

#### Game Object Sizes

```python
BASE_BLOCK_SIZE = 30
BLOCK_SIZE = 45
SCALE = BLOCK_SIZE / BASE_BLOCK_SIZE

PADDLE_THICK = int(12 * SCALE)
PADDLE_LEN = int(150 * SCALE)
BALL_RADIUS = int(8 * SCALE)
CANNON_GAP = int(10 * SCALE)
CANNON_LEN = int(25 * SCALE)
```

#### Physics Constants

```python
PADDLE_MAX_SPEED = 10      # pixels per frame
PADDLE_ACCEL = 0.6         # acceleration per frame
PADDLE_FRICTION = 0.85     # velocity retention
BALL_SPEED = 5
BALL_FRICTION = 0.999
MAGNUS_COEFF = 0.054       # Spin effect strength
SPIN_DAMPING = 0.995       # Spin decay per frame
SPIN_TRANSFER = 0.1        # Paddle to ball spin transfer
```

#### Color Definitions

```python
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
BG = (30, 30, 30)
GREY = (100, 100, 100)
```

#### Power-up System

```python
POTION_COLORS = {
    'widen': (0, 120, 255),      # blue
    'sticky': (0, 200, 0),       # green
    'through': (255, 140, 0),    # orange
    'barrier': (0, 255, 255),    # cyan
    'pierce': (200, 0, 255)      # purple
}

POTION_TYPE_WEIGHTS = [
    ('widen', 20),   # most common
    ('sticky', 20),  # most common
    ('through', 10), # uncommon
    ('barrier', 5),  # rare
    ('pierce', 2)    # rarest
]
```

#### Example Usage

```python
from config import *

# Use constants in game logic
if ball.vel.length() > BALL_SPEED * 2:
    ball.vel = ball.vel.normalize() * BALL_SPEED

# Get random power-up type
power_type = get_random_potion_type()
```

---

## Utility Functions

### utils.py

Collection of helper functions for texture generation and particle effects.

#### Texture Generation

```python
def generate_grass(w, h):
    """Generate tiled grass background texture."""

def make_checker(size, col1, col2):
    """Create checkerboard pattern."""

def make_bricks(size, base_col=BLOCK_COLOR_DEFAULT[0], mortar_col=(60,60,60), **kwargs):
    """Generate brick texture with highlights and shadows."""

def make_round_bricks(size, base_col=BLOCK_COLOR_DEFAULT[0], mortar_col=(60,60,60), corner='tl'):
    """Generate brick texture with rounded corner."""

def make_garden(size):
    """Create grass/garden tile texture."""

def make_wood(size=8, base_col=(176, 96, 32)):
    """Generate wood plank texture."""
```

#### Particle System

```python
class Particle:
    def __init__(self, x, y, vel, color, life, size=1, alpha=255, fade=True, friction=None):
        """Create particle with physics and visual properties."""
    
    def update(self):
        """Update particle position and lifetime."""
    
    def draw(self, surf):
        """Render particle to surface."""
```

#### Example Usage

```python
from utils import generate_grass, make_bricks, Particle

# Create background
background = generate_grass(WIDTH, HEIGHT)

# Generate brick texture for castle blocks
brick_texture = make_bricks(BLOCK_SIZE, (100, 100, 100))

# Create explosion particles
particles = []
for i in range(20):
    vel = pygame.Vector2(random.uniform(-5, 5), random.uniform(-5, 5))
    particle = Particle(x, y, vel, RED, life=60, size=3)
    particles.append(particle)

# Update particles
for particle in particles[:]:
    particle.update()
    if particle.life <= 0:
        particles.remove(particle)
    else:
        particle.draw(screen)
```

---

## UI Components

### TutorialOverlay Class (`tutorial.py`)

Main menu system with animated background and button controls.

#### Constructor

```python
TutorialOverlay()
```

#### Public Methods

```python
def update(self, events):
    """Process input events and update animations."""

def draw(self, surface: pygame.Surface):
    """Render menu interface."""

def complete_loading(self):
    """Transition from loading state to game start."""
```

#### Key Attributes

- `active`: Whether overlay is currently shown
- `loading`: Whether in loading state
- `buttons`: List of menu button configurations

#### Example Usage

```python
tutorial = TutorialOverlay()

# Main menu loop
while tutorial.active:
    events = pygame.event.get()
    tutorial.update(events)
    tutorial.draw(screen)
    pygame.display.flip()

# Start game after menu closes
if not tutorial.active:
    start_game()
```

### PauseMenu Class (`pause_menu.py`)

In-game pause functionality with resume/quit options.

#### Constructor

```python
PauseMenu()
```

#### Public Methods

```python
def update(self, events):
    """Handle pause menu input."""

def draw(self, screen):
    """Render pause menu overlay."""

def toggle(self):
    """Show/hide pause menu."""
```

### GameOver Module (`game_over.py`)

Game over screen with score display and restart options.

#### Functions

```python
def run_game_over(screen, font, final_score):
    """Display game over screen and handle input."""
```

---

## Game Systems

### Physics System

The game implements realistic ball physics with:

- **Collision Detection**: Circle-rectangle collision for balls and paddles/blocks
- **Magnus Effect**: Spinning balls curve in flight
- **Friction**: Gradual velocity reduction for realistic movement
- **Elastic Collisions**: Energy-conserving bounces with momentum transfer

### Power-up System

Five types of power-ups affect gameplay:

1. **Widen** (Blue): Enlarges paddle by 50%, stackable
2. **Sticky** (Green): Balls stick to paddle, release with spacebar
3. **Through** (Orange): Balls pass through blocks once
4. **Barrier** (Cyan): Temporary protective shield
5. **Pierce** (Purple): Balls penetrate multiple blocks

### Wave Progression

- Castles grow larger and more complex each wave
- Cannon count increases (2 → 5 maximum)
- Shooting frequency and accuracy improve
- Block health increases in later waves

### Audio System

- Background music changes between menu and gameplay
- Sound effects for collisions, power-ups, and destruction
- Positional audio for cannon shots with pitch variation

---

## Usage Examples

### Basic Game Setup

```python
import pygame
from config import *
from paddle import Paddle
from ball import Ball
from castle import Castle
from tutorial import TutorialOverlay

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# Initialize game objects
tutorial = TutorialOverlay()
paddles = {'bottom': Paddle('bottom')}
castle = Castle(level=1)
balls = []
score = 0

# Main game loop
running = True
while running:
    dt = clock.tick(FPS)
    
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    if tutorial.active:
        tutorial.update(pygame.event.get())
        tutorial.draw(screen)
    else:
        # Game logic
        keys = pygame.key.get_pressed()
        paddles['bottom'].dir = (-1 if keys[pygame.K_LEFT] else 
                                 1 if keys[pygame.K_RIGHT] else 0)
        
        # Update game objects
        for paddle in paddles.values():
            paddle.move()
            paddle.update()
        
        for ball in balls[:]:
            ball.update(dt/1000)
            # Remove out-of-bounds balls
            if not screen.get_rect().colliderect(ball.rect()):
                balls.remove(ball)
        
        new_balls = castle.update(dt, score, paddles, None, balls)
        balls.extend(new_balls)
        
        # Draw everything
        screen.fill(BG)
        castle.draw(screen)
        for paddle in paddles.values():
            paddle.draw(screen)
        for ball in balls:
            ball.draw(screen, None)
    
    pygame.display.flip()

pygame.quit()
```

### Custom Ball Creation

```python
# Create different types of projectiles
cannonball = Ball(x, y, vx, vy, WHITE, spin=0.2)
fireball = Ball(x, y, vx, vy, RED, spin=-0.1)
potion = Ball(x, y, vx, vy, YELLOW, is_power=True, power_type='widen')
piercing = Ball(x, y, vx, vy, WHITE, pierce=True, spin=0.5)

# Ball with custom properties
sticky_ball = Ball(x, y, vx, vy, GREEN)
sticky_ball.stuck_to = paddle
sticky_ball.stuck_offset = pygame.Vector2(10, 0)
```

### Advanced Castle Configuration

```python
import numpy as np
from castle import Castle

# Create custom castle from mask
mask = np.array([
    [1, 1, 1, 1, 1],
    [1, 0, 1, 0, 1],
    [1, 1, 1, 1, 1],
    [0, 1, 1, 1, 0],
    [0, 0, 1, 0, 0]
])

castle = Castle.from_mask(
    mask, 
    block_size=BLOCK_SIZE, 
    level=5,
    staged_build=True,
    build_callback=lambda typ, idx: print(f"Built {typ} at {idx}")
)
```

### Particle Effects

```python
from utils import Particle

def create_explosion(x, y, count=20):
    particles = []
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 8)
        vel = pygame.Vector2(
            math.cos(angle) * speed,
            math.sin(angle) * speed
        )
        color = random.choice([RED, YELLOW, (255, 128, 0)])
        particle = Particle(x, y, vel, color, life=40, size=3)
        particles.append(particle)
    return particles

# Use in game loop
explosion_particles = create_explosion(impact_x, impact_y)
for particle in explosion_particles:
    particle.update()
    particle.draw(screen)
```

---

## Dependencies

- **pygame**: Main game framework
- **numpy**: Array operations for castle generation
- **random**: Procedural generation and effects
- **math**: Mathematical calculations
- **sys**: System operations
- **os**: File system access

## Installation

```bash
pip install pygame numpy
```

## Running the Game

```bash
python main.py
```

---

This documentation covers all major public APIs and components in the Castle Pong game. Each class and function includes parameter descriptions, usage examples, and key attributes to help developers understand and extend the codebase.