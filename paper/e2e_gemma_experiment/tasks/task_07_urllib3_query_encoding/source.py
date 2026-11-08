def parse_url_query(query: str) -> dict:
    """Parses URL query strings into dictionary."""
    if not query:
        return {}
    params = {}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v.replace("+", " ")
        else:
            params[part] = ""
    return params
