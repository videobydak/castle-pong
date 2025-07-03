import random
import pygame
from typing import Dict, Any
from config import PADDLE_LEN, WIDTH, HEIGHT, PADDLE_MARGIN, SCALE
import coin

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
}

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
            if not hasattr(paddle, 'upgrade_width_applied'):
                paddle.base_len = PADDLE_LEN + width_bonus
                paddle.rect.width = paddle.base_len
                paddle.width = paddle.base_len
                paddle.upgrade_width_applied = True
    
    # Wind Walker's Grace - Paddle agility (reduced inertia)
    if store.has_upgrade('paddle_agility'):
        level = store.get_upgrade_level('paddle_agility')
        for paddle in paddles.values():
            # Increase acceleration and max speed
            paddle.accel = 0.6 + (level * 0.2)  # base 0.6, +0.2 per level
            paddle.max_speed = 10 + (level * 3)  # base 10, +3 per level
    
    # Fortune's Favor - Coin boost
    if store.has_upgrade('coin_boost'):
        level = store.get_upgrade_level('coin_boost')
        multiplier = 1.0 + (level * 0.25)  # +25% per level
        coin.set_coin_multiplier(multiplier)
    
    # Lodestone Aura / Prospector's Dream - Magnetism
    if store.has_upgrade('ball_magnetism') or store.has_upgrade('coin_magnet'):
        strength = 2.0 if store.has_upgrade('ball_magnetism') else 1.0
        if store.has_upgrade('coin_magnet'):
            strength += 1.5
        coin.set_magnetism_strength(strength)

def apply_consumable_upgrades(store, upgrade_id: str, paddles: Dict[str, Any], player_wall, castle):
    """Apply consumable upgrade effects immediately when purchased."""
    
    if upgrade_id == 'paddle_heal':
        # Healer's Balm - Restore paddle to full length
        if paddles:
            weakest = min(paddles.values(), key=lambda p: p.width)
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
        # This would need to be implemented in the heart system
        pass
    
    elif upgrade_id == 'shield_barrier':
        # Arcane Ward - Magical barrier
        upgrade_states['shield_barrier_active'] = True
        upgrade_states['shield_barrier_timer'] = 30000  # 30 seconds
    
    elif upgrade_id == 'block_vision':
        # Oracle's Sight - Reveal weak points (visual effect)
        # This would add visual indicators to blocks
        pass
    
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
    
    if upgrade_id == 'wall_layer1':
        # Apprentice Fortification - Upgrade wall to layer 1
        upgrade_wall_layer(castle, 1)
    
    elif upgrade_id == 'wall_layer2':
        # Master Stonework - Upgrade wall to layer 2
        upgrade_wall_layer(castle, 2)
    
    elif upgrade_id == 'wall_layer3':
        # Legendary Masonry - Upgrade wall to layer 3
        upgrade_wall_layer(castle, 3)
    
    elif upgrade_id == 'repair_drone':
        # Golem Servant - Auto repair drone
        upgrade_states['repair_drone_active'] = True
        upgrade_states['repair_drone_timer'] = upgrade_states['repair_drone_interval']
    
    elif upgrade_id == 'fire_resistance':
        # Wet Paddle Charm - Fire resistance
        for paddle in paddles.values():
            paddle.fire_resistance = True

def apply_tiered_upgrades(store, upgrade_id: str, level: int, paddles: Dict[str, Any], player_wall, castle):
    """Apply tiered upgrade effects based on level."""
    
    if upgrade_id == 'extra_life':
        # Phoenix Feather - Extra lives
        # This would be handled in the game over logic
        pass
    
    elif upgrade_id == 'auto_collect':
        # Treasure Hunter's Instinct - Auto collect coins
        # This would modify coin collection radius
        pass
    
    elif upgrade_id == 'score_bonus':
        # Glory Seeker's Pride - Score bonus
        # This would modify score calculations
        pass
    
    elif upgrade_id == 'emergency_heal':
        # Angel's Grace - Auto heal when critical
        upgrade_states['emergency_heal_uses'] = level

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
        if paddle.width <= 30:  # critical threshold
            heal_paddle(paddle)
            upgrade_states['emergency_heal_uses'] -= 1
            if upgrade_states['emergency_heal_uses'] <= 0:
                break

def heal_paddle(paddle):
    """Restore paddle length."""
    new_len = min(PADDLE_LEN, int(paddle.width * 1.5))
    if new_len <= paddle.width:
        return
    
    if paddle.side in ("top", "bottom"):
        centre = paddle.rect.centerx
        paddle.rect.width = new_len
        paddle.rect.x = max(PADDLE_MARGIN, min(WIDTH - new_len - PADDLE_MARGIN, centre - new_len // 2))
    else:
        centre = paddle.rect.centery
        paddle.rect.height = new_len
        paddle.rect.y = max(PADDLE_MARGIN, min(HEIGHT - new_len - PADDLE_MARGIN, centre - new_len // 2))
    
    paddle.width = new_len

def repair_wall_blocks(player_wall, count: int):
    """Repair destroyed wall blocks."""
    # This would need to be implemented based on how the player wall tracks damage
    # For now, this is a placeholder
    pass

def upgrade_wall_layer(castle, layer: int):
    """Upgrade castle wall to specified layer."""
    # Upgrade all existing blocks to the specified layer
    for key in castle.block_health.keys():
        tier = layer + 1  # layer 1 = tier 2, etc.
        castle.block_tiers[key] = tier
        castle.set_block_color_by_strength(key, tier)
        # Set health based on tier
        extra = 0 if tier == 2 else (1 if tier == 3 else 2)
        castle.block_health[key] = 1 + extra

def get_time_scale() -> float:
    """Get current time scale for slow-motion effects."""
    if upgrade_states['time_slow_active']:
        return 0.3  # 30% speed
    return 1.0

def is_barrier_active() -> bool:
    """Check if magical barrier is active."""
    return upgrade_states['shield_barrier_active']

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
    }