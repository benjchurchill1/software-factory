import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const HOME = '/home/owner'
const STATE = `${HOME}/.claude/state/build-loop/app-0123456789`
const REPO = '/work/app'
const MARKER = 'nonce-7f3a9c2e1b4d'
const T0 = Date.parse('2026-10-03T10:00:00Z')

type World = { files: Map<string, { text: string; mtimeMs: number }>; prompts: string[]; toasts: string[] }

// An in-memory machine beneath the plugin: files, the session, the prompt queue.
const world = (on: On, opts: { seat?: boolean; session?: string } = {}): World => {
  const w: World = { files: new Map(), prompts: [], toasts: [] }
  const put = (path: string, text: string, mtimeMs = T0) => w.files.set(path, { text, mtimeMs })
  put(`${STATE}/armed.json`, JSON.stringify({ cwd_prefix: REPO, marker: MARKER, max: 60, max_total: 500, arming_id: 'a1', exclude_sessions: ['monitor'] }))
  put(`${STATE}/count.json`, JSON.stringify({ consecutive: 3, total: 41 }))
  if (opts.seat !== false) put(`${STATE}/seat.json`, JSON.stringify({ session: 'seat', arming: 'a1' }))

  mock.env(on, { HOME })
  const value = <T,>(v: T) => ({ value: v })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.measure', ($, e) => ({ changed: e.changed }))
  on('turn.complete', ($, e) => ({ text: e.answer }) as any)
  on('session.id', () => value(opts.session ?? 'seat'))
  on('session.cwd', () => value(`${REPO}/packages/web`))
  on('session.messages', () => value([]))
  on('session.usage', () => value({ startedAt: T0, context: { window: 200000 }, rateLimits: [], cost: { usd: 1.5 } }))
  on('command.register', ($, e) => value({ command: e.name }))
  on('ui.toast', ($, e) => (w.toasts.push(e.text), value(undefined)))
  on('prompt.submit', ($, e) => (w.prompts.push(e.text), { text: e.text }))
  on('fs.read', ($, e) => {
    const file = w.files.get(e.path)
    return file ? value(file.text) : { deny: `ENOENT ${e.path}` }
  })
  on('fs.write', ($, e) => (put(e.path, e.text), value(undefined)))
  on('fs.exists', ($, e) => value(w.files.has(e.path)))
  on('fs.stat', ($, e) => {
    const file = w.files.get(e.path)
    const isDir = [...w.files.keys()].some(k => k.startsWith(e.path + '/')) || e.path.startsWith(REPO)
    if (!file && !isDir) return { deny: `ENOENT ${e.path}` }
    return value({ kind: file ? 'file' : 'dir', size: file?.text.length ?? 0, mtimeMs: file?.mtimeMs ?? 0, isLink: false, ...(e.resolve ? { realPath: e.path } : {}) })
  })
  on('fs.list', ($, e) => {
    const names = new Set<string>()
    for (const k of w.files.keys()) if (k.startsWith(e.path + '/')) names.add(k.slice(e.path.length + 1).split('/')[0]!)
    return value([...names].map(name => ({ name, kind: w.files.has(`${e.path}/${name}`) ? 'file' : 'dir', size: 0, mtimeMs: 0, isLink: false }) as const))
  })
  return w
}

const start = ($: any) =>
  $.session.start({ cwd: `${REPO}/packages/web`, surface: 'terminal', isInteractive: true })

test('wakes the seat once, a minute after its pause runs out', async ($, on) => {
  const clock = mock.clock(on, { now: T0 })
  const w = world(on)
  w.files.set(`${STATE}/pause`, { text: JSON.stringify({ until: '2026-10-03T11:00:00Z', reason: 'usage' }), mtimeMs: T0 })
  await start($)

  await clock.advance(60 * 60 * 1000) // 11:00, the reset itself: not yet
  expect(w.prompts).toHaveLength(0)
  await clock.advance(90 * 1000) // 11:01:30
  expect(w.prompts).toHaveLength(1)
  expect(w.prompts[0]).toContain('BUILD-LOOP RESUME')
  expect(w.prompts[0]).toContain(`${STATE}/pause`)
  expect(w.toasts.some(t => t.includes('resuming the build'))).toBe(true)
  expect(JSON.parse(w.files.get(`${STATE}/resumed.json`)!.text)).toEqual({ arming: 'a1', until: '2026-10-03T11:00:00Z', count: 1 })

  await clock.advance(10 * 60 * 1000) // the same pause never wakes it twice
  expect(w.prompts).toHaveLength(1)

  // A new pause after the next pre-flight wakes it again.
  w.files.set(`${STATE}/pause`, { text: JSON.stringify({ until: '2026-10-03T12:00:00Z', reason: 'usage' }), mtimeMs: T0 })
  await clock.set(Date.parse('2026-10-03T12:02:00Z'))
  expect(w.prompts).toHaveLength(2)
})

test('leaves alone a session that is not the seat', async ($, on) => {
  const clock = mock.clock(on, { now: T0 })
  const w = world(on, { session: 'someone-else' })
  w.files.set(`${STATE}/pause`, { text: JSON.stringify({ until: '2026-10-03T10:05:00Z' }), mtimeMs: T0 })
  await start($)
  await clock.advance(30 * 60 * 1000)
  expect(w.prompts).toHaveLength(0)
})

test('does not wake a seat that wrote its stop file', async ($, on) => {
  const clock = mock.clock(on, { now: T0 })
  const w = world(on)
  w.files.set(`${STATE}/pause`, { text: JSON.stringify({ until: '2026-10-03T10:05:00Z' }), mtimeMs: T0 })
  w.files.set(`${STATE}/stop`, { text: 'done\n', mtimeMs: T0 })
  await start($)
  await clock.advance(30 * 60 * 1000)
  expect(w.prompts).toHaveLength(0)
})

test('does not wake against a stale arming', async ($, on) => {
  const clock = mock.clock(on, { now: T0 + 73 * 3600 * 1000 })
  const w = world(on)
  w.files.set(`${STATE}/pause`, { text: JSON.stringify({ until: '2026-10-03T10:05:00Z' }), mtimeMs: T0 })
  await start($)
  await clock.advance(5 * 60 * 1000)
  expect(w.prompts).toHaveLength(0)
})

test('the pasted prompt with the marker claims the seat', async ($, on) => {
  mock.clock(on, { now: T0 })
  const w = world(on, { seat: false })
  await start($)
  await $.prompt.submit({ text: `Run the build loop. ${MARKER}` })
  expect(JSON.parse(w.files.get(`${STATE}/seat.json`)!.text)).toMatchObject({ session: 'seat', arming: 'a1' })
})

test('the excluded monitor session cannot claim the seat', async ($, on) => {
  mock.clock(on, { now: T0 })
  const w = world(on, { seat: false, session: 'monitor' })
  await start($)
  await $.prompt.submit({ text: `Watching. ${MARKER}` })
  expect(w.files.has(`${STATE}/seat.json`)).toBe(false)
})

test('a measurement writes the tightest window for pre-flight', async ($, on) => {
  mock.clock(on, { now: T0 })
  const w = world(on)
  await start($)
  await $.session.measure({
    context: { window: 200000 },
    rateLimits: [
      { kind: 'seven_day', percentUsed: 40, resetsAt: '2026-10-08T00:00:00Z' },
      { kind: 'five_hour', percentUsed: 72.5, resetsAt: '2026-10-03T13:00:00Z' },
    ],
    cost: { usd: 12.4 },
    changed: ['rateLimits', 'cost'],
  })
  expect(w.files.get(`${STATE}/usage-window`)!.text).toBe('27.5 2026-10-03T13:00:00Z\n')
  expect(JSON.parse(w.files.get(`${STATE}/usage-window.json`)!.text)).toMatchObject({ cost_usd: 12.4 })
})

test("the seat's turns are recorded with their tokens", async ($, on) => {
  mock.clock(on, { now: T0 })
  const w = world(on)
  await start($)
  await $.turn.complete({
    answer: 'lane 3 built',
    durationMs: 42000,
    isAborted: false,
    turnId: 't1',
    reason: 'answer',
    usage: { model: 'm', input_tokens: 10, output_tokens: 20, cache_read_input_tokens: 30, cache_creation_input_tokens: 40 },
  })
  const row = JSON.parse(w.files.get(`${STATE}/turns.jsonl`)!.text.trim())
  expect(row).toMatchObject({ session: 'seat', agent: null, turn: 't1', ms: 42000, input: 10, output: 20, cache_read: 30, cache_write: 40, session_cost_usd: 1.5 })
})

test('the band shows the keep-alive counts on every surface that has one', async ($, on) => {
  mock.clock(on, { now: T0 })
  world(on)
  await start($)
  await $.command.run({ command: 'factory', args: '', origin: { kind: 'user' }, presentation: { isFullscreen: false, columns: 120 } } as any)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({
      plugin: 'factory-live',
      surface,
      component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 120 } as any,
    })
    expect(await ui.find({ type: 'Text', text: /held 3\/60 · 41\/500/ })).toBeDefined()
    await ui.unmount()
  }
})
