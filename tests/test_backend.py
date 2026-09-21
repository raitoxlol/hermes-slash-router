import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import resolve as core_resolve

spec = importlib.util.spec_from_file_location('plugin_api', ROOT / 'dashboard/plugin_api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class BackendTest(unittest.TestCase):
    def setUp(self):
        core_resolve._last_call = float('-inf')

    def request(self):
        return api.ResolveRequest(token='brainpicker', commands=[{'name': 'model', 'description': 'Select model'}])

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(api.HTTPException) as result:
            api.resolve(self.request())
        self.assertEqual(result.exception.status_code, 503)

    def test_transport_and_threshold(self):
        for confidence, target in [(.95, 'model'), (.85, 'model'), (.84, None)]:
            reply = {'answers': {'route': {'choice': 'c0', 'confidence': confidence}}, 'model': 'jev-1.13.0'}
            with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                    patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
                core_resolve._last_call = float('-inf')
                decision = api.resolve(self.request())
            self.assertEqual(decision['target'], target)
            self.assertEqual(decision['confidence'], confidence)
            self.assertEqual(opened.call_args.kwargs['timeout'], 3)

    def test_prior_route_is_advisory_and_only_current_choices_reach_jev(self):
        body = self.request()
        body.prior_route = api.PriorRoute(target='missing', confidence=0.99, origin='jev')
        reply = {'answers': {'route': {'choice': 'none', 'confidence': 0.9}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
            api.resolve(body)
        payload = json.loads(opened.call_args.args[0].data.decode())
        state = json.loads(payload['state'])
        self.assertIsNone(state['prior_decision'])

    def test_correction_examples_are_bounded_to_relevant_live_choices(self):
        body = self.request()
        body.correction_examples = [
            api.PriorRoute(target='model', confidence=0.9, origin='correction', token='mdl', meaning='switch model'),
            api.PriorRoute(target='missing', confidence=0.9, origin='correction', token='nope', meaning='gone'),
        ]
        reply = {'answers': {'route': {'choice': 'none', 'confidence': 0.9}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
            api.resolve(body)
        payload = json.loads(opened.call_args.args[0].data.decode())
        state = json.loads(payload['state'])
        self.assertEqual(state['correction_examples'][0]['token'], 'mdl')
        instructions = payload['questions']['route']['instructions']
        self.assertIn('new explicit explanation takes priority', instructions)

    def test_invalid_response_and_outage(self):
        for reply in [{}, {'answers': {'route': {'choice': 'c0', 'confidence': 'yes'}}}]:
            with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                    patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())), \
                    self.assertRaises(api.HTTPException) as result:
                core_resolve._last_call = float('-inf')
                api.resolve(self.request())
            self.assertEqual(result.exception.status_code, 502)

    def test_burst_is_rejected_without_network(self):
        core_resolve._last_call = core_resolve.time.monotonic()
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch.object(core_resolve.urllib.request, 'urlopen') as opened, \
                self.assertRaises(api.HTTPException) as result:
            api.resolve(self.request())
        self.assertEqual(result.exception.status_code, 429)
        opened.assert_not_called()

    def test_unknown_choice_abstains(self):
        reply = {'answers': {'route': {'choice': 'not-in-catalog', 'confidence': 1}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
            self.assertIsNone(api.resolve(self.request())['target'])

    def test_clarification_is_sent_to_jev(self):
        body = self.request()
        body.explanation = 'switch the model'
        reply = {'answers': {'route': {'choice': 'c0', 'confidence': 0.9}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), \
                patch.object(core_resolve.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
            api.resolve(body)
        state = json.loads(json.loads(opened.call_args.args[0].data.decode())['state'])
        self.assertEqual(state['user_clarification'], 'switch the model')
        self.assertEqual(state['mistyped_slash_command'], 'brainpicker')

    def test_learning_requires_explanation(self):
        with patch.object(core_resolve.urllib.request, 'urlopen') as opened, self.assertRaises(api.HTTPException) as result:
            api.learn(self.request())
        self.assertEqual(result.exception.status_code, 422)
        opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
