#!/usr/bin/env python3
"""Claude Code UserPromptSubmit: if a slash is unknown, Jev rewrites it before dispatch."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SLASH = re.compile(r'^(\s*)/([\w:-]+)(?=\s|$)([\s\S]*)$')
SKIP = {
    'help', 'compact', 'clear', 'model', 'permissions', 'mcp', 'memory', 'init',
    'review', 'doctor', 'login', 'logout', 'theme', 'vim', 'cost', 'usage',
    'resume', 'rewind', 'export', 'config', 'hooks', 'skills', 'agents', 'status',
    'bug', 'feedback', 'context', 'plan', 'task', 'terminal', 'add-dir',
    'security-review', 'pr-comments', 'release-notes', 'route', 'start', 'skill',
    'plugin', 'plugins', 'reload', 'diff', 'undo', 'commit', 'pr', 'issue',
}

def _prompt(event: dict) -> str:
    for key in ('prompt', 'user_prompt', 'text', 'input'):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ''


def main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0
    if not isinstance(event, dict):
        return 0
    text = _prompt(event)
    match = SLASH.match(text)
    if not match:
        return 0
    token = match.group(2).lower()
    if token in SKIP or token.replace('_', '-') in SKIP:
        return 0
    env = os.environ.copy()
    if not env.get('TYPESAFE_API_KEY'):
        for path in (
            Path(os.environ.get('HERMES_HOME', '')) / '.env' if os.environ.get('HERMES_HOME') else None,
            Path.home() / '.hermes' / 'profiles' / 'max' / '.env',
            Path.home() / '.hermes' / '.env',
        ):
            if path is None or not path.is_file():
                continue
            try:
                for line in path.read_text(encoding='utf-8').splitlines():
                    line = line.strip()
                    if line.startswith('export '):
                        line = line[7:]
                    if not line.startswith('TYPESAFE_API_KEY='):
                        continue
                    value = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if value:
                        env['TYPESAFE_API_KEY'] = value
                        break
            except OSError:
                continue
            if env.get('TYPESAFE_API_KEY'):
                break
    if not env.get('TYPESAFE_API_KEY'):
        return 0
    binary = shutil.which('slash-route') or str(Path.home() / '.local' / 'bin' / 'slash-route')
    try:
        result = subprocess.run(
            [binary, 'resolve', '--surface', 'claude', token],
            capture_output=True, text=True, timeout=8, env=env,
        )
        payload = json.loads(result.stdout or '{}')
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return 0
    target = payload.get('target')
    if not payload.get('ok') or not isinstance(target, str) or target == token:
        return 0
    rewritten = f'{match.group(1)}/{target}{match.group(3)}'
    json.dump({
        'updatedInput': rewritten,
        'hookSpecificOutput': {
            'hookEventName': 'UserPromptSubmit',
            'updatedInput': rewritten,
        },
    }, sys.stdout, ensure_ascii=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
