def validate_str(value, strip_whitespace: bool = True):
    if strip_whitespace:
        value = value.strip()
    if not isinstance(value, str):
        raise TypeError("Input must be a valid string")
    return value
