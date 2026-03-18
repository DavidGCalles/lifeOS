def build_headers(header_names: list[str], header_contents: list[str]) -> dict[str, str]:
    """
    Builds a dictionary of headers from two lists: header names and header contents.
    Automatically prepends "Bearer " to the content of the "Authorization" header if found.

    Args:
        header_names: A list of header names (e.g., ["Content-Type", "Authorization"]).
        header_contents: A list of header contents (e.g., ["application/json", "<token>"]).

    Returns:
        A dictionary of headers (e.g., {"Content-Type": "application/json", "Authorization": "Bearer <token>"}).

    Raises:
        ValueError: If the lengths of header_names and header_contents do not match.
    """
    if len(header_names) != len(header_contents):
        raise ValueError("The number of header names must match the number of header contents.")

    built_headers = {}
    for i, name in enumerate(header_names):
        content = header_contents[i]
        if name.lower() == "authorization" and not content.lower().startswith("bearer "):
            built_headers[name] = f"Bearer {content}"
        else:
            built_headers[name] = content

    return built_headers
