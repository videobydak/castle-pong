# Castle Pong - Difficulty Scaling Improvements

## Summary
This document describes the improvements made to the cannon targeting difficulty scaling system in Castle Pong. The changes implement more sophisticated wave-based difficulty progression for cannon behavior.

## Previous Implementation Issues
1. **Fixed Wall Shot Probability**: `WALL_SHOT_PROB = 0.8` was hardcoded to 80%, meaning cannons always favored wall shots over paddle shots regardless of wave level
2. **Edge Bias vs Area Control**: The previous system used "edge bias" that grew per wave, but this controlled whether cannons preferred edge blocks vs center blocks when already targeting the wall, rather than controlling the overall targeting area
3. **No Progressive Paddle Targeting Reduction**: Cannons didn't become progressively less likely to target paddles as waves advanced

## New Implementation

### 1. Dynamic Wall Shot Probability (`get_wall_shot_prob`)
```python
def get_wall_shot_prob(wave_level):
    base_paddle_prob = 0.8  # 80% paddle shots in wave 1
    reduction_factor = 0.9  # 10% relative reduction per wave
    current_paddle_prob = base_paddle_prob * (reduction_factor ** (wave_level - 1))
    current_paddle_prob = max(0.1, current_paddle_prob)  # Minimum 10% paddle targeting
    wall_shot_prob = 1.0 - current_paddle_prob
    return wall_shot_prob
```

**Wave Progression**:
- Wave 1: 20% wall shots, 80% paddle shots
- Wave 2: 28% wall shots, 72% paddle shots  
- Wave 3: 35.2% wall shots, 64.8% paddle shots
- Wave 4: 41.68% wall shots, 58.32% paddle shots
- Wave 10: ~65.13% wall shots, ~34.87% paddle shots

### 2. Dynamic Wall Targeting Area (`get_wall_targeting_area`)
```python
def get_wall_targeting_area(wave_level):
    base_area = 0.4  # 40% of wall width in wave 1
    growth_factor = 1.1  # 10% relative increase per wave
    current_area = base_area * (growth_factor ** (wave_level - 1))
    return min(0.95, current_area)  # Cap at 95%
```

**Wave Progression**:
- Wave 1: 40% of wall width (middle area only)
- Wave 2: 44% of wall width
- Wave 3: 48.4% of wall width  
- Wave 4: 53.24% of wall width
- Wave 10: ~95% of wall width (nearly full wall coverage)

### 3. Implementation Details

The new system replaces the old edge bias logic with area-based targeting:

```python
# Old system (removed):
edge_prob = min(0.95, 0.2 * (1.05 ** (castle.level - 1)))
if edge_blocks and random.random() < edge_prob:
    chosen_block = random.choice(edge_blocks)
else:
    chosen_block = random.choice(centre_blocks if centre_blocks else candidate_blocks)

# New system:
wall_width = max_x - min_x
center_x = (min_x + max_x) / 2
targeting_area = get_wall_targeting_area(castle.level)
targeting_width = wall_width * targeting_area
targeting_min_x = center_x - targeting_width / 2
targeting_max_x = center_x + targeting_width / 2

target_area_blocks = [b for b in candidate_blocks 
                     if targeting_min_x <= b.centerx <= targeting_max_x]
blocks_to_choose_from = target_area_blocks if target_area_blocks else candidate_blocks
chosen_block = random.choice(blocks_to_choose_from)
```

## Difficulty Progression Benefits

1. **Early Game Friendliness**: Wave 1 cannons heavily favor targeting paddles (80%), making the game more accessible for new players
2. **Progressive Challenge**: Each wave increases wall targeting likelihood by 10% relative reduction in paddle preference
3. **Spatial Difficulty**: Wall targeting area grows from 40% to 95%, meaning later waves can target the entire player wall
4. **Balanced Endgame**: Even at high waves, cannons still target paddles ~35% of the time, maintaining tactical variety

## Files Modified

1. **`castle_update.py`**:
   - Added `get_wall_shot_prob()` function
   - Added `get_wall_targeting_area()` function 
   - Replaced fixed `WALL_SHOT_PROB` with dynamic calls
   - Replaced edge bias logic with area-based targeting in two locations

2. **`castle.py`**:
   - Removed hardcoded `WALL_SHOT_PROB` constant
   - Added comment indicating dynamic handling

## Testing Recommendations

1. **Wave 1**: Verify cannons primarily target paddles and only hit middle 40% of wall
2. **Wave 5**: Check that wall shots are more common and cover ~60% of wall width
3. **Wave 10+**: Confirm cannons can target most of the wall but still occasionally target paddles
4. **Edge Cases**: Test behavior when no paddles are present or wall is very narrow

This implementation provides a more nuanced and progressive difficulty curve that makes the game more approachable for beginners while maintaining challenge for experienced players.