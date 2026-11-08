def dump_cookie(key: str, value: str) -> str:
    """Serializes cookie key-value pair."""
    # Bug: only quotes when space is present, ignores comma and semicolon
    if " " in value:
        value = f'"{value}"'
    return f"{key}={value}; Path=/"
