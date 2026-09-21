"""Bundled catalogs plus live scans of local slash/skill folders."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / 'catalogs'
SURFACES = ('hermes', 'telegram', 'claude', 'codex', 'omp')
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.S)


def _bundled(surface: str) -> list[dict[str, str]]:
    alias = 'hermes' if surface == 'telegram' else surface
    path = CATALOG_DIR / f'{alias}.json'
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    return list(data.get('commands') or [])


def _frontmatter_description(text: str, fallback: str) -> str:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return fallback
    lines = match.group(1).splitlines()
    for index, line in enumerate(lines):
        if not line.startswith('description:'):
            continue
        value = line.split(':', 1)[1].strip()
        if value in {'>', '>-', '|', '|-', '+'}:
            parts = []
            for cont in lines[index + 1:]:
                if cont.startswith(' ') or cont.startswith('\t'):
                    parts.append(cont.strip())
                elif not cont.strip():
                    continue
                else:
                    break
            value = ' '.join(parts)
        cleaned = value.strip('"').strip("'").strip()
        return cleaned[:1000] or fallback
    return fallback

def _scan_command_dir(folder: Path) -> list[dict[str, str]]:
    if not folder.is_dir():
        return []
    out: list[dict[str, str]] = []
    for path in sorted(folder.glob('*.md')):
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            continue
        name = path.stem.lower().replace('_', '-')
        out.append({'name': name, 'description': _frontmatter_description(text, name)})
    return out


def _scan_skills(folder: Path) -> list[dict[str, str]]:
    if not folder.is_dir():
        return []
    out: list[dict[str, str]] = []
    for skill_md in sorted(folder.glob('*/SKILL.md')):
        try:
            text = skill_md.read_text(encoding='utf-8')
        except OSError:
            continue
        name = skill_md.parent.name.lower().replace('_', '-')
        out.append({'name': name, 'description': _frontmatter_description(text, name)})
    return out


def _live(surface: str) -> list[dict[str, str]]:
    home = Path.home()
    if surface in {'hermes', 'telegram'}:
        return _scan_skills(home / '.hermes' / 'skills')
    if surface == 'claude':
        return _scan_command_dir(home / '.claude' / 'commands') + _scan_skills(home / '.claude' / 'skills')
    if surface == 'codex':
        return _scan_skills(home / '.agents' / 'skills')
    if surface == 'omp':
        return _scan_skills(home / '.agents' / 'skills')
    return []


def load_catalog(surface: str) -> list[dict[str, str]]:
    surface = surface.strip().lower()
    if surface not in SURFACES:
        raise ValueError(f'Unknown surface {surface!r}. Choose one of: {", ".join(SURFACES)}')
    merged: dict[str, dict[str, str]] = {}
    for command in _bundled(surface) + _live(surface):
        name = str(command.get('name', '')).lstrip('/').lower()
        if not name:
            continue
        merged[name] = {'name': name, 'description': str(command.get('description') or name)[:1000]}
    return sorted(merged.values(), key=lambda item: item['name'])
