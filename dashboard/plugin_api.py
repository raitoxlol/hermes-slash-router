"""Jev transport. Credentials stay in the gateway process; no generated commands."""
import importlib.util
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Load our own module by path under a plugin-prefixed name rather than putting the
# plugin root on sys.path: the gateway's import namespace is shared with every other
# plugin and site-package, so an unprefixed `core` there collides silently.
_spec = importlib.util.spec_from_file_location(
    'hermes_slash_router_core.resolve',
    Path(__file__).resolve().parents[1] / 'slash_router_core' / 'resolve.py',
)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
MIN_CONFIDENCE, SlashRouteError, resolve_route = _core.MIN_CONFIDENCE, _core.SlashRouteError, _core.resolve_route

router = APIRouter()


class Command(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[\w:-]+$")
    description: str = Field(max_length=1000)


class PriorRoute(BaseModel):
    target: str = Field(min_length=1, max_length=100, pattern=r"^[\w:-]+$")
    confidence: float = Field(ge=MIN_CONFIDENCE, le=1)
    origin: Literal['jev', 'correction']
    token: Optional[str] = Field(default=None, min_length=1, max_length=64, pattern=r"^[\w:-]+$")
    meaning: Optional[str] = Field(default=None, max_length=500)


class ResolveRequest(BaseModel):
    token: str = Field(min_length=1, max_length=64, pattern=r"^[\w:-]+$")
    commands: list[Command] = Field(min_length=1, max_length=1000)
    explanation: str = Field(default='', max_length=500)
    prior_route: Optional[PriorRoute] = None
    correction_examples: list[PriorRoute] = Field(default_factory=list, max_length=8)


def _call(body: ResolveRequest):
    try:
        result = resolve_route(
            body.token,
            [command.model_dump() for command in body.commands],
            explanation=body.explanation,
            prior_route=body.prior_route.model_dump() if body.prior_route else None,
            correction_examples=[example.model_dump() for example in body.correction_examples],
        )
    except SlashRouteError as exc:
        raise HTTPException(exc.code, exc.message) from exc
    return {
        'target': result['target'],
        'confidence': result['confidence'],
        'source': result['source'],
        'model': result.get('model'),
    }


def _key_saved() -> bool:
    """Check only the active profile's saved key; never return its value."""
    import os
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        # Standalone backend tests do not install the Hermes host.
        home = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    else:
        home = get_hermes_home()
    try:
        lines = (home / '.env').read_text(encoding='utf-8').splitlines()
    except OSError:
        return False
    for line in lines:
        line = line.strip().removeprefix('export ')
        if line.startswith('TYPESAFE_API_KEY=') and line.split('=', 1)[1].strip().strip('"\''):
            return True
    return False


@router.get('/status')
def status():
    import os
    configured = bool(os.environ.get('TYPESAFE_API_KEY'))
    # loaded: usable now. saved: in .env but this process started without it. missing: nowhere.
    key = 'loaded' if configured else 'saved' if _key_saved() else 'missing'
    return {'configured': configured, 'key': key, 'model': 'jev-1.13.0'}


@router.post('/resolve')
def resolve(body: ResolveRequest):
    return _call(body)


@router.post('/learn')
def learn(body: ResolveRequest):
    if not body.explanation.strip():
        raise HTTPException(422, 'Explain the intended action.')
    return resolve(body)
