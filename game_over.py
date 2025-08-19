import pygame
import sys
import random

def run_game_over(screen, final_score, WIDTH, HEIGHT):
    """
    Displays the game over screen and handles the restart logic.
    """
    # Switch to sombre game-over music that loops a 73-s slice
    try:
        pygame.mixer.music.load('Untitled2.mp3')
        pygame.mixer.music.set_volume(0.6)
        pygame.mixer.music.play(-1)
        last_restart = pygame.time.get_ticks()
        LOOP_MS = 73000  # 1 min 13 s
    except pygame.error as e:
        print('[Audio] Failed to load game-over music:', e)
        LOOP_MS = None
        last_restart = 0

    over_font = pygame.font.Font(None, 72)
    info_font = pygame.font.Font(None, 32)
    restart_font = pygame.font.Font(None, 28)
    txt_main  = over_font.render("Your Castle Has Fallen!", True, (200,0,0))
    txt_score = info_font.render(f"Final Score: {final_score}", True, (0,0,0))
    txt_restart = restart_font.render("Press Spacebar to Restart!", True, (0,0,0))
    txt_menu = restart_font.render("Press Escape for Main Menu", True, (0,0,0))
    main_rect = txt_main.get_rect(center=(WIDTH//2, HEIGHT//2-60))
    score_rect= txt_score.get_rect(center=(WIDTH//2, HEIGHT//2+10))
    restart_rect = txt_restart.get_rect(center=(WIDTH//2, HEIGHT//2+60))
    menu_rect = txt_menu.get_rect(center=(WIDTH//2, HEIGHT//2+90))
    burst = []
    clock2 = pygame.time.Clock()
    # Wait for spacebar to restart
    while True:
        ms2 = clock2.tick(60)
        for e in pygame.event.get():
            if e.type==pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_SPACE:
                    return 'restart'  # Exit game over screen to restart
                if e.key==pygame.K_ESCAPE:
                    return 'main_menu'  # Exit to main menu
        # restart the cropped music slice every 73 s
        if LOOP_MS and pygame.time.get_ticks() - last_restart >= LOOP_MS:
            pygame.mixer.music.play(-1, 0.0)
            last_restart = pygame.time.get_ticks()

        # spawn random confetti particles
        for _ in range(6):
            vel = pygame.Vector2(random.uniform(-2,2), random.uniform(-3,-1))
            clr = random.choice([(255,0,0),(255,120,0),(255,200,0),(200,0,0)])
            burst.append({'pos':pygame.Vector2(WIDTH//2, HEIGHT//2), 'vel':vel, 'color':clr, 'life':60})
        # update
        for p in burst[:]:
            p['pos'] += p['vel']
            p['vel'].y += 0.05
            p['life'] -= 1
            if p['life']<=0:
                burst.remove(p)
        # draw
        screen.fill((255,255,255))
        for p in burst:
            pygame.draw.circle(screen, p['color'], (int(p['pos'].x), int(p['pos'].y)), 3)
        screen.blit(txt_main, main_rect)
        screen.blit(txt_score, score_rect)
        screen.blit(txt_restart, restart_rect)
        screen.blit(txt_menu, menu_rect)
        pygame.display.flip() 