"""Advisory route reminders. Never applied automatically."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def default_path() -> Path:
    return Path.home() / '.local' / 'share' / 'slash-route' / 'routes.json'


class RouteStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else default_path()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {'routes': {}, 'history': []}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {'routes': {}, 'history': []}
        routes = data.get('routes') if isinstance(data.get('routes'), dict) else {}
        history = data.get('history') if isinstance(data.get('history'), list) else []
        return {'routes': routes, 'history': history}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
        tmp.replace(self.path)

    @staticmethod
    def identity(surface: str, commands: list[dict[str, str]], token: str) -> dict[str, str]:
        names = sorted(command['name'] for command in commands)
        digest = hashlib.sha256(json.dumps(names, separators=(',', ':')).encode()).hexdigest()
        return {
            'key': json.dumps([surface, digest, token], separators=(',', ':')),
            'scope': json.dumps([surface, digest], separators=(',', ':')),
        }

    def remember(self, key: str, token: str, route: dict[str, Any]) -> None:
        data = self._load()
        record = {
            'input': token,
            'target': route['target'],
            'source': route.get('source', 'jev'),
            'origin': route.get('origin') or route.get('source', 'jev'),
            'confidence': route['confidence'],
            'model': route.get('model'),
            'at': datetime.now(timezone.utc).isoformat(),
        }
        if record['origin'] == 'correction' and isinstance(route.get('meaning'), str) and route['meaning'].strip():
            record['meaning'] = route['meaning'].strip()[:500]
        saved = data['routes']
        existing = saved.get(key) or {}
        next_routes = {k: v for k, v in saved.items() if k != key}
        if existing.get('origin') == 'correction' and record['origin'] != 'correction':
            next_routes[key] = existing
        else:
            next_routes[key] = record
        if len(next_routes) > 500:
            keep = list(next_routes.items())[-500:]
            next_routes = dict(keep)
        data['routes'] = next_routes
        data['history'] = (data['history'] + [{
            'input': token,
            'target': record['target'],
            'origin': record['origin'],
            'at': record['at'],
        }])[-200:]
        self._save(data)

    def prior_route(self, key: str, commands: list[dict[str, str]]) -> Optional[dict[str, Any]]:
        available = {command['name'] for command in commands}
        record = self._load()['routes'].get(key)
        if not isinstance(record, dict) or record.get('target') not in available:
            return None
        return record

    def correction_examples(self, scope: str, token: str, commands: list[dict[str, str]]) -> list[dict[str, Any]]:
        available = {command['name'] for command in commands}
        try:
            scope_parts = json.loads(scope)
        except json.JSONDecodeError:
            return []
        examples: list[dict[str, Any]] = []
        for key, record in reversed(list(self._load()['routes'].items())):
            if not isinstance(record, dict) or record.get('origin') != 'correction':
                continue
            try:
                key_parts = json.loads(key)
            except json.JSONDecodeError:
                continue
            if key_parts[:2] != scope_parts:
                continue
            example_token = record.get('input')
            if example_token == token or record.get('target') not in available:
                continue
            if not record.get('meaning'):
                continue
            examples.append({
                'token': example_token,
                'target': record['target'],
                'meaning': record['meaning'],
                'confidence': record.get('confidence', 0.85),
                'origin': 'correction',
            })
            if len(examples) >= 8:
                break
        return examples
