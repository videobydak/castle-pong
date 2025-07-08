# Yellow Potion Bug Fix

## Problem Description

The game was spawning yellow potions when no potions were unlocked in the store. This occurred because:

1. **Potion System**: All 5 potion types (`widen`, `sticky`, `through`, `barrier`, `pierce`) start locked and must be purchased in the store
2. **The Bug**: When `get_random_potion_type()` returned `None` (no unlocked potions), the cannon still created potion balls with `power_type=None`
3. **Yellow Fallback**: The ball drawing code used `POTION_COLORS.get(self.power_type, YELLOW)` which fell back to `YELLOW` when `power_type` was `None`
4. **Unused Color**: `YELLOW` is not assigned to any potion type in `POTION_COLORS`, making it appear as an "unused" color

## Root Cause

The issue was in two places:

1. **Cannon Preview**: `cannon.py` lines 208-209 - Preview showed yellow potions even when none were unlocked
2. **Cannon Spawn**: `cannon.py` lines 272-273 - Actual potion spawning didn't check if potions were unlocked
3. **Castle Logic**: `castle_update.py` lines 515-517 - Castle chose 'power' shot type without checking unlocked potions

## Solution

### 1. Fixed Cannon Preview (cannon.py)
```python
# Before:
ptype = self.preview_power or get_random_potion_type(self._rng)
preview_ball = Ball(draw_origin.x, draw_origin.y, 0, 0, config.YELLOW, True, ptype, spin=0, force_no_spin=True)

# After:
ptype = self.preview_power or get_random_potion_type(self._rng)
if ptype is None:
    # No potions unlocked, fall back to white cannonball
    preview_ball = Ball(draw_origin.x, draw_origin.y, 0, 0, config.WHITE, spin=0, force_no_spin=True)
else:
    preview_ball = Ball(draw_origin.x, draw_origin.y, 0, 0, config.YELLOW, True, ptype, spin=0, force_no_spin=True)
```

### 2. Fixed Cannon Spawn (cannon.py)
```python
# Before:
ptype = self.preview_power or get_random_potion_type(self._rng)
b = Ball(start_pos.x, start_pos.y, vx, vy, config.YELLOW, True, ptype, spin=spin)

# After:
ptype = self.preview_power or get_random_potion_type(self._rng)
if ptype is None:
    # No potions unlocked, fall back to white cannonball
    b = Ball(start_pos.x, start_pos.y, vx, vy, config.WHITE, spin=spin)
else:
    b = Ball(start_pos.x, start_pos.y, vx, vy, config.YELLOW, True, ptype, spin=spin)
```

### 3. Fixed Castle Logic (castle_update.py)
```python
# Before:
elif r < fireball_prob + potion_prob and not castle.potion_reserved:
    chosen_type = 'power'
    castle.potion_reserved = True

# After:
elif r < fireball_prob + potion_prob and not castle.potion_reserved:
    # Check if any potions are unlocked before choosing power type
    from upgrade_effects import get_unlocked_potions
    unlocked_potions = get_unlocked_potions()
    if unlocked_potions:
        chosen_type = 'power'
        castle.potion_reserved = True
    else:
        chosen_type = 'white'
```

## Potion Types and Colors

The game has 5 potion types, all starting locked:

| Potion Type | Color (RGB) | Rarity | Effect |
|-------------|-------------|--------|---------|
| `widen` | (0, 120, 255) - Blue | Common | Enlarges paddle |
| `sticky` | (0, 200, 0) - Green | Common | Balls stick to paddle |
| `through` | (255, 140, 0) - Orange | Uncommon | Converts balls to potions/fireballs |
| `barrier` | (0, 255, 255) - Cyan | Rare | Temporary shield |
| `pierce` | (200, 0, 255) - Purple | Rarest | Balls pass through blocks |

## Verification

- ✅ No yellow potions spawn when no potions are unlocked
- ✅ Preview shows white cannonballs instead of yellow potions
- ✅ Castle logic respects potion unlock status
- ✅ "Through" power-up conversion already had proper checks
- ✅ All potion colors are properly assigned to specific types

## Files Modified

1. `cannon.py` - Fixed preview and spawn logic
2. `castle_update.py` - Fixed castle shot type selection
3. `YELLOW_POTION_BUG_FIX.md` - This documentation file 