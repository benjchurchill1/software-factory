// factory-live: the software-factory build seat, from inside Claude Code.
//
// Three jobs, all scoped to a repo the keep-alive hook is armed for
// (hooks/arm.py), and all inert anywhere else:
//
//   wake      When the seat paused on a usage limit (it wrote the arming's
//             `pause` file and stopped), submit a resume prompt once the
//             pause's `until` has passed. This is the loop prompt's
//             <RESUME_MECHANISM>. Once per pause, at most MAX_RESUMES per
//             arming, never after the `stop` file or a stale arming.
//   measure   Write the account's rate-limit windows to `usage-window` (one
//             line, "<percent left> <resets at>", for pre-flight's
//             <USAGE_WINDOW_COMMAND>) and `usage-window.json`, and every turn
//             of the seat (subagents included) to `turns.jsonl`: duration,
//             tokens, model, and the session's running cost.
//   show      A band above the prompt with the keep-alive's counts, the pause,
//             the windows and the cost; `/factory` prints the same with paths.
//
// The journal stays single-writer: this mod writes only its own files in the
// arming's state directory, never `journal.jsonl`.

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { FactorySnapshot, FactoryWindow } from '../types'

const snapshot = atom({ plugin: 'factory-live', key: 'snapshot' } as const, null)
const isHidden = atom({ plugin: 'factory-live', key: 'isHidden' } as const, false)

const MAX_AGE_MS = 72 * 3600 * 1000 // the keep-alive hook's MAX_AGE_H
const TICK_MS = 30 * 1000
const GRACE_MS = 60 * 1000 // let the window actually reset before waking
const MAX_RESUMES = 24
const ROTATE_BYTES = 2 * 1024 * 1024

type Arming = {
  state: string
  repo: string
  marker: string
  armingId: string
  armedAt: number
  max: number
  maxTotal: number
  excluded: string[]
}

type Resumed = { arming: string; until: string; count: number }

const asInt = (value: unknown, fallback: number) => {
  const n = Number(value)
  return Number.isInteger(n) && n >= 1 ? n : fallback
}

const readJson = async ($: EngineInterface, path: string): Promise<any> => {
  try {
    return JSON.parse(await $.fs.read(path))
  } catch {
    return undefined
  }
}

const realPath = async ($: EngineInterface, path: string) => {
  const stat = await $.fs.stat(path, { resolve: true }).catch(() => undefined)
  return (stat?.realPath ?? path).replace(/\/+$/, '')
}

const isInside = (child: string, parent: string) =>
  child === parent || child.startsWith(parent + '/')

const parseAt = (value: unknown) => {
  if (typeof value !== 'string') return undefined
  const ms = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : value + 'Z')
  return Number.isNaN(ms) ? undefined : ms
}

const hhmm = (iso: string) => {
  const ms = parseAt(iso)
  return ms === undefined ? iso : new Date(ms).toISOString().slice(11, 16) + 'Z'
}

const stateRoot = async ($: EngineInterface) => {
  const override = await $.env.get('BUILD_LOOP_STATE_ROOT')
  if (override) return override.replace(/\/+$/, '')
  return `${(await $.env.get('HOME')) ?? ''}/.claude/state/build-loop`
}

// The arming for this session's repo: the longest cwd_prefix containing the
// session's directory, as the keep-alive hook picks it.
const findArming = async ($: EngineInterface): Promise<Arming | null> => {
  const root = await stateRoot($)
  const cwd = await realPath($, await $.session.cwd())
  const entries = await $.fs.list(root).catch(() => [])
  const candidates = [root, ...entries.filter(one => one.kind === 'dir').map(one => `${root}/${one.name}`)]
  let best: Arming | null = null
  for (const state of candidates) {
    const path = `${state}/armed.json`
    const cfg = await readJson($, path)
    if (!cfg || typeof cfg.cwd_prefix !== 'string') continue
    const repo = await realPath($, cfg.cwd_prefix)
    if (!isInside(cwd, repo) || (best && best.repo.length >= repo.length)) continue
    const stat = await $.fs.stat(path).catch(() => undefined)
    best = {
      state,
      repo,
      marker: String(cfg.marker ?? ''),
      armingId: String(cfg.arming_id ?? ''),
      armedAt: stat?.mtimeMs ?? 0,
      max: asInt(cfg.max, 60),
      maxTotal: asInt(cfg.max_total, 500),
      excluded: Array.isArray(cfg.exclude_sessions) ? cfg.exclude_sessions.map(String) : [],
    }
  }
  return best
}

const isSeatOf = async ($: EngineInterface, arm: Arming) => {
  const session = await $.session.id()
  if (arm.excluded.includes(session)) return false
  const seat = await readJson($, `${arm.state}/seat.json`)
  return seat?.session === session && seat?.arming === arm.armingId
}

const claimSeat = async ($: EngineInterface, arm: Arming) => {
  const session = await $.session.id()
  if (arm.excluded.includes(session)) return
  const at = new Date(await $.clock.now()).toISOString()
  await $.fs.write(`${arm.state}/seat.json`, JSON.stringify({ session, arming: arm.armingId, at }) + '\n')
}

const hasMarker = (arm: Arming, text: string) => arm.marker.length >= 12 && text.includes(arm.marker)

// Appends are serialised within this process; the files are this mod's alone.
let appending: Promise<void> = Promise.resolve()
const appendLine = ($: EngineInterface, path: string, line: string) => {
  appending = appending.then(async () => {
    let text = await $.fs.read(path).catch(() => '')
    if (text.length > ROTATE_BYTES) {
      await $.fs.write(`${path}.1`, text)
      text = ''
    }
    await $.fs.write(path, text + line + '\n')
  }).catch(() => undefined)
  return appending
}

const pausedUntil = async ($: EngineInterface, arm: Arming) => {
  const pause = await readJson($, `${arm.state}/pause`)
  return typeof pause?.until === 'string' && parseAt(pause.until) !== undefined ? (pause.until as string) : null
}

const resumeText = (arm: Arming, until: string) =>
  `BUILD-LOOP RESUME (factory-live): the usage pause in ${arm.state}/pause ran until ${until}, ` +
  'and that time has passed. Pick the loop back up as §Pausing on a usage limit says: delete the ' +
  'pause file, close the `paused` phase in the journal, run pre-flight again, and carry on from the ' +
  'checkpoint. If pre-flight says PAUSE again, write the new pause file and stop as before; you ' +
  'will be woken at the next reset.'

// Wake the seat once its pause has run out. Returns what it did, for the tests.
const maybeResume = async ($: EngineInterface, arm: Arming): Promise<string> => {
  if (!(await isSeatOf($, arm))) return 'not the seat'
  if (await $.fs.exists(`${arm.state}/stop`)) return 'stopped'
  const now = await $.clock.now()
  if (now - arm.armedAt > MAX_AGE_MS) return 'arming stale'
  const until = await pausedUntil($, arm)
  if (until === null) return 'not paused'
  if (now < (parseAt(until) ?? Infinity) + GRACE_MS) return 'still paused'
  const last: Resumed | undefined = await readJson($, `${arm.state}/resumed.json`)
  const count = last?.arming === arm.armingId ? last.count : 0
  if (last?.arming === arm.armingId && last.until === until) return 'already woken for this pause'
  if (count >= MAX_RESUMES) return 'resume cap reached'
  const next: Resumed = { arming: arm.armingId, until, count: count + 1 }
  await $.fs.write(`${arm.state}/resumed.json`, JSON.stringify(next) + '\n')
  $.ui.toast(`factory-live: usage window reset, resuming the build (${next.count} of ${MAX_RESUMES})`)
  void $.prompt.submit({ text: resumeText(arm, until) })
  return 'resumed'
}

const writeWindows = async ($: EngineInterface, arm: Arming, windows: FactoryWindow[], costUsd: number | null) => {
  const at = new Date(await $.clock.now()).toISOString()
  await $.fs.write(`${arm.state}/usage-window.json`, JSON.stringify({ at, windows, cost_usd: costUsd }) + '\n')
  const tightest = [...windows].sort((a, b) => b.percentUsed - a.percentUsed)[0]
  if (!tightest) return
  const left = Math.max(0, Math.round((100 - tightest.percentUsed) * 10) / 10)
  await $.fs.write(`${arm.state}/usage-window`, `${left} ${tightest.resetsAt ?? ''}`.trim() + '\n')
}

const refresh = async ($: EngineInterface, windows?: FactoryWindow[], costUsd?: number | null) => {
  const arm = await findArming($)
  const previous = (await $.state.get({ plugin: 'factory-live', key: 'snapshot' } as const)).value
  if (!arm) {
    await update($, snapshot, () => null)
    return null
  }
  const count = (await readJson($, `${arm.state}/count.json`)) ?? {}
  const resumed: Resumed | undefined = await readJson($, `${arm.state}/resumed.json`)
  const until = await pausedUntil($, arm)
  const now = await $.clock.now()
  const next: FactorySnapshot = {
    repo: arm.repo,
    state: arm.state,
    isSeat: await isSeatOf($, arm),
    isStopped: await $.fs.exists(`${arm.state}/stop`),
    pausedUntil: until !== null && (parseAt(until) ?? 0) > now ? until : null,
    consecutive: Number(count.consecutive ?? 0),
    max: arm.max,
    total: Number(count.total ?? 0),
    maxTotal: arm.maxTotal,
    resumes: resumed?.arming === arm.armingId ? resumed.count : 0,
    windows: windows ?? previous?.windows ?? [],
    costUsd: costUsd !== undefined ? costUsd : (previous?.costUsd ?? null),
  }
  await update($, snapshot, () => next)
  return arm
}

const describe = (snap: FactorySnapshot | null) => {
  if (!snap?.repo) return 'factory-live: this session is in no repo the keep-alive hook is armed for.'
  const lines = [
    `factory-live: ${snap.repo}`,
    `  this session  ${snap.isSeat ? 'the build seat' : 'not the build seat (its opening prompt did not carry the marker)'}`,
    `  keep-alive    ${snap.isStopped ? 'released by the stop file' : `${snap.consecutive} of ${snap.max} without progress, ${snap.total} of ${snap.maxTotal} this arming`}`,
    `  pause         ${snap.pausedUntil ? `until ${snap.pausedUntil}; the seat is woken a minute after` : 'none'}`,
    `  resumes       ${snap.resumes} of ${MAX_RESUMES} this arming`,
    `  windows       ${snap.windows.length ? snap.windows.map(w => `${w.kind} ${w.percentUsed}%${w.resetsAt ? ` (resets ${w.resetsAt})` : ''}`).join(', ') : 'no reading yet'}`,
    `  cost          ${snap.costUsd === null ? 'no reading yet' : `$${snap.costUsd.toFixed(2)} this session`}`,
    `  files         ${snap.state}/{usage-window,usage-window.json,turns.jsonl,resumed.json,seat.json}`,
    `  pre-flight    <USAGE_WINDOW_COMMAND> can be: cat "${snap.state}/usage-window"`,
  ]
  return lines.join('\n')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'factory',
      description: 'Show the build seat as factory-live sees it: keep-alive counts, pause, windows, cost',
    })
    $.clock.every(TICK_MS, () => {
      void refresh($).then(arm => (arm ? maybeResume($, arm) : undefined)).catch(() => undefined)
    })
    void (async () => {
      const arm = await findArming($)
      // A resumed seat: its marker is in the transcript, not in a new prompt.
      if (arm && !(await isSeatOf($, arm))) {
        const messages = await $.session.messages()
        if (messages.some(one => one.role === 'user' && hasMarker(arm, one.text))) await claimSeat($, arm)
      }
      await refresh($)
    })().catch(() => undefined)
    return next(e)
  })

  // The seat names itself with the marker in the prompt the owner pastes.
  on('prompt.submit', async ($, e, next) => {
    const arm = await findArming($).catch(() => null)
    if (arm && hasMarker(arm, e.text) && !(await isSeatOf($, arm))) {
      await claimSeat($, arm)
      void refresh($).catch(() => undefined)
    }
    return next(e)
  })

  on('session.measure', async ($, e, next) => {
    const windows = e.rateLimits.map(w => ({ kind: w.kind, percentUsed: w.percentUsed, resetsAt: w.resetsAt }))
    const costUsd = e.cost?.usd ?? null
    const arm = await refresh($, windows, costUsd).catch(() => null)
    if (arm && windows.length) await writeWindows($, arm, windows, costUsd).catch(() => undefined)
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const arm = await findArming($).catch(() => null)
    if (arm && (await isSeatOf($, arm))) {
      const usage = e.usage
      const costUsd = e.agentId === undefined ? ((await $.session.usage()).cost?.usd ?? null) : null
      const row = {
        at: new Date(await $.clock.now()).toISOString(),
        session: await $.session.id(),
        agent: e.agentId ?? null,
        turn: e.turnId,
        ms: e.durationMs,
        reason: e.reason,
        model: usage?.model ?? null,
        input: usage?.input_tokens ?? 0,
        output: usage?.output_tokens ?? 0,
        cache_read: usage?.cache_read_input_tokens ?? 0,
        cache_write: usage?.cache_creation_input_tokens ?? 0,
        session_cost_usd: costUsd,
      }
      await appendLine($, `${arm.state}/turns.jsonl`, JSON.stringify(row))
    }
    return next(e)
  })

  on('command.run', { command: 'factory' }, async $ => {
    await refresh($).catch(() => undefined)
    const snap = (await $.state.get({ plugin: 'factory-live', key: 'snapshot' } as const)).value ?? null
    await update($, isHidden, () => false)
    return { text: describe(snap) }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const snap = await read($, snapshot)
    if (e.props.hasSurvey || !snap?.repo || (await read($, isHidden))) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const tightest = [...snap.windows].sort((a, b) => b.percentUsed - a.percentUsed)[0]
    const parts = [
      snap.isSeat ? 'seat' : 'watching',
      snap.isStopped ? 'released' : `held ${snap.consecutive}/${snap.max} · ${snap.total}/${snap.maxTotal}`,
      snap.pausedUntil ? `paused until ${hhmm(snap.pausedUntil)}${snap.isSeat ? ', wakes after' : ''}` : '',
      tightest ? `${tightest.kind.replace('_', ' ')} ${tightest.percentUsed}%` : '',
      snap.costUsd === null ? '' : `$${snap.costUsd.toFixed(2)}`,
    ].filter(Boolean)
    return (
      <Box>
        <Text color={snap.pausedUntil ? 'yellow' : undefined} dimColor={!snap.pausedUntil}>
          factory · {parts.join(' · ')}{' '}
        </Text>
        <Button key="hide" label="Hide" plain onPress={() => update($, isHidden, () => true)} />
      </Box>
    )
  })
}

export const internals = { maybeResume, findArming, describe, resumeText, MAX_RESUMES, GRACE_MS }
