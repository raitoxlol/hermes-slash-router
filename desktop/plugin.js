import { host, COMPOSER_AREAS, PALETTE_AREA, atom, useValue, useQuery, Button, Input, StatusDot, Tip } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'hermes-slash-router'
const MIN_CONFIDENCE = 0.85
const MAX_CORRECTION_EXAMPLES = 8
const normalize = value => String(value).replace(/^\//, '').toLowerCase()
const clarificationToken = explanation => explanation.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
  .replace(/[^\p{L}\p{N}_:-]+/gu, '_').replace(/^[_:]+|[_:]+$/g, '').slice(0, 64)

export function catalogEntries(catalog) {
  return (catalog.pairs || []).filter(([name]) => {
    const desktop = catalog.commands?.[name]?.desktop
    return !desktop || desktop === 'hidden'
  }).map(([name, description]) => ({ name: normalize(name), description }))
}
const profileOf = api => api.state.focusedSessionProfile?.get() || api.state.profile.get()
const sessionOf = api => api.state.focusedSessionId?.get() || api.state.activeSessionId?.get() || null
async function routeIdentity(profile, entries, token) {
  const bytes = new TextEncoder().encode(JSON.stringify([...entries].sort((a, b) => a.name.localeCompare(b.name))))
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  const fingerprint = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
  return { key: JSON.stringify([profile, fingerprint, token]), scope: JSON.stringify([profile, fingerprint]) }
}
function remember(ctx, key, token, route) {
  const record = { input: token, target: route.target, source: route.source, origin: route.origin || route.source,
    confidence: route.confidence, model: route.model, at: new Date().toISOString() }
  if (record.origin === 'correction' && typeof route.meaning === 'string' && route.meaning.trim()) {
    record.meaning = route.meaning.trim().slice(0, 500)
  }
  const saved = ctx.storage.get('routes', {})
  const next = Object.fromEntries(Object.entries(saved).filter(([k]) => k !== key).slice(-499))
  const existingOrigin = saved[key]?.origin || saved[key]?.source
  // Keep an explicit correction as the user's reminder. Ordinary Jev results
  // still go in history, but cannot erase what the user taught for this token.
  next[key] = existingOrigin === 'correction' && record.origin !== 'correction' ? saved[key] : record
  ctx.storage.set('routes', next)
  ctx.storage.set('history', [...ctx.storage.get('history', []).slice(-199), {
    input: token, target: route.target, source: record.source, origin: record.origin,
    confidence: record.confidence, model: record.model, at: record.at
  }])
}
function priorRouteFor(ctx, key, entries) {
  const saved = ctx.storage.get('routes', {})[key]
  const origin = saved?.origin || saved?.source
  if (!['jev', 'correction'].includes(origin) || !Number.isFinite(saved?.confidence) ||
      saved.confidence < MIN_CONFIDENCE || !entries.some(entry => entry.name === saved.target)) return null
  const prior = { target: saved.target, confidence: saved.confidence, origin }
  if (origin === 'correction' && typeof saved.meaning === 'string' && saved.meaning.trim()) {
    prior.token = saved.input
    prior.meaning = saved.meaning.trim().slice(0, 500)
  }
  return prior
}
function correctionExamplesFor(ctx, scope, currentToken, entries) {
  const allowed = new Set(entries.map(entry => entry.name))
  const saved = ctx.storage.get('routes', {})
  return Object.entries(saved).flatMap(([key, route]) => {
    let identity
    try { identity = JSON.parse(key) } catch { return [] }
    if (!Array.isArray(identity) || identity.length !== 3 ||
        JSON.stringify(identity.slice(0, 2)) !== scope || identity[2] === currentToken) return []
    const origin = route?.origin || route?.source
    const meaning = typeof route?.meaning === 'string' ? route.meaning.trim().slice(0, 500) : ''
    if (origin !== 'correction' || !meaning || !allowed.has(route.target) ||
        !Number.isFinite(route.confidence) || route.confidence < MIN_CONFIDENCE ||
        typeof identity[2] !== 'string' || !identity[2] || identity[2].length > 64) return []
    return [{ token: identity[2], target: route.target, meaning, confidence: route.confidence,
      origin: 'correction', at: typeof route.at === 'string' ? route.at : '' }]
  }).sort((a, b) => a.at.localeCompare(b.at)).slice(-MAX_CORRECTION_EXAMPLES)
    .map(({ token, target, meaning, confidence, origin }) => ({ token, target, meaning, confidence, origin }))
}
export function createHandler(ctx, api = host, show = () => {}) {
  let generation = 0
  return async draft => {
    const turn = ++generation
    show(null)
    // A final punctuation mark belongs to the command token, not its arguments.
    const match = /^(\s*)\/([\p{L}\p{N}_:-]+)[.!?,]*(?=\s|$)([\s\S]*)$/u.exec(draft.text)
    if (!match) return draft
    const token = normalize(match[2])
    if (token.length > 64) return draft
    const profile = profileOf(api), session = sessionOf(api)
    const current = () => turn === generation && profile === profileOf(api) && session === sessionOf(api)
    let entries = [], key
    const clarify = reason => {
      if (!current()) return null
      const pending = { token, reason, profile, session, explanation: '', busy: false }
      let learning = false
      pending.teach = async explanation => {
        if (!current() || learning) return { ok: false, message: 'Send the shortcut again to start over.' }
        explanation = String(explanation).trim()
        if (!explanation || explanation.length > 500) return { ok: false, message: 'Describe what you wanted in 1–500 characters.' }
        learning = true
        try {
          const fresh = catalogEntries(await api.request('commands.catalog', {}))
          if (!current() || !fresh.length) return { ok: false, message: 'Send again to refresh the command list.' }
          const identity = await routeIdentity(profile, fresh, token)
          const freshKey = identity.key
          // Put the explanation in both fields: new backends can use it directly, while
          // older gateways that already expose /resolve can still interpret its safe slug.
          const route = await ctx.rest('/resolve', { method: 'POST', body: {
            token: clarificationToken(explanation) || token, explanation, commands: fresh,
            prior_route: priorRouteFor(ctx, freshKey, fresh),
            correction_examples: correctionExamplesFor(ctx, identity.scope, token, fresh)
          }, timeoutMs: 5000 })
          if (!current()) return { ok: false, message: 'Send the shortcut again in this chat.' }
          if (!route?.target || !Number.isFinite(route.confidence) || route.confidence < MIN_CONFIDENCE || !fresh.some(e => e.name === route.target)) {
            return { ok: false, message: 'I’m still unsure. Describe the action more specifically, or type the exact command you meant.' }
          }
          const latest = catalogEntries(await api.request('commands.catalog', {}))
          if (!current() || freshKey !== (await routeIdentity(profile, latest, token)).key) return { ok: false, message: 'Available commands changed. Try explaining again.' }
          remember(ctx, freshKey, token, { ...route, source: 'correction', origin: 'correction', meaning: explanation })
          show(null)
          api.notify({ kind: 'info', message: `Saved: /${token} → /${route.target}. Press Send to run it.` })
          return { ok: true }
        } catch {
          return { ok: false, message: 'Could not reach Jev. Your explanation is still here; wait a moment, then try again.' }
        } finally {
          learning = false
        }
      }
      show(pending)
      return null
    }
    try {
      const catalog = await api.request('commands.catalog', {})
      if (!current()) return null
      if (Object.hasOwn(catalog.canon || {}, `/${token}`) || Object.hasOwn(catalog.commands || {}, `/${token}`)) return draft
      entries = catalogEntries(catalog)
      if (!entries.length) return clarify('No desktop commands are available. Reconnect and send again.')
      const identity = await routeIdentity(profile, entries, token)
      key = identity.key
      const decision = await ctx.rest('/resolve', { method: 'POST', body: {
        token, commands: entries, prior_route: priorRouteFor(ctx, key, entries),
        correction_examples: correctionExamplesFor(ctx, identity.scope, token, entries)
      }, timeoutMs: 5000 })
      const route = decision && { ...decision, source: 'jev', origin: 'jev' }
      if (!current()) return null
      if (!route?.target || !Number.isFinite(route.confidence) || route.confidence < MIN_CONFIDENCE || !entries.some(e => e.name === route.target)) {
        return clarify('Tell me what you wanted to do. I’ll work out the command and remember it.')
      }
      remember(ctx, key, token, route)
      api.notify({ kind: 'info', message: `/${token} → /${route.target}` })
      return { ...draft, text: `${match[1]}/${route.target}${match[3]}` }
    } catch {
      return clarify(entries.length
        ? 'Jev is unavailable or busy. Tell me what you meant, then retry in a moment.'
        : 'The command list could not load. Reconnect and send again.')
    }
  }
}

export function Clarification({ pending }) {
  const state = useValue(pending)
  const focusedProfile = useValue(host.state.focusedSessionProfile || host.state.profile)
  const profile = useValue(host.state.profile)
  const focusedSession = useValue(host.state.focusedSessionId || host.state.activeSessionId)
  const activeSession = useValue(host.state.activeSessionId)
  const session = focusedSession || activeSession || null
  if (!state || state.profile !== (focusedProfile || profile) || state.session !== session) return null
  const teach = async () => {
    if (state.busy || !state.explanation.trim()) return
    const busyState = { ...state, busy: true }
    pending.set(busyState)
    const result = await state.teach(state.explanation)
    if (!result.ok && pending.get() === busyState) pending.set({ ...state, reason: result.message })
  }
  return jsxs('fieldset', {
    'aria-label': 'Slash command clarification',
    children: [
      jsx('legend', { children: `What did you mean by /${state.token}?` }),
      jsx('p', { role: 'status', children: state.reason }),
      jsx(Input, { 'aria-label': 'What did you mean?', placeholder: 'Describe what you wanted to do…', value: state.explanation,
        maxLength: 500, disabled: state.busy, onChange: event => pending.set({ ...state, explanation: event.target.value }),
        autoFocus: true,
        onKeyDown: event => {
          if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); void teach() }
          if (event.key === 'Escape' && !state.busy) { event.preventDefault(); event.stopPropagation(); pending.set(null) }
        } }),
      jsx(Button, { type: 'button', disabled: state.busy || !state.explanation.trim(), onClick: teach,
        children: state.busy ? 'Understanding…' : 'Remember what I meant' }),
      jsx(Button, { type: 'button', disabled: state.busy, onClick: () => pending.set(null), children: 'Dismiss' }),
      jsx('p', { children: 'Enter to save, Esc to dismiss. Jev keeps this as a hint and still checks every time. Once saved, press Send again.' })
    ]
  })
}

const KEY_STATES = {
  loaded: { tone: 'good', label: 'Jev key', tip: 'TYPESAFE_API_KEY is loaded. Slash routing is ready.' },
  saved: { tone: 'warn', label: 'Jev key: restart', tip: 'TYPESAFE_API_KEY is saved in .env but not loaded. Restart the Hermes gateway.' },
  missing: { tone: 'bad', label: 'Jev key missing', tip: 'TYPESAFE_API_KEY is not saved. Add it to ~/.hermes/.env, then restart Hermes.' },
  offline: { tone: 'muted', label: 'Jev key ?', tip: 'Cannot reach the Slash Router backend. Enable the plugin in config.yaml and restart Hermes.' }
}

export function keyState(data, error) {
  if (error || !data) return KEY_STATES.offline
  return KEY_STATES[data.key] || (data.configured ? KEY_STATES.loaded : KEY_STATES.missing)
}

export function KeyStatus({ ctx }) {
  const { data, error, refetch } = useQuery({
    queryKey: [ID, 'key-status'],
    queryFn: () => ctx.rest('/status', { timeoutMs: 3000 }),
    refetchInterval: 60000,
    retry: false
  })
  const state = keyState(data, error)
  return jsx(Tip, {
    label: `${state.tip} Click to recheck.`,
    children: jsxs('button', {
      type: 'button',
      'aria-label': state.tip,
      className: 'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground',
      onClick: () => { void refetch() },
      children: [jsx(StatusDot, { tone: state.tone }), state.label]
    })
  })
}

export default {
  id: ID,
  name: 'Slash Router · Jev',
  defaultEnabled: false,
  register(ctx) {
    const pending = atom(null)
    ctx.register({ id: 'key-status', area: 'statusBar.right', order: 140, render: () => jsx(KeyStatus, { ctx }) })
    ctx.register({ id: 'clarification', area: COMPOSER_AREAS.bottom, render: () => jsx(Clarification, { pending }) })
    ctx.register({ id: 'route', area: COMPOSER_AREAS.middleware, order: -100, data: { handler: createHandler(ctx, host, value => pending.set(value)) } })
    ctx.register({ id: 'history', area: PALETTE_AREA, data: {
      id: `${ID}.history`, label: 'Slash Router: copy routing history', keywords: ['jev', 'commands'],
      run: async () => {
        await ctx.os.writeClipboard(JSON.stringify(ctx.storage.get('history', []), null, 2))
        host.notify({ kind: 'info', message: 'Routing history copied (command names only).' })
      }
    } })
    ctx.register({ id: 'forget', area: PALETTE_AREA, data: {
      id: `${ID}.forget`, label: 'Slash Router: forget the last route reminder', keywords: ['jev', 'undo'],
      run: () => {
        const routes = ctx.storage.get('routes', {})
        const last = Object.keys(routes).at(-1)
        if (last) delete routes[last]
        ctx.storage.set('routes', routes)
        host.notify({ kind: 'info', message: last ? 'Last route reminder forgotten.' : 'No saved routes.' })
      }
    } })
  }
}
