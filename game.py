# =============================================================================
# ** LEGACY FILE – NOT USED OR MAINTAINED **
# This is an old standalone game loop kept only for reference.
# The current, actively maintained game loop lives in main.py.
# =============================================================================

import pygame, sys, random
from config import *
from utils import generate_grass
from paddle import Paddle
from ball import Ball
from castle import Castle
from heart import update_hearts, draw_hearts

pygame.init()
pygame.mixer.init()
MUSIC_PATH = "Untitled.mp3"
try:
    pygame.mixer.music.load(MUSIC_PATH)
    pygame.mixer.music.set_volume(0.6)
    pygame.mixer.music.play(-1)
except pygame.error as e:
    print(f"[Audio] Failed to load '{MUSIC_PATH}':", e)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock  = pygame.time.Clock()
font       = pygame.font.SysFont(None, 36)
small_font = pygame.font.SysFont(None, 18)

# Generate a background grass texture once
BACKGROUND = generate_grass(WIDTH, HEIGHT)
BACKGROUND.set_alpha(100) # Fade the background
WHITE_BG = pygame.Surface((WIDTH, HEIGHT))
WHITE_BG.fill(WHITE)


# --- Game setup ---
paddles = {side: Paddle(side) for side in ('top','bottom','left','right')}
castle_level = 1
castle  = Castle(level=castle_level)
balls   = []
power_timers = {}  # side -> (type, expiry_time)
score = 0

# --- helper for circle-rect bounce (duplicated from main.py) ---
def reflect(ball, rect):
    """Robust circle-rectangle reflection producing rounded-corner bounces."""
    orig_speed = ball.vel.length()
    # closest point on rect
    cx = max(rect.left, min(ball.pos.x, rect.right))
    cy = max(rect.top,  min(ball.pos.y, rect.bottom))
    closest = pygame.Vector2(cx, cy)
    normal = ball.pos - closest
    if normal.length_squared() == 0:
        overlaps = [ball.pos.x - rect.left, rect.right - ball.pos.x,
                    ball.pos.y - rect.top, rect.bottom - ball.pos.y]
        min_overlap = min(overlaps)
        idx = overlaps.index(min_overlap)
        if idx == 0: normal = pygame.Vector2(-1,0)
        elif idx==1: normal = pygame.Vector2(1,0)
        elif idx==2: normal = pygame.Vector2(0,-1)
        else: normal = pygame.Vector2(0,1)
    else:
        normal = normal.normalize()
    ball.vel = ball.vel.reflect(normal)
    ball.pos = closest + normal * (BALL_RADIUS + 0.1)
    if orig_speed:
        ball.vel = ball.vel.normalize() * orig_speed

# --- Main loop ---
running = True
last_time = pygame.time.get_ticks()
music_restart_time = 0
while running:
    ms = clock.tick(FPS)
    dt = ms / (1000/60)  # normalize to 60fps speed
    now = pygame.time.get_ticks()
    new_balls = castle.update(ms, score, paddles)
    if new_balls:
        balls.extend(new_balls)

    # restart music if scheduled
    if music_restart_time and pygame.time.get_ticks() >= music_restart_time:
        pygame.mixer.music.play(-1)
        music_restart_time = 0

    # — Event handling —
    for e in pygame.event.get():
        if e.type==pygame.QUIT:
            running=False
        # keypresses
        if e.type==pygame.KEYDOWN or e.type==pygame.KEYUP:
            down = (e.type==pygame.KEYDOWN)
            # spacebar for sticky/shoot (only sticky release logic kept)
            if e.key==pygame.K_SPACE and down:
                # if paddle is sticky, fire a new ball
                for side,p in paddles.items():
                    if power_timers.get(side, [None,0])[0]=='sticky':
                        # shoot out toward castle
                        if abs(WIDTH//2 - p.rect.centerx) > 1 and abs(HEIGHT//2 - p.rect.centery) > 1:
                            dx = (WIDTH//2 - p.rect.centerx)/abs(WIDTH//2 - p.rect.centerx) * BALL_SPEED
                            dy = (HEIGHT//2 - p.rect.centery)/abs(HEIGHT//2 - p.rect.centery) * BALL_SPEED
                            balls.append(Ball(p.rect.centerx, p.rect.centery, dx, dy, WHITE))
    
    # — Update paddles & balls —
    for p in paddles.values():
        p.move()
    
    # Update paddle directions using key state polling
    keys = pygame.key.get_pressed()
    space_down = keys[pygame.K_SPACE]
    paddles['top'].dir    = (-1 if keys[pygame.K_a] else (1 if keys[pygame.K_d] else 0))
    paddles['bottom'].dir = (-1 if keys[pygame.K_LEFT] else (1 if keys[pygame.K_RIGHT] else 0))
    paddles['left'].dir   = (-1 if keys[pygame.K_w] else (1 if keys[pygame.K_s] else 0))
    paddles['right'].dir  = (-1 if keys[pygame.K_UP] else (1 if keys[pygame.K_DOWN] else 0))
    
    # pass bump state
    for p in paddles.values():
        p.set_bump_pressed(space_down)
    
    for ball in balls[:]:
        ball.update(dt)
        # piercing trail
        if hasattr(ball, 'pierce') and ball.pierce:
            for _ in range(2):
                vel = pygame.Vector2(random.uniform(-1,1), random.uniform(-1,1))*0.3
                col = random.choice([(255,255,255), (170,0,255)])
                # create simple pixel particle directly on screen (reuse utils.Particle?)
                # For simplicity, ignore if Particle not imported; use small rect draw later.
            
        r = ball.rect()

        # out-of-bounds removal
        if not screen.get_rect().colliderect(r):
            balls.remove(ball)
            continue

        # check collision with paddles
        for side,p in paddles.items():
            if r.colliderect(p.rect):
                if ball.is_power:
                    # apply powerup and consume the ball
                    power_timers[side] = [ball.power_type, now+10000]
                    if ball.power_type == 'widen':
                        p.enlarge()
                    balls.remove(ball)
                elif ball.color == RED:
                    # red ball damages the paddle but bounces away
                    if power_timers.get(side, [None,0])[0] != 'widen':
                        p.shrink()
                    # Grow paddle if widen is active
                    if power_timers.get(side, [None,0])[0] == 'widen':
                        p.grow_on_hit()
                    if side in ('top','bottom'):
                        ball.vel.y *= -1
                        # Add horizontal component based on paddle motion
                        ball.vel.x += p.vel * LINEAR_TRANSFER
                        # Spin transfer: move right (positive vel) imparts clockwise spin (positive)
                        ball.spin += p.vel * SPIN_TRANSFER
                    else:
                        ball.vel.x *= -1
                        ball.vel.y += p.vel * LINEAR_TRANSFER
                        # For vertical paddles, invert sign so upward motion gives opposite spin direction
                        ball.spin -= p.vel * SPIN_TRANSFER
                    # Boost proportionally to actual bump velocity
                    ball.vel *= p.get_bump_boost()
                    ball.pos += ball.vel * 0.1
                else:
                    # white ball bounces back toward the castle
                    # Grow paddle if widen is active
                    if power_timers.get(side, [None,0])[0] == 'widen':
                        p.grow_on_hit()
                    if side in ('top','bottom'):
                        ball.vel.y *= -1
                        ball.vel.x += p.vel * LINEAR_TRANSFER
                        ball.spin += p.vel * SPIN_TRANSFER
                    else:
                        ball.vel.x *= -1
                        ball.vel.y += p.vel * LINEAR_TRANSFER
                        ball.spin += p.vel * SPIN_TRANSFER
                    # Boost proportionally to actual bump velocity
                    ball.vel *= p.get_bump_boost()
                    # slightly nudge it away so it doesn't instantly collide again
                    ball.pos += ball.vel * 0.1
                break
        else:
            # check collision with castle blocks
            for b in castle.blocks[:]:
                if r.colliderect(b):
                    incoming_dir = ball.vel.normalize() if ball.vel.length_squared()!=0 else pygame.Vector2(0,-1)
                    castle.shatter_block(b, incoming_dir)
                    score += 100
                    reflect(ball, b)
                    ball.pos += ball.vel * 0.1
                    if ball.vel.length() < BALL_SPEED*1.5:
                        ball.vel *= 1.05
                    break

    # Update hearts (movement, collection, expiry)
    update_hearts(dt, ms, balls, paddles)

    # expire powerups
    for side, (ptype, exp) in list(power_timers.items()):
        if now >= exp:
            if ptype=='widen':
                paddles[side].widen()  # Only decrement stack on natural expiry
            del power_timers[side]

    # — Draw everything —
    screen.blit(WHITE_BG, (0,0))
    screen.blit(BACKGROUND, (0,0))
    castle.draw(screen)
    for side, p in paddles.items():
        col = None
        if side in power_timers:
            col = POTION_COLORS.get(power_timers[side][0])
        p.draw(screen, overlay_color=col)
    for ball in balls: ball.draw(screen, small_font)
    # Draw hearts above balls but below HUD
    draw_hearts(screen)
    # HUD – score only bottom-left
    hud = small_font.render(f"Score: {score}", True, (0,0,0))
    screen.blit(hud, (10, HEIGHT-20))
    pygame.display.flip()

    # — Check win/lose —
    if len(castle.blocks)==0 and not castle.destroyed_blocks:
        print("You broke the castle! New one appears.")
        # fadeout and schedule restart
        pygame.mixer.music.fadeout(2000)
        music_restart_time = pygame.time.get_ticks() + 2000
        castle_level += 1
        castle = Castle(level=castle_level)

    if all(p.logical_width<20 for p in paddles.values()):
        print(f"All paddles gone. Game over. Final Score: {score}")
        running=False
    
    if len(castle.blocks) > 0 and len(castle.cannons) == 0:
        print(f"All cannons destroyed. Game over. Final Score: {score}")
        running = False


pygame.quit()
sys.exit() 