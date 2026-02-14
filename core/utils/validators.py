import re

def is_float(value):
    """Checks if a string can be converted to a float."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def validate_dims(text):
    """
    Flexible Dimension Validator.
    Accepts LxWxH with various separators:
    '120x80x100', '120*80*100', '120 80 100', '120-80-100'
    """
    # Split by x, *, space, dash, slash, or comma
    parts = re.split(r'[x*X\s/,-]', text.strip())
    
    # Remove any empty strings (e.g. if user typed '120 * 80 * 100')
    parts = [p for p in parts if p]

    if len(parts) == 3 and all(is_float(p) for p in parts):
        return [float(p) for p in parts]
    
    return None