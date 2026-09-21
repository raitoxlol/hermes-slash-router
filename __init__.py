"""Hermes Agent entry: Desktop middleware, /route, and failed-slash recovery."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_CLI_PATCHED = False


def _handle_route(raw_args: str) -> str:
    from core.catalogs import load_catalog
    from core.resolve import SlashRouteError, clarification_token, normalize_token, resolve_route
    from core.store import RouteStore

    text = (raw_args or '').strip()
    if not text or text in {'-h', '--help', 'help'}:
        return (
            'Usage: /route <messy-command> [what you meant]\n'
            'Example: /route mdl\n'
            'Teach: /route sm start a new session'
        )
    parts = text.split(None, 1)
    try:
        token = normalize_token(parts[0])
    except SlashRouteError as exc:
        return exc.message
    meaning = parts[1].strip() if len(parts) > 1 else ''
    commands = load_catalog('hermes')
    store = RouteStore()
    identity = store.identity('hermes', commands, token)
    try:
        result = resolve_route(
            clarification_token(meaning, token) if meaning else token,
            commands,
            explanation=meaning,
            prior_route=store.prior_route(identity['key'], commands),
            correction_examples=store.correction_examples(identity['scope'], token, commands),
        )
    except SlashRouteError as exc:
        return exc.message
    if not result.get('target'):
        return (
            f'Unsure what /{token} meant. Reply `/route {token} <what you wanted>` '
            'and Jev will check that explanation against live Hermes commands.'
        )
    if meaning:
        result['origin'] = 'correction'
        result['meaning'] = meaning
    store.remember(identity['key'], token, result)
    reminder = ' Saved as a reminder; Jev still rechecks next time.' if meaning else ''
    return f'/{token} → /{result["target"]} (jev).{reminder} Type the real command to run it.'


def _live_known_tokens() -> set[str]:
    known: set[str] = {'route', 'start'}
    try:
        from hermes_cli.commands import GATEWAY_KNOWN_COMMANDS
        known.update(name.lower() for name in GATEWAY_KNOWN_COMMANDS)
    except Exception:
        pass
    try:
        from hermes_cli.commands import COMMANDS
        known.update(str(name).lower().lstrip('/') for name in COMMANDS)
    except Exception:
        pass
    try:
        from agent.skill_commands import get_skill_commands
        known.update(key.lstrip('/').lower() for key in get_skill_commands())
    except Exception:
        pass
    try:
        from hermes_cli.plugins import get_plugin_commands
        commands = get_plugin_commands()
        if isinstance(commands, dict):
            known.update(str(name).lower().lstrip('/') for name in commands)
    except Exception:
        pass
    expanded = set(known)
    for name in list(known):
        expanded.add(name.replace('-', '_'))
        expanded.add(name.replace('_', '-'))
    return expanded


def _authorized(event, gateway) -> bool:
    source = getattr(event, 'source', None)
    checker = getattr(gateway, '_is_user_authorized_for_source', None) if gateway is not None else None
    if not callable(checker) or source is None:
        return False
    try:
        return bool(checker(source))
    except Exception:
        return False


def on_gateway_dispatch(event=None, gateway=None, session_store=None, **kwargs):
    """Telegram/Discord/etc: if the slash is unknown, Jev may rewrite it to a real command."""
    del session_store, kwargs
    text = getattr(event, 'text', None)
    if not isinstance(text, str) or not text.lstrip().startswith('/'):
        return None
    if not _authorized(event, gateway):
        return None
    from core.recover import recover_unknown_slash
    rewritten = recover_unknown_slash(text, surface='telegram', known=_live_known_tokens())
    if rewritten and rewritten != text:
        return {'action': 'rewrite', 'text': rewritten}
    return None


def _patch_cli_unknown_slashes() -> None:
    """CLI has no rewrite hook; wrap the unknown-command path so Jev runs after prefix match fails."""
    global _CLI_PATCHED
    if _CLI_PATCHED:
        return
    try:
        from cli import HermesCLI
        from hermes_cli.commands import COMMANDS
    except Exception:
        return
    original = HermesCLI._expand_slash_prefix

    def wrapped(self, cmd_original, cmd_lower, skill_commands, skill_bundles):
        typed_base = cmd_lower.split()[0]
        all_known = set(COMMANDS) | set(skill_commands) | set(skill_bundles)
        if not any(item.startswith(typed_base) for item in all_known):
            from core.recover import recover_unknown_slash
            rewritten = recover_unknown_slash(
                cmd_original, surface='hermes',
                known={str(item).lstrip('/') for item in all_known},
            )
            if rewritten:
                return self.process_command(rewritten)
        return original(self, cmd_original, cmd_lower, skill_commands, skill_bundles)


    HermesCLI._expand_slash_prefix = wrapped
    _CLI_PATCHED = True


def register(ctx) -> None:
    ctx.register_command(
        'route',
        handler=_handle_route,
        description='Jev-route a messy slash token to a real Hermes command',
        args_hint='<command> [what you meant]',
    )
    ctx.register_hook('pre_gateway_dispatch', on_gateway_dispatch)
    _patch_cli_unknown_slashes()
