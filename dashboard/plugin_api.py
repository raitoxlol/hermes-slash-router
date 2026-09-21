"""Jev transport. Credentials stay in the gateway process; no generated commands."""
import sys
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.resolve import MIN_CONFIDENCE, SlashRouteError, resolve_route

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


@router.get('/status')
def status():
    import os
    return {'configured': bool(os.environ.get('TYPESAFE_API_KEY')), 'model': 'jev-1.13.0'}


@router.post('/resolve')
def resolve(body: ResolveRequest):
    return _call(body)


@router.post('/learn')
def learn(body: ResolveRequest):
    if not body.explanation.strip():
        raise HTTPException(422, 'Explain the intended action.')
    return resolve(body)
