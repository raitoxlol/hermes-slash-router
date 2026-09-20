"""Hermes Agent entry point for the desktop slash router.

The desktop half owns the user-facing behavior. Hermes mounts its companion
HTTP routes from dashboard/plugin_api.py when this package is enabled.
"""


def register(ctx) -> None:
    """Register the native package; this plugin contributes through Desktop."""
    del ctx  # The desktop contribution and namespaced API are registered separately.
