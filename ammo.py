import pygame
from typing import Dict

# -----------------------------------------------------------------------------
# Ammo System - Manages turret ammunition
# -----------------------------------------------------------------------------

# Global ammo storage
_ammo_count = 0  # General ammo starts at 0
_ammo_types = {
    'basic': 0,     # Basic turret ammo
    'rapid': 0,     # Rapid turret ammo  
    'heavy': 0      # Heavy turret ammo
}
_unlocked_types = set()  # track first-time unlocks

def get_ammo_count() -> int:
    """Get current total ammo count."""
    return _ammo_count

def get_ammo_by_type(ammo_type: str) -> int:
    """Get ammo count for specific turret type."""
    return _ammo_types.get(ammo_type, 0)

def add_ammo(amount: int, ammo_type: str = None):
    """Add ammo to inventory."""
    global _ammo_count, _ammo_types
    
    if ammo_type and ammo_type in _ammo_types:
        # Add specific ammo type
        _ammo_types[ammo_type] += amount
    else:
        # Add general ammo
        _ammo_count += amount

def spend_ammo(amount: int = 1, ammo_type: str = None) -> bool:
    """
    Spend ammo. Returns True if successful.
    
    Args:
        amount: Amount of ammo to spend
        ammo_type: Specific ammo type, or None for general ammo
    """
    global _ammo_count, _ammo_types
    
    if ammo_type and ammo_type in _ammo_types:
        # Try to spend specific ammo first
        if _ammo_types[ammo_type] >= amount:
            _ammo_types[ammo_type] -= amount
            return True
        # Fall back to general ammo
        elif _ammo_count >= amount:
            _ammo_count -= amount
            return True
        else:
            return False
    else:
        # Spend general ammo
        if _ammo_count >= amount:
            _ammo_count -= amount
            return True
        else:
            return False

def reset_ammo():
    """Reset ammo to starting values (for new game)."""
    global _ammo_count, _ammo_types
    _ammo_count = 0
    _ammo_types = {'basic': 0, 'rapid': 0, 'heavy': 0}
    _unlocked_types.clear()

def get_ammo_summary() -> Dict[str, int]:
    """Get summary of all ammo types."""
    return {
        'total': _ammo_count,
        'basic': _ammo_types['basic'],
        'rapid': _ammo_types['rapid'], 
        'heavy': _ammo_types['heavy']
    }

def unlock_type(ammo_type: str):
    """Unlock a turret ammo type and grant starter ammo once."""
    global _unlocked_types
    if ammo_type in _unlocked_types:
        return
    starters = {
        'basic': 10,
        'rapid': 24,
        'heavy': 3,
    }
    amt = starters.get(ammo_type, 0)
    if amt > 0:
        add_ammo(amt, ammo_type)
    _unlocked_types.add(ammo_type)
