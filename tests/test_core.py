import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.catalogs import SURFACES, load_catalog
from core.resolve import SlashRouteError, clarification_token, normalize_token, resolve_route
from core import resolve as core_resolve
from core.store import RouteStore
from slash_route import main


class CoreTest(unittest.TestCase):
    def setUp(self):
        core_resolve._last_call = float('-inf')

    def test_normalize_token(self):
        self.assertEqual(normalize_token('/MDL'), 'mdl')
        with self.assertRaises(SlashRouteError):
            normalize_token('has space')

    def test_clarification_token(self):
        self.assertEqual(clarification_token('Start a new session!', 'sm'), 'start_a_new_session')

    def test_catalogs_load(self):
        for surface in SURFACES:
            commands = load_catalog(surface)
            self.assertTrue(commands)
            self.assertTrue(any(command['name'] == 'route' for command in commands))

    def test_store_keeps_corrections(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RouteStore(Path(tmp) / 'routes.json')
            commands = [{'name': 'model', 'description': 'Select model'}]
            identity = store.identity('claude', commands, 'mdl')
            store.remember(identity['key'], 'mdl', {
                'target': 'model', 'confidence': 0.9, 'source': 'jev', 'origin': 'correction',
                'meaning': 'switch model', 'model': 'jev-1.13.0',
            })
            prior = store.prior_route(identity['key'], commands)
            self.assertEqual(prior['origin'], 'correction')
            examples = store.correction_examples(identity['scope'], 'modle', commands)
            self.assertEqual(examples[0]['token'], 'mdl')

    def test_cli_catalog_and_resolve(self):
        self.assertEqual(main(['surfaces']), 0)
        self.assertEqual(main(['catalog', '--surface', 'omp']), 0)
        reply = {'answers': {'route': {'choice': 'c0', 'confidence': 0.95}}, 'model': 'jev-1.13.0'}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
            code = main(['resolve', '--surface', 'claude', 'mdl'])
        self.assertEqual(code, 0)

    def test_cli_abstains(self):
        reply = {'answers': {'route': {'choice': 'none', 'confidence': 0.4}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
            code = main(['--plain', 'resolve', '--surface', 'codex', 'xyzzy'])
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
