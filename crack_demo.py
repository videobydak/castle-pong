import pygame
import sys
import random
import math
import time
from config import (
    CRACK_SEGMENTS_BASE, CRACK_SEGMENTS_RANDOM, CRACK_SEGMENT_LENGTH_BASE, CRACK_SEGMENT_LENGTH_RANDOM,
    CRACK_BRANCH_PROB, CRACK_BRANCH_MIN, CRACK_BRANCH_MAX, CRACK_ANGLE_RANDOMNESS, CRACK_WIDTH, CRACK_COLOR
)

WIDTH, HEIGHT = 400, 400
BLOCK_SIZE = 200
FPS = 60

class CrackAnimator:
    def __init__(self, rect):
        self.rect = rect
        self.cracks = []  # List of polylines
        self.animated_cracks = []  # List of (polyline, progress)
        self.animating = False
        self.animation_speed = 0.25
        self.debug_impacts = []  # List of (origin, angle)

    def reset(self):
        self.cracks = []
        self.animated_cracks = []
        self.animating = False
        self.debug_impacts = []

    def add_crack(self, impact_point, impact_angle, debug=True):
        # Add a new crack from a given point and angle
        num_segments = CRACK_SEGMENTS_BASE + random.randint(0, CRACK_SEGMENTS_RANDOM)
        new_cracks = []
        for _ in range(num_segments):
            length = CRACK_SEGMENT_LENGTH_BASE + random.randint(0, CRACK_SEGMENT_LENGTH_RANDOM)
            polyline = [impact_point]
            end = (
                int(impact_point[0] + length * math.cos(impact_angle)),
                int(impact_point[1] + length * math.sin(impact_angle))
            )
            end = self._clip_to_rect(impact_point, end)
            polyline.append(end)
            self._grow_crack(polyline, end, impact_angle, length, 0)
            new_cracks.append(polyline)
        self.animated_cracks = [(polyline, 0) for polyline in new_cracks]
        self.animating = True
        if debug:
            self.debug_impacts.append((impact_point, impact_angle))

    def _grow_crack(self, polyline, start, angle, length, depth):
        if random.random() < CRACK_BRANCH_PROB and depth < 2:
            num_branches = random.randint(CRACK_BRANCH_MIN, CRACK_BRANCH_MAX)
            for _ in range(num_branches):
                branch_angle = angle + random.uniform(-CRACK_ANGLE_RANDOMNESS, CRACK_ANGLE_RANDOMNESS)
                branch_length = length * random.uniform(0.5, 0.8)
                end = (
                    int(start[0] + branch_length * math.cos(branch_angle)),
                    int(start[1] + branch_length * math.sin(branch_angle))
                )
                end = self._clip_to_rect(start, end)
                polyline.append(end)
                self._grow_crack(polyline, end, branch_angle, branch_length, depth+1)

    def _clip_to_rect(self, start, end):
        x, y = end
        x = max(self.rect.left, min(self.rect.right, x))
        y = max(self.rect.top, min(self.rect.bottom, y))
        return (x, y)

    def update(self):
        if self.animating:
            finished = True
            new_animated = []
            for polyline, progress in self.animated_cracks:
                segs = len(polyline) - 1
                if progress < segs:
                    progress += self.animation_speed
                    finished = False
                new_animated.append((polyline, progress))
            self.animated_cracks = new_animated
            if finished:
                for polyline, _ in self.animated_cracks:
                    self.cracks.append(polyline)
                self.animated_cracks = []
                self.animating = False

    def draw(self, surface, show_debug=True):
        # Draw permanent cracks
        for polyline in self.cracks:
            if len(polyline) > 1:
                pygame.draw.lines(surface, CRACK_COLOR, False, polyline, CRACK_WIDTH)
        # Draw animating cracks
        for polyline, progress in self.animated_cracks:
            segs = len(polyline) - 1
            if segs < 1:
                continue
            full_segs = int(progress)
            if full_segs > 0:
                pygame.draw.lines(surface, CRACK_COLOR, False, polyline[:full_segs+1], CRACK_WIDTH)
            if full_segs < segs:
                start = polyline[full_segs]
                end = polyline[full_segs+1]
                t = progress - full_segs
                interp = (
                    int(start[0] + (end[0] - start[0]) * t),
                    int(start[1] + (end[1] - start[1]) * t)
                )
                pygame.draw.line(surface, CRACK_COLOR, start, interp, CRACK_WIDTH)
        # Debug: draw impact points and angles
        if show_debug:
            line_len = 50
            for origin, angle in self.debug_impacts:
                pygame.draw.circle(surface, (255,0,0), origin, 7)
                end = (
                    int(origin[0] + line_len * math.cos(angle)),
                    int(origin[1] + line_len * math.sin(angle))
                )
                pygame.draw.line(surface, (255,0,0), origin, end, 3)

# Exportable for game integration

def create_crack_animator(rect):
    """Factory function to create a CrackAnimator for a given block rect."""
    return CrackAnimator(rect)

# Demo using CrackAnimator

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Procedural Crack Demo')
    clock = pygame.time.Clock()
    block_rect = pygame.Rect((WIDTH-BLOCK_SIZE)//2, (HEIGHT-BLOCK_SIZE)//2, BLOCK_SIZE, BLOCK_SIZE)
    crack_anim = CrackAnimator(block_rect)
    last_hit_time = time.time()
    hit_count = 0
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        now = time.time()
        if not crack_anim.animating and now - last_hit_time > 5:
            hit_count += 1
            if hit_count > 2:
                crack_anim.reset()
                hit_count = 1
            # For demo: randomize impact location and angle on perimeter
            side = random.randint(0, 3)
            if side == 0:  # top
                x = random.randint(block_rect.left, block_rect.right)
                y = block_rect.top
                angle = random.uniform(math.radians(60), math.radians(120))
            elif side == 1:  # right
                x = block_rect.right
                y = random.randint(block_rect.top, block_rect.bottom)
                angle = random.uniform(math.radians(150), math.radians(210))
            elif side == 2:  # bottom
                x = random.randint(block_rect.left, block_rect.right)
                y = block_rect.bottom
                angle = random.uniform(math.radians(240), math.radians(300))
            else:  # left
                x = block_rect.left
                y = random.randint(block_rect.top, block_rect.bottom)
                angle = random.uniform(math.radians(-30), math.radians(30))
            crack_anim.add_crack((x, y), angle, debug=True)
            last_hit_time = now
        crack_anim.update()
        screen.fill((200,200,200))
        pygame.draw.rect(screen, (255,255,255), block_rect)
        pygame.draw.rect(screen, (0,0,0), block_rect, 4)
        crack_anim.draw(screen, show_debug=True)
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main() 