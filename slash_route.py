#!/usr/bin/env python3
"""Route a messy slash token through Jev for Hermes, Telegram, Claude, Codex, or OMP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.catalogs import SURFACES, load_catalog
from core.resolve import SlashRouteError, clarification_token, resolve_route
from core.store import RouteStore


def _print(payload: dict, *, plain: bool) -> int:
    if plain:
        if payload.get('target'):
            print(f"/{payload['token']} → /{payload['target']}")
            return 0
        print(payload.get('ask') or 'Unsure. Describe what you meant.')
        return 2
    print(json.dumps(payload, indent=2))
    return 0 if payload.get('ok') else 2


def _route(args: argparse.Namespace) -> dict:
    commands = load_catalog(args.surface)
    store = RouteStore()
    identity = store.identity(args.surface, commands, args.token)
    prior = store.prior_route(identity['key'], commands)
    examples = store.correction_examples(identity['scope'], args.token, commands)
    explanation = (args.meaning or '').strip()
    token = clarification_token(explanation, args.token) if explanation else args.token
    result = resolve_route(
        token,
        commands,
        explanation=explanation,
        prior_route=prior,
        correction_examples=examples,
    )
    result['surface'] = args.surface
    result['token'] = args.token
    if result.get('target'):
        if explanation:
            result['origin'] = 'correction'
            result['meaning'] = explanation
        store.remember(identity['key'], args.token, result)
        result['ok'] = True
        result['ask'] = None
        return result
    result['ok'] = False
    result['ask'] = 'Unsure. Describe the intended command, then rerun with --meaning.'
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='slash-route', description=__doc__)
    parser.add_argument('--plain', action='store_true', help='Human one-liner instead of JSON')
    sub = parser.add_subparsers(dest='cmd', required=True)

    surfaces = sub.add_parser('surfaces', help='List surfaces')
    catalog = sub.add_parser('catalog', help='Show a surface command catalog')
    catalog.add_argument('--surface', required=True, choices=SURFACES)

    resolve = sub.add_parser('resolve', help='Route a messy token')
    resolve.add_argument('--surface', required=True, choices=SURFACES)
    resolve.add_argument('token')
    resolve.add_argument('--meaning', default='', help='Optional clarification to teach Jev')

    learn = sub.add_parser('learn', help='Resolve using an explicit meaning')
    learn.add_argument('--surface', required=True, choices=SURFACES)
    learn.add_argument('token')
    learn.add_argument('--meaning', required=True)

    args = parser.parse_args(argv)
    try:
        if args.cmd == 'surfaces':
            payload = {'ok': True, 'surfaces': list(SURFACES)}
            return _print(payload, plain=args.plain)
        if args.cmd == 'catalog':
            commands = load_catalog(args.surface)
            payload = {'ok': True, 'surface': args.surface, 'commands': commands, 'count': len(commands)}
            if args.plain:
                for command in commands:
                    print(f"/{command['name']}\t{command['description']}")
                return 0
            return _print(payload, plain=False)
        if args.cmd in {'resolve', 'learn'}:
            from core.resolve import normalize_token
            args.token = normalize_token(args.token)
            if args.cmd == 'learn' and not args.meaning.strip():
                raise SlashRouteError(422, 'Explain the intended action.')
            return _print(_route(args), plain=args.plain)
        raise SlashRouteError(422, 'Unknown command')
    except SlashRouteError as exc:
        payload = {'ok': False, 'error': exc.message, 'code': exc.code}
        return _print(payload, plain=args.plain)
    except ValueError as exc:
        payload = {'ok': False, 'error': str(exc), 'code': 422}
        return _print(payload, plain=args.plain)


if __name__ == '__main__':
    raise SystemExit(main())
