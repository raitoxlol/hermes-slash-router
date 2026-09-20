import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('plugin_api', Path(__file__).parents[1] / 'dashboard/plugin_api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class BackendTest(unittest.TestCase):
    def setUp(self):
        api._last_call = float('-inf')

    def request(self):
        return api.ResolveRequest(token='brainpicker', commands=[{'name': 'model', 'description': 'Select model'}])

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(api.HTTPException) as result:
            api.resolve(self.request())
        self.assertEqual(result.exception.status_code, 503)

    def test_transport_and_threshold(self):
        for confidence, target in [(.95, 'model'), (.85, 'model'), (.84, None)]:
            api._last_call = float('-inf')
            reply = {'model': 'jev-1.13.0', 'answers': {'route': {'choice': 'c0', 'confidence': confidence}}}
            with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
                result = api.resolve(self.request())
                self.assertEqual(result['target'], target)
                req = opened.call_args.args[0]
                self.assertEqual(req.full_url, 'https://api.typesafe.ai/v1/systemone')
                self.assertIn('none', json.loads(req.data)['questions']['route']['criteria'])
                self.assertEqual(opened.call_args.kwargs['timeout'], 3)

    def test_prior_route_is_advisory_and_only_current_choices_reach_jev(self):
        body = self.request()
        body.commands.append(api.Command(name='reasoning', description='Thinking effort'))
        body.prior_route = api.PriorRoute(target='model', confidence=.99, origin='jev')
        reply = {'model': 'jev-1.13.0', 'answers': {'route': {'choice': 'c1', 'confidence': .96}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
            result = api.resolve(body)
        request = json.loads(opened.call_args.args[0].data)
        state = json.loads(request['state'])
        self.assertEqual(result['target'], 'reasoning')
        self.assertEqual(state['prior_decision'], {'target': 'model', 'confidence': .99, 'origin': 'jev'})
        self.assertIn('Re-evaluate the current token', request['questions']['route']['instructions'])
        body.prior_route = api.PriorRoute(target='removed', confidence=.99, origin='jev')
        api._last_call = float('-inf')
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
            api.resolve(body)
        state = json.loads(json.loads(opened.call_args.args[0].data)['state'])
        self.assertIsNone(state['prior_decision'])

    def test_correction_examples_are_bounded_to_relevant_live_choices(self):
        body = self.request()
        body.commands.append(api.Command(name='reasoning', description='Thinking effort'))
        body.prior_route = api.PriorRoute(target='model', confidence=.99, origin='correction',
                                          token='brainpicker', meaning='change which model I use')
        body.correction_examples = [
            api.PriorRoute(target='reasoning', confidence=.97, origin='correction',
                           token='thnkin', meaning='change how much the model thinks'),
            api.PriorRoute(target='removed', confidence=.96, origin='correction',
                           token='gone', meaning='select a missing command'),
            api.PriorRoute(target='model', confidence=.95, origin='correction',
                           token='brainpicker', meaning='duplicate of this token'),
            api.PriorRoute(target='model', confidence=.95, origin='jev',
                           token='ordinary', meaning='not a user correction'),
        ]
        reply = {'model': 'jev-1.13.0', 'answers': {'route': {'choice': 'c1', 'confidence': .96}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
            result = api.resolve(body)
        request = json.loads(opened.call_args.args[0].data)
        state = json.loads(request['state'])
        self.assertEqual(result['target'], 'reasoning')
        self.assertEqual(state['prior_decision'], {'target': 'model', 'confidence': .99,
                                                    'origin': 'correction', 'token': 'brainpicker',
                                                    'meaning': 'change which model I use'})
        self.assertEqual(state['correction_examples'], [{'token': 'thnkin', 'target': 'reasoning',
                                                         'meaning': 'change how much the model thinks',
                                                         'confidence': .97, 'origin': 'correction'}])
        instructions = request['questions']['route']['instructions']
        self.assertIn('not aliases or default answers', instructions)
        self.assertIn('new explicit explanation takes priority', instructions)

    def test_invalid_response_and_outage(self):
        for reply in [{}, {'answers': {'route': {'choice': 'c0', 'confidence': 'yes'}}}]:
            api._last_call = float('-inf')
            with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())), self.assertRaises(api.HTTPException) as result:
                api.resolve(self.request())
            self.assertEqual(result.exception.status_code, 502)
        api._last_call = float('-inf')
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', side_effect=TimeoutError), self.assertRaises(api.HTTPException):
            api.resolve(self.request())

    def test_burst_is_rejected_without_network(self):
        api._last_call = api.time.monotonic()
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen') as opened, self.assertRaises(api.HTTPException) as result:
            api.resolve(self.request())
        self.assertEqual(result.exception.status_code, 429)
        opened.assert_not_called()

    def test_unknown_choice_abstains(self):
        reply = {'answers': {'route': {'choice': 'not-in-catalog', 'confidence': 1}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())):
            self.assertIsNone(api.resolve(self.request())['target'])

    def test_clarification_is_sent_to_jev(self):
        body = self.request()
        body.explanation = 'I meant change which AI model I use'
        reply = {'answers': {'route': {'choice': 'c0', 'confidence': .98}}}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(api.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
            self.assertEqual(api.learn(body)['target'], 'model')
            state = json.loads(json.loads(opened.call_args.args[0].data)['state'])
            self.assertEqual(state['user_clarification'], body.explanation)
            self.assertEqual(state['mistyped_slash_command'], 'brainpicker')

    def test_learning_requires_explanation(self):
        with patch.object(api.urllib.request, 'urlopen') as opened, self.assertRaises(api.HTTPException) as result:
            api.learn(self.request())
        self.assertEqual(result.exception.status_code, 422)
        opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
