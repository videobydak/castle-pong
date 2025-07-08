import random
import pygame
from typing import Dict, Any
from config import PADDLE_LEN, WIDTH, HEIGHT, PADDLE_MARGIN, SCALE
import coin
import math

# Upgrade state tracking
upgrade_states = {
    'coin_multiplier_active': False,
    'coin_multiplier_timer': 0,
    'time_slow_active': False,
    'time_slow_timer': 0,
    'shield_barrier_active': False,
    'shield_barrier_timer': 0,
    'ghost_paddle_active': False,
    'ghost_paddle_timer': 0,
    'repair_drone_active': False,
    'repair_drone_timer': 0,
    'repair_drone_interval': 5000,  # repair every 5 seconds
    'emergency_heal_uses': 0,
    'multi_ball_charges': 0,
    'power_shot_charges': 0,
    'lucky_charm_active': False,
    'lucky_charm_timer': 0,
    'block_vision_active': False,
    'block_vision_timer': 0,
    'wave_preview_active': False,
    'extra_lives': 0,
    'auto_collect_level': 0,
    'score_bonus_level': 0,
}

# ------------------------------
# Potion unlock state
# ------------------------------
unlocked_potions = set()

def unlock_potion(potion_id: str):
    unlocked_potions.add(potion_id)

def get_unlocked_potions():
    return list(unlocked_potions)

def apply_upgrade_effects(store, paddles: Dict[str, Any], player_wall, castle, dt_ms: int):
    """Apply all active upgrade effects to the game state."""
    
    # Apply passive upgrades
    apply_passive_upgrades(store, paddles, player_wall, castle)
    
    # Update temporary effects
    update_temporary_effects(dt_ms, player_wall)
    
    # Apply emergency healing if needed
    apply_emergency_healing(store, paddles)

def apply_passive_upgrades(store, paddles: Dict[str, Any], player_wall, castle):
    """Apply permanent passive upgrade effects."""
    
    # Giant's Grip - Paddle width upgrades
    if store.has_upgrade('paddle_width'):
        level = store.get_upgrade_level('paddle_width')
        width_bonus = level * 30  # 30 pixels per level
        for paddle in paddles.values():
            # Update base_width to include store upgrades
            paddle.base_width = PADDLE_LEN + width_bonus
            # Update actual_width if no widen potion is active
            if paddle.widen_stack == 0:
                paddle.actual_width = paddle.base_width
                paddle.logical_width = paddle.actual_width
                paddle._start_width_animation(paddle.logical_width)
            else:
                # If widen potion is active, only update actual_width
                # The logical_width will be updated when potion expires
                paddle.actual_width = paddle.base_width
            # Mark that upgrade has been applied
            if not hasattr(paddle, 'upgrade_width_applied'):
                paddle.upgrade_width_applied = True
    
    # Wind Walker's Grace - Paddle agility (reduced inertia)
    if store.has_upgrade('paddle_agility'):
        level = store.get_upgrade_level('paddle_agility')
        for paddle in paddles.values():
            # Store original values if not already stored
            if not hasattr(paddle, 'original_accel'):
                paddle.original_accel = getattr(paddle, 'accel', 0.6)
                paddle.original_max_speed = getattr(paddle, 'max_speed', 10)
            
            # Increase acceleration and max speed
            paddle.accel = paddle.original_accel + (level * 0.2)  # +0.2 per level
            paddle.max_speed = paddle.original_max_speed + (level * 3)  # +3 per level
    
    # Fortune's Favor - Coin boost
    if store.has_upgrade('coin_boost'):
        level = store.get_upgrade_level('coin_boost')
        multiplier = 1.0 + (level * 0.25)  # +25% per level
        coin.set_coin_multiplier(multiplier)
    
    # Lodestone Magnetism (combined tiered upgrade)
    if store.has_upgrade('lodestone_magnetism'):
        level = store.get_upgrade_level('lodestone_magnetism')
        # Level 1 → 1.5, Level 2 → 2.5, Level 3 → 3.5
        strength = 1.5 + (level - 1) * 1.0
        coin.set_magnetism_strength(strength)

def apply_consumable_upgrades(store, upgrade_id: str, paddles: Dict[str, Any], player_wall, castle):
    """Apply consumable upgrade effects immediately when purchased."""
    
    if upgrade_id == 'paddle_heal':
        # Healer's Balm - Restore paddle to full length
        if paddles:
            weakest = min(paddles.values(), key=lambda p: p.logical_width)
            heal_paddle(weakest)
    
    elif upgrade_id == 'wall_repair':
        # Stone Mason's Kit - Repair damaged wall blocks
        repair_wall_blocks(player_wall, 3)  # repair 3 blocks
    
    elif upgrade_id == 'coin_multiplier':
        # Midas Touch - Double coin drops for this wave
        upgrade_states['coin_multiplier_active'] = True
        upgrade_states['coin_multiplier_timer'] = 60000  # 1 minute
        coin.set_coin_multiplier(2.0)
    
    elif upgrade_id == 'time_slow':
        # Chronos Blessing - Slow time for 10 seconds
        upgrade_states['time_slow_active'] = True
        upgrade_states['time_slow_timer'] = 10000
    
    elif upgrade_id == 'lucky_charm':
        # Rabbit's Foot - Increase heart drop chance
        # Set a flag that the heart system can check
        upgrade_states['lucky_charm_active'] = True
        upgrade_states['lucky_charm_timer'] = 30000  # 30 seconds
    
    elif upgrade_id == 'shield_barrier':
        # Arcane Ward - Magical barrier
        upgrade_states['shield_barrier_active'] = True
        upgrade_states['shield_barrier_timer'] = 30000  # 30 seconds
    
    elif upgrade_id == 'block_vision':
        # Oracle's Sight - Reveal weak points (visual effect)
        upgrade_states['block_vision_active'] = True
        upgrade_states['block_vision_timer'] = 45000  # 45 seconds
    
    elif upgrade_id == 'ghost_paddle':
        # Spectral Form - Paddle becomes ethereal
        upgrade_states['ghost_paddle_active'] = True
        upgrade_states['ghost_paddle_timer'] = 15000  # 15 seconds
        for paddle in paddles.values():
            paddle.ghost_mode = True
    
    elif upgrade_id == 'multi_ball':
        # Mirror's Edge - Next shot splits
        upgrade_states['multi_ball_charges'] += 1
    
    elif upgrade_id == 'power_shot':
        # Titan's Might - Next three shots pierce
        upgrade_states['power_shot_charges'] += 3

def apply_single_upgrades(store, upgrade_id: str, paddles: Dict[str, Any], player_wall, castle):
    """Apply single-purchase upgrade effects."""
    
    if upgrade_id == 'repair_drone':
        # Golem Servant - Auto repair drone
        upgrade_states['repair_drone_active'] = True
        upgrade_states['repair_drone_timer'] = upgrade_states['repair_drone_interval']
    
    elif upgrade_id == 'fire_resistance':
        # Wet Paddle Charm - Fire resistance
        for paddle in paddles.values():
            paddle.fire_resistance = True
    
    elif upgrade_id == 'coin_radius':
        # Merchant's Reach - Increase coin collection range
        # This would modify the collision detection range for coins
        coin.set_magnetism_strength(1.5)
    
    elif upgrade_id == 'wave_preview':
        # Strategic Foresight - See preview of next wave
        upgrade_states['wave_preview_active'] = True
    
    elif upgrade_id == 'coin_magnet':
        # Prospector's Dream - Coins drift toward paddle
        coin.set_magnetism_strength(2.0)

    # ---------------- Potion unlocks ----------------
    elif upgrade_id.startswith('potion_'):
        unlock_potion(upgrade_id.split('_',1)[1])

def apply_tiered_upgrades(store, upgrade_id: str, level: int, paddles: Dict[str, Any], player_wall, castle):
    """Apply tiered upgrade effects based on level."""
    
    if upgrade_id == 'extra_life':
        # Phoenix Feather - Extra lives
        upgrade_states['extra_lives'] = level
    
    elif upgrade_id == 'auto_collect':
        # Treasure Hunter's Instinct - Auto collect coins
        upgrade_states['auto_collect_level'] = level
        # Increase coin collection radius based on level
        coin.set_magnetism_strength(1.0 + (level * 0.5))
    
    elif upgrade_id == 'score_bonus':
        # Glory Seeker's Pride - Score bonus
        upgrade_states['score_bonus_level'] = level
    
    elif upgrade_id == 'emergency_heal':
        # Angel's Grace - Auto heal when critical
        upgrade_states['emergency_heal_uses'] = level
    
    elif upgrade_id == 'fortified_walls':
        # Upgrade player wall visual strength based on level (1 or 2)
        upgrade_player_wall_layer(player_wall, level)
    
    elif upgrade_id == 'lodestone_magnetism':
        # Apply magnetism handled in passive upgrades; nothing to do here except maybe update strength immediately
        strength = 1.5 + (level - 1) * 1.0
        coin.set_magnetism_strength(strength)

def update_temporary_effects(dt_ms: int, player_wall):
    """Update temporary upgrade effects and timers."""
    
    # Coin multiplier
    if upgrade_states['coin_multiplier_active']:
        upgrade_states['coin_multiplier_timer'] -= dt_ms
        if upgrade_states['coin_multiplier_timer'] <= 0:
            upgrade_states['coin_multiplier_active'] = False
            coin.set_coin_multiplier(1.0)  # reset to normal
    
    # Time slow
    if upgrade_states['time_slow_active']:
        upgrade_states['time_slow_timer'] -= dt_ms
        if upgrade_states['time_slow_timer'] <= 0:
            upgrade_states['time_slow_active'] = False
    
    # Shield barrier
    if upgrade_states['shield_barrier_active']:
        upgrade_states['shield_barrier_timer'] -= dt_ms
        if upgrade_states['shield_barrier_timer'] <= 0:
            upgrade_states['shield_barrier_active'] = False
    
    # Ghost paddle
    if upgrade_states['ghost_paddle_active']:
        upgrade_states['ghost_paddle_timer'] -= dt_ms
        if upgrade_states['ghost_paddle_timer'] <= 0:
            upgrade_states['ghost_paddle_active'] = False
    
    # Lucky charm
    if upgrade_states.get('lucky_charm_active', False):
        upgrade_states['lucky_charm_timer'] -= dt_ms
        if upgrade_states['lucky_charm_timer'] <= 0:
            upgrade_states['lucky_charm_active'] = False
    
    # Block vision
    if upgrade_states.get('block_vision_active', False):
        upgrade_states['block_vision_timer'] -= dt_ms
        if upgrade_states['block_vision_timer'] <= 0:
            upgrade_states['block_vision_active'] = False
    
    # Repair drone
    if upgrade_states['repair_drone_active']:
        upgrade_states['repair_drone_timer'] -= dt_ms
        if upgrade_states['repair_drone_timer'] <= 0:
            repair_wall_blocks(player_wall, 1)  # repair 1 block
            upgrade_states['repair_drone_timer'] = upgrade_states['repair_drone_interval']

def apply_emergency_healing(store, paddles: Dict[str, Any]):
    """Apply emergency healing when paddles become critical."""
    if upgrade_states['emergency_heal_uses'] <= 0:
        return
    
    for paddle in paddles.values():
        if paddle.logical_width <= 30:  # critical threshold
            heal_paddle(paddle)
            upgrade_states['emergency_heal_uses'] -= 1
            if upgrade_states['emergency_heal_uses'] <= 0:
                break

def heal_paddle(paddle):
    """Restore paddle length."""
    # Restore paddle to its base width (which includes store upgrades)
    paddle.actual_width = paddle.base_width
    # If no widen potion is active, update logical width immediately
    if paddle.widen_stack == 0:
        paddle.logical_width = paddle.actual_width
        paddle._start_width_animation(paddle.logical_width)
    # If widen potion is active, logical width will be updated when potion expires
    
    # Trigger heal pulse visual effect
    paddle.heal_pulse_timer = 30  # 30 frames of pulsing

def repair_wall_blocks(player_wall, count: int):
    """Repair destroyed wall blocks."""
    if not player_wall or not hasattr(player_wall, 'blocks'):
        return
    
    # Find potential repair positions by creating a grid of where blocks should be
    repaired_count = 0
    block_size = player_wall.block_size
    rows = player_wall.rows
    
    # Calculate where blocks should be based on the original wall structure
    start_y = HEIGHT - rows * block_size
    full_cols = math.ceil(WIDTH / block_size)
    
    potential_repairs = []
    
    # Check each potential block position
    for row in range(rows):
        y = start_y + row * block_size
        for col in range(full_cols):
            x = col * block_size
            # Last column might exceed WIDTH – clamp its width to fit onscreen
            w = min(block_size, WIDTH - x)
            if w <= 0:
                continue
                
            potential_rect = pygame.Rect(x, y, w, block_size)
            
            # Check if there's already a block here
            has_block = any(potential_rect.colliderect(existing_block) for existing_block in player_wall.blocks)
            
            if not has_block:
                potential_repairs.append(potential_rect)
    
    # Repair up to 'count' blocks, prioritizing middle positions
    if potential_repairs:
        # Sort by distance from center-bottom (most important positions first)
        center_x = WIDTH // 2
        potential_repairs.sort(key=lambda rect: abs(rect.centerx - center_x) + rect.y)
        
        for i in range(min(count, len(potential_repairs))):
            new_block = potential_repairs[i]
            
            # Determine the target tier based on current wall level
            # Get the current wall tier from the color pair
            current_tier = 1  # Default tier 1
            if hasattr(player_wall, '_color_pair'):
                from config import BLOCK_COLOR_L1, BLOCK_COLOR_L2, BLOCK_COLOR_L3
                if player_wall._color_pair == BLOCK_COLOR_L2:
                    current_tier = 2
                elif player_wall._color_pair == BLOCK_COLOR_L3:
                    current_tier = 3
            
            # For tier 2+ walls, implement tiered rebuilding
            if current_tier >= 2:
                # Start with tier 1 and rebuild up
                key = (new_block.x, new_block.y)
                player_wall.blocks.append(new_block)
                player_wall.block_health[key] = 1
                player_wall.block_colors[key] = BLOCK_COLOR_L1  # Start with tier 1 color
                
                # Add to rebuilding queue for tiered rebuild
                if not hasattr(player_wall, 'rebuilding_blocks'):
                    player_wall.rebuilding_blocks = {}
                
                player_wall.rebuilding_blocks[key] = {
                    'time': pygame.time.get_ticks(),
                    'current_tier': 1,
                    'target_tier': current_tier,
                    'block': new_block
                }
                
                # Start pop animation for this tier
                player_wall.pop_anims.append((new_block.copy(), pygame.time.get_ticks()))
            else:
                # Tier 1 walls rebuild normally
                player_wall.blocks.append(new_block)
                key = (new_block.x, new_block.y)
                player_wall.block_health[key] = 1
                player_wall.block_colors[key] = BLOCK_COLOR_L1
                # Start pop animation
                player_wall.pop_anims.append((new_block.copy(), pygame.time.get_ticks()))
            
            repaired_count += 1

def upgrade_wall_layer(castle, layer: int):
    """Upgrade castle wall to specified layer."""
    if not castle or not hasattr(castle, 'block_health'):
        return
        
    # Upgrade all existing blocks to the specified layer
    for key in list(castle.block_health.keys()):
        tier = layer + 1  # layer 1 = tier 2, etc.
        
        # Set tier
        if not hasattr(castle, 'block_tiers'):
            castle.block_tiers = {}
        castle.block_tiers[key] = tier
        
        # Update color if the method exists
        if hasattr(castle, 'set_block_color_by_strength'):
            castle.set_block_color_by_strength(key, tier)
        
        # Set health based on tier
        if tier == 2:
            castle.block_health[key] = 2
        elif tier == 3:
            castle.block_health[key] = 3
        elif tier == 4:
            castle.block_health[key] = 4
        else:
            castle.block_health[key] = 1

def get_time_scale() -> float:
    """Get current time scale for slow-motion effects."""
    if upgrade_states['time_slow_active']:
        return 0.3  # 30% speed
    return 1.0

def is_barrier_active() -> bool:
    """Check if magical barrier is active."""
    return upgrade_states['shield_barrier_active']

def is_lucky_charm_active() -> bool:
    """Check if lucky charm (increased heart drop chance) is active."""
    return upgrade_states.get('lucky_charm_active', False)

def is_block_vision_active() -> bool:
    """Check if block vision (reveal weak points) is active."""
    return upgrade_states.get('block_vision_active', False)

def has_wave_preview() -> bool:
    """Check if wave preview is available."""
    return upgrade_states.get('wave_preview_active', False)

def get_extra_lives() -> int:
    """Get number of extra lives available."""
    return upgrade_states.get('extra_lives', 0)

def use_extra_life() -> bool:
    """Use an extra life if available."""
    if upgrade_states.get('extra_lives', 0) > 0:
        upgrade_states['extra_lives'] -= 1
        return True
    return False

def get_score_bonus_multiplier() -> float:
    """Get score bonus multiplier."""
    level = upgrade_states.get('score_bonus_level', 0)
    return 1.0 + (level * 0.2)  # +20% per level

def should_apply_multi_ball() -> bool:
    """Check if multi-ball effect should be applied."""
    if upgrade_states['multi_ball_charges'] > 0:
        upgrade_states['multi_ball_charges'] -= 1
        return True
    return False

def should_apply_power_shot() -> bool:
    """Check if power shot effect should be applied."""
    if upgrade_states['power_shot_charges'] > 0:
        upgrade_states['power_shot_charges'] -= 1
        return True
    return False

def reset_upgrade_states():
    """Reset all upgrade states (for game restart)."""
    global upgrade_states
    upgrade_states = {
        'coin_multiplier_active': False,
        'coin_multiplier_timer': 0,
        'time_slow_active': False,
        'time_slow_timer': 0,
        'shield_barrier_active': False,
        'shield_barrier_timer': 0,
        'ghost_paddle_active': False,
        'ghost_paddle_timer': 0,
        'repair_drone_active': False,
        'repair_drone_timer': 0,
        'repair_drone_interval': 5000,
        'emergency_heal_uses': 0,
        'multi_ball_charges': 0,
        'power_shot_charges': 0,
        'lucky_charm_active': False,
        'lucky_charm_timer': 0,
        'block_vision_active': False,
        'block_vision_timer': 0,
        'wave_preview_active': False,
        'extra_lives': 0,
        'auto_collect_level': 0,
        'score_bonus_level': 0,
    }

# ------------------------------------------------------------------
#  New helper – upgrade player wall layer (visual only)
# ------------------------------------------------------------------

def upgrade_player_wall_layer(player_wall, level: int):
    """Upgrade *player_wall* bricks to stronger visuals for *level* (1 or 2)."""
    if not player_wall:
        return
    from config import BLOCK_COLOR_L2, BLOCK_COLOR_L3

    if level == 1:
        player_wall._color_pair = BLOCK_COLOR_L2
        # Set health to 2 for all blocks and update their colors
        for key in player_wall.block_health:
            player_wall.block_health[key] = 2
            player_wall.block_colors[key] = BLOCK_COLOR_L2
    else:
        player_wall._color_pair = BLOCK_COLOR_L3
        for key in player_wall.block_health:
            player_wall.block_health[key] = 3
            player_wall.block_colors[key] = BLOCK_COLOR_L3

    # Clear texture cache so new colour is generated
    if hasattr(player_wall, '_textures'):
        player_wall._textures = {}

    # Potential enhancement: add extra health – currently visual only