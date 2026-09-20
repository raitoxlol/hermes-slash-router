import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'
const source = (await readFile(new URL('../desktop/plugin.js', import.meta.url), 'utf8')).replace(/^import .*\n/gm, '')
const { createHandler, default: desktopPlugin } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
const catalog = { pairs: [['/model', 'Select model'], ['/reasoning', 'Thinking effort'], ['/help', 'Help']], canon: { '/model': '/model', '/reasoning': '/reasoning', '/help': '/help' } }
function setup(cat = catalog, response = { target: 'model', confidence: .99, source: 'jev' }) {
  const storage = new Map(), calls = [], notices = [], prompts = []
  let profile = 'max'
  const ctx = { storage: { get: (k, fallback) => storage.get(k) ?? fallback, set: (k, v) => storage.set(k, v) }, rest: async (...args) => { calls.push(args); if (typeof response === 'function') return response(...args); if (response instanceof Error) throw response; return response } }
  const api = { state: { profile: { get: () => profile } }, request: async () => cat, notify: n => notices.push(n) }
  return { handler: createHandler(ctx, api, p => prompts.push(p)), ctx, api, calls, storage, notices, prompts, setProfile: p => { profile = p } }
}
test('Jev resolves a transposed typo and preserves arguments, spacing and attachments', async () => {
  const s = setup(), attachments = [{ id: 'x' }]
  const out = await s.handler({ text: ' /modle  provider/model\n', attachments })
  assert.equal(out.text, ' /model  provider/model\n'); assert.equal(out.attachments, attachments)
  assert.equal(s.calls.length, 1)
  assert.equal(s.calls[0][1].body.token, 'modle')
})
test('desktop plugin remains opt-in until the user enables it', () => {
  assert.equal(desktopPlugin.defaultEnabled, false)
})
test('Jev interprets reasoning and effort in either catalog direction', async () => {
  const forward = setup(catalog, () => ({ target: 'reasoning', confidence: .99 }))
  assert.equal((await forward.handler({ text: '/effort high' })).text, '/reasoning high')
  assert.equal(forward.calls[0][1].body.token, 'effort')
  const reverseCatalog = { pairs: [['/effort', 'Thinking effort']], canon: { '/effort': '/effort' } }
  const reverse = setup(reverseCatalog, () => ({ target: 'effort', confidence: .99 }))
  assert.equal((await reverse.handler({ text: '/reasoning low' })).text, '/effort low')
  assert.equal(reverse.calls[0][1].body.token, 'reasoning')
  const typo = setup(catalog, () => ({ target: 'reasoning', confidence: .99 }))
  assert.equal((await typo.handler({ text: '/effrot high' })).text, '/reasoning high')
  assert.equal(typo.calls[0][1].body.token, 'effrot')
})
test('real commands, native aliases and prose bypass routing', async () => {
  const s = setup({ ...catalog, canon: { ...catalog.canon, '/effort': '/reasoning' } })
  for (const text of ['/model gpt', '/effort high', 'hello /modle', '//comment']) assert.equal((await s.handler({ text })).text, text)
  assert.equal(s.calls.length, 0)
})
test('a saved Jev choice is only a reminder; every lookup gets a fresh decision', async () => {
  let response = { target: 'model', confidence: .99, source: 'jev' }
  const s = setup(catalog, () => response)
  assert.equal((await s.handler({ text: '/brainpicker secret-argument' })).text, '/model secret-argument')
  assert.equal(s.calls[0][1].body.token, 'brainpicker')
  assert.ok(!JSON.stringify(s.calls).includes('secret-argument'))
  const again = createHandler(s.ctx, s.api)
  response = { target: 'reasoning', confidence: .96, source: 'jev' }
  assert.equal((await again({ text: '/brainpicker other' })).text, '/reasoning other')
  assert.equal(s.calls.length, 2)
  assert.deepEqual(s.calls[1][1].body.prior_route, { target: 'model', confidence: .99, origin: 'jev' })
  assert.ok(!JSON.stringify([...s.storage]).includes('secret-argument'))
  assert.equal(s.storage.get('history').at(-1).source, 'jev')
})
test('a saved Jev choice is not used when the fresh check abstains', async () => {
  let response = { target: 'model', confidence: .99, source: 'jev' }
  const s = setup(catalog, () => response)
  assert.equal((await s.handler({ text: '/mdl' })).text, '/model')
  response = { target: null, confidence: .5 }
  assert.equal(await s.handler({ text: '/mdl' }), null)
  assert.equal(s.calls.length, 2)
  assert.deepEqual(s.calls[1][1].body.prior_route, { target: 'model', confidence: .99, origin: 'jev' })
  assert.equal(s.prompts.at(-1).token, 'mdl')
})
test('profile and catalog changes invalidate learned mappings', async () => {
  const cat = structuredClone(catalog), s = setup(cat)
  await s.handler({ text: '/brainpicker' }); s.setProfile('other'); await s.handler({ text: '/brainpicker' })
  cat.pairs.push(['/new', 'New session']); await s.handler({ text: '/brainpicker' })
  assert.equal(s.calls.length, 3)
})
test('low confidence, missing/unknown choices, malformed answers and outages preserve draft', async () => {
  for (const response of [{ target: 'model', confidence: .84 }, { target: 'delete', confidence: 1 }, { target: null, confidence: 1 }, { target: 'model' }, new Error('offline')]) {
    const s = setup(catalog, response)
    assert.equal(await s.handler({ text: '/somethingelse' }), null)
    assert.equal(s.storage.size, 0)
  }
})
test('Jev selection at the 0.85 confidence floor is accepted', async () => {
  const s = setup(catalog, { target: 'model', confidence: .85 })
  assert.equal((await s.handler({ text: '/mdl' })).text, '/model')
})
test('unavailable desktop commands cannot be selected', async () => {
  const s = setup({ pairs: [['/clear', 'Clear screen']], commands: { '/clear': { desktop: 'terminal' } } })
  assert.equal(await s.handler({ text: '/claer' }), null)
  assert.equal(s.calls.length, 0)
})

test('typos, consonant shortcuts, semantic tokens and absent names all go to Jev', async () => {
  const cat = { ...catalog, pairs: [...catalog.pairs, ['/worktree', 'Create or switch worktree'], ['/new', 'Start a new session']] }
  const targets = { mdl: 'model', modle: 'model', thnkin: 'reasoning', wktr: 'worktree', effort: 'reasoning', newsession: 'new' }
  const s = setup(cat, (_path, opts) => ({ target: targets[opts.body.token], confidence: .98 }))
  const cases = [
    ['/mdl gpt', '/model gpt'], ['/modle gpt', '/model gpt'], ['/thnkin high', '/reasoning high'],
    ['/wktr. new', '/worktree new'], ['/effort medium', '/reasoning medium'], ['/newsession', '/new']
  ]
  for (const [input, expected] of cases) assert.equal((await s.handler({ text: input })).text, expected)
  assert.deepEqual(s.calls.map(([, options]) => options.body.token), Object.keys(targets))
  assert.ok(s.calls.every(([, options]) => options.body.commands.some(command => command.name === 'worktree')))
})
test('old local guesses are not treated as Jev memory', async () => {
  const s = setup()
  assert.equal((await s.handler({ text: '/mdl' })).text, '/model')
  const routes = s.storage.get('routes')
  const key = Object.keys(routes)[0]
  routes[key] = { ...routes[key], target: 'reasoning', source: 'abbreviation', origin: undefined }
  s.storage.set('routes', routes)
  const again = createHandler(s.ctx, s.api)
  assert.equal((await again({ text: '/mdl' })).text, '/model')
  assert.equal(s.calls.length, 2)
  assert.equal(s.calls[1][1].body.prior_route, null)
})
test('plain-text explanation goes to Jev, learns, and preserves original arguments on resend', async () => {
  let lookups = 0
  const s = setup(catalog, (_path, opts) => opts.body.explanation
    ? { target: 'model', confidence: .97, source: 'jev' }
    : ++lookups === 1 ? { target: null, confidence: .5 } : { target: 'model', confidence: .97, source: 'jev' })
  assert.equal(await s.handler({ text: '/brn secret-argument' }), null)
  const prompt = s.prompts.at(-1)
  assert.equal(prompt.token, 'brn')
  assert.deepEqual(await prompt.teach('I meant change which AI model is used'), { ok: true })
  assert.equal(s.calls[1][0], '/resolve')
  assert.equal(s.calls[1][1].body.token, 'i_meant_change_which_ai_model_is_used')
  assert.equal(s.calls[1][1].body.explanation, 'I meant change which AI model is used')
  assert.equal((await s.handler({ text: '/brn secret-argument' })).text, '/model secret-argument')
  assert.equal(s.calls.length, 3)
  assert.deepEqual(s.calls[2][1].body.prior_route, {
    target: 'model', confidence: .97, origin: 'correction', token: 'brn',
    meaning: 'I meant change which AI model is used'
  })
  assert.deepEqual(s.calls[2][1].body.correction_examples, [])
  const persisted = JSON.stringify([...s.storage])
  assert.ok(!persisted.includes('secret-argument'))
  assert.ok(persisted.includes('I meant change which AI model is used'))
  assert.ok(!JSON.stringify(s.storage.get('history')).includes('I meant change'))
})
test('a taught meaning helps Jev interpret related spellings without reusing its answer', async () => {
  const cat = { ...catalog, pairs: [...catalog.pairs, ['/new', 'Start a new session']],
    canon: { ...catalog.canon, '/new': '/new' } }
  let firstSm = true, jevChoice = 'new'
  const s = setup(cat, (_path, { body }) => body.explanation
    ? { target: 'new', confidence: .98 }
    : body.token === 'sm' && firstSm
      ? (firstSm = false, { target: null, confidence: .5 })
      : { target: jevChoice, confidence: .97 })

  assert.equal(await s.handler({ text: '/sm' }), null)
  assert.deepEqual(await s.prompts.at(-1).teach('start a new session'), { ok: true })
  const route = Object.values(s.storage.get('routes')).find(item => item.origin === 'correction')
  assert.deepEqual({ input: route.input, target: route.target, meaning: route.meaning },
    { input: 'sm', target: 'new', meaning: 'start a new session' })
  assert.ok(!JSON.stringify(s.storage.get('history')).includes('start a new session'))

  jevChoice = 'model'
  assert.equal((await s.handler({ text: '/sm' })).text, '/model')
  assert.equal(s.calls.at(-1)[1].body.prior_route.target, 'new')
  assert.equal(Object.values(s.storage.get('routes')).find(item => item.origin === 'correction').target, 'new')

  jevChoice = 'new'
  assert.equal((await s.handler({ text: '/now' })).text, '/new')
  const nowRequest = s.calls.at(-1)[1].body
  assert.equal(nowRequest.token, 'now')
  assert.equal(nowRequest.prior_route, null)
  assert.deepEqual(nowRequest.correction_examples, [{ token: 'sm', target: 'new',
    meaning: 'start a new session', confidence: .98, origin: 'correction' }])

  assert.equal((await s.handler({ text: '/nwe' })).text, '/new')
  const nweRequest = s.calls.at(-1)[1].body
  assert.equal(nweRequest.token, 'nwe')
  assert.equal(nweRequest.prior_route, null)
  assert.deepEqual(nweRequest.correction_examples, nowRequest.correction_examples)
  assert.equal(s.calls.length, 5)
})
test('correction examples stay within their profile and catalog', async () => {
  const cat = { ...catalog, pairs: [...catalog.pairs, ['/new', 'Start a new session']] }
  const s = setup(cat, (_path, { body }) => body.explanation
    ? { target: 'new', confidence: .98 }
    : body.token === 'sm' ? { target: null, confidence: .5 }
      : { target: 'new', confidence: .97 })
  await s.handler({ text: '/sm' })
  assert.deepEqual(await s.prompts.at(-1).teach('start a new session'), { ok: true })

  s.setProfile('other')
  assert.equal((await s.handler({ text: '/nwe' })).text, '/new')
  assert.deepEqual(s.calls.at(-1)[1].body.correction_examples, [])
  s.setProfile('max')
  cat.pairs.push(['/extra', 'Another command'])
  assert.equal((await s.handler({ text: '/nwe' })).text, '/new')
  assert.deepEqual(s.calls.at(-1)[1].body.correction_examples, [])
})
test('unsure or invalid explanations never poison memory', async () => {
  for (const answer of [{target:null, confidence:.99}, {target:'model', confidence:.4}, {target:'not-a-command',confidence:1}]) {
    const s = setup(catalog, answer)
    await s.handler({text:'/xyzzy'})
    assert.equal((await s.prompts.at(-1).teach('something')).ok, false)
    assert.equal(s.storage.size, 0)
  }
})
test('unavailable learning backend reports a retry and preserves correction', async () => {
  const s = setup(catalog, new Error('offline'))
  await s.handler({ text: '/xyzzy' })
  const result = await s.prompts.at(-1).teach('change the model')
  assert.equal(result.ok, false)
  assert.match(result.message, /try again/)
  assert.equal(s.storage.size, 0)
})
test('stale explanation cannot save across profile changes or catalog removal', async () => {
  const cat = structuredClone(catalog)
  const s = setup(cat, (_path, opts) => opts.body.explanation ? {target:'model',confidence:1} : {target:null,confidence:1})
  await s.handler({ text: '/xyzzy' })
  const old = s.prompts.at(-1); s.setProfile('other')
  assert.equal((await old.teach('change model')).ok, false)
  await s.handler({ text: '/xyzzy' }); const next = s.prompts.at(-1)
  cat.pairs = cat.pairs.filter(([name]) => name !== '/model')
  assert.equal((await next.teach('change model')).ok, false)
  assert.equal(s.storage.size, 0)
})
test('blank explanations make no request', async () => {
  const s = setup(catalog, { target:null,confidence:1 })
  await s.handler({text:'/xyzzy'})
  assert.equal((await s.prompts.at(-1).teach('   ')).ok,false)
  assert.equal(s.calls.length,1)
})
test('bottom prompt has a free-text answer without a command approval list', async () => {
  const sdk = `
    const atom = value => ({get: () => value, set: next => { value = next }});
    const useValue = a => a.get();
    const jsx = (type, props, key) => ({type, props, key}), jsxs = jsx;
    const Button = 'button', Input = 'input';
    const host = {state: {profile: atom('max'), focusedSessionProfile: atom(''), focusedSessionId: atom(null), activeSessionId: atom('session-a')}};
  `
  const ui = await import(`data:text/javascript;base64,${Buffer.from(sdk + source).toString('base64')}`)
  let state = { token: 'xyz', profile: 'max', session: 'session-a', explanation: '', reason: 'Explain what you meant', teach: async () => ({ok:true}) }
  const pending = { get: () => state, set: next => { state = next } }
  let tree = ui.Clarification({ pending })
  assert.equal(tree.type, 'fieldset')
  assert.match(tree.props.children[0].props.children, /What did you mean/)
  const search = tree.props.children.find(c => c?.type === 'input')
  search.props.onChange({ target: { value: 'reason' } })
  tree = ui.Clarification({ pending })
  assert.deepEqual(tree.props.children.filter(c => c?.type === 'button').map(c => c.props.children), ['Remember what I meant', 'Dismiss'])
  assert.equal(state.explanation, 'reason')
  state = { ...state, session: 'session-b' }
  assert.equal(ui.Clarification({ pending }), null)
})
