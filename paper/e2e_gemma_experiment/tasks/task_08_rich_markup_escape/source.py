import re

def escape(text: str) -> str:
    """Escapes markup tags in Rich text."""
    return re.sub(r"\[([a-z]+)\]", r"\[\1\]", text)
