"""Host entry point for the Desktop plugin's HTTP backend."""


def register(_ctx) -> None:
    """Keep the package loadable without registering agent commands or hooks."""
