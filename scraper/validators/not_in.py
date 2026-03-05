"""Not-in validation rule - complement to 'in'."""

from typing import Any, List


def validate_not_in(value: Any, options: List[Any]) -> bool:
    """Validate that value is NOT in the list.
    
    Args:
        value: The value to check
        options: List of values that are NOT allowed
        
    Returns:
        True if value is NOT in the options list
    """
    return value not in options


def not_in_rule(value: Any, options: List[Any]) -> tuple[bool, str]:
    """Validation rule for 'not_in'.
    
    Args:
        value: The value to validate
        options: List of disallowed values
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if validate_not_in(value, options):
        return True, ""
    return False, f"Value '{value}' is not allowed. Must not be one of: {options}"
