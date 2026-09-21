"""If a slash is unknown to the host, ask Jev; rewrite only on a confident live hit."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from .catalogs import load_catalog
from .resolve import SlashRouteError, normalize_token, resolve_route
from .store import RouteStore

SLASH_RE = re.compile(r'^(\s*)/([\w:-]+)(?:@[\w]+)?(?=\s|$)([\s\S]*)$')
SKIP_TOKENS = frozenset({'start', 'route'})


def parse_slash(text: str) -> Optional[tuple[str, str, str]]:
    match = SLASH_RE.match(text or '')
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def _aliases(token: str) -> set[str]:
    token = token.lower().lstrip('/')
    return {token, token.replace('_', '-'), token.replace('-', '_')}


def is_known(token: str, known: Iterable[str]) -> bool:
    catalog = {item.lower().lstrip('/') for item in known}
    return bool(_aliases(token) & catalog)


def recover_unknown_slash(
    text: str,
    *,
    surface: str = 'hermes',
    known: Optional[Iterable[str]] = None,
    commands: Optional[list[dict[str, str]]] = None,
) -> Optional[str]:
    """Return rewritten `/{target}{args}` when Jev maps an unknown slash; else None."""
    parsed = parse_slash(text)
    if parsed is None:
        return None
    prefix, raw_token, rest = parsed
    try:
        token = normalize_token(raw_token)
    except SlashRouteError:
        return None
    if token in SKIP_TOKENS or is_known(token, known or ()):
        return None
    commands = list(commands) if commands is not None else load_catalog(surface)
    store = RouteStore()
    identity = store.identity(surface, commands, token)
    try:
        result = resolve_route(
            token,
            commands,
            prior_route=store.prior_route(identity['key'], commands),
            correction_examples=store.correction_examples(identity['scope'], token, commands),
        )
    except SlashRouteError:
        return None
    target = result.get('target')
    if not target or target == token:
        return None
    store.remember(identity['key'], token, result)
    return f'{prefix}/{target}{rest}'
