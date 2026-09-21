import importlib.util
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.recover import parse_slash, recover_unknown_slash
import core.resolve as core_resolve
from core.resolve import SlashRouteError

spec = importlib.util.spec_from_file_location('slash_router_plugin', ROOT / '__init__.py')
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class RecoverTest(unittest.TestCase):
    def setUp(self):
        core_resolve._last_call = float('-inf')

    def test_parse_telegram_mention(self):
        self.assertEqual(parse_slash('/mdl@mybot extra')[1], 'mdl')

    def test_skips_known_and_start(self):
        commands = [{'name': 'model', 'description': 'Select model'}]
        self.assertIsNone(recover_unknown_slash('/start', known=set(), commands=commands))
        self.assertIsNone(recover_unknown_slash('/model', known={'model'}, commands=commands))

    def test_rewrites_unknown_when_jev_hits(self):
        commands = [{'name': 'model', 'description': 'Select model'}]

        class FakeStore:
            def identity(self, *args, **kwargs):
                return {'key': 'k', 'scope': 's'}

            def prior_route(self, *args, **kwargs):
                return None

            def correction_examples(self, *args, **kwargs):
                return []

            def remember(self, *args, **kwargs):
                return None

        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch('core.recover.RouteStore', return_value=FakeStore()), \
                patch('core.recover.resolve_route', return_value={
                    'target': 'model', 'confidence': 0.95, 'source': 'jev', 'origin': 'jev',
                }):
            self.assertEqual(
                recover_unknown_slash('/mdl --fast', known={'help'}, commands=commands),
                '/model --fast',
            )


    def test_fail_closed_on_jev_error(self):
        commands = [{'name': 'model', 'description': 'Select model'}]
        with patch('core.recover.resolve_route', side_effect=SlashRouteError(502, 'down')):
            self.assertIsNone(recover_unknown_slash('/mdl', known=set(), commands=commands))

    def test_gateway_hook_rewrites_authorized_unknown(self):
        class Event:
            def __init__(self):
                self.text = '/mdl'
                self.source = object()

        class Gateway:
            def _is_user_authorized_for_source(self, source):
                return True

        with patch('core.recover.recover_unknown_slash', return_value='/model'):
            result = plugin.on_gateway_dispatch(event=Event(), gateway=Gateway())
        self.assertEqual(result, {'action': 'rewrite', 'text': '/model'})

    def test_gateway_hook_skips_unauthorized(self):
        class Event:
            text = '/mdl'
            source = object()

        class Gateway:
            def _is_user_authorized_for_source(self, source):
                return False

        with patch('core.recover.recover_unknown_slash') as recover:
            self.assertIsNone(plugin.on_gateway_dispatch(event=Event(), gateway=Gateway()))
        recover.assert_not_called()


if __name__ == '__main__':
    unittest.main()
