export type FactoryWindow = { kind: string; percentUsed: number; resetsAt?: string }

/** What the band and /factory draw from: refreshed on a timer and on each measurement. */
export type FactorySnapshot = {
  /** The repo the arming covers, or null when this session is in no armed repo. */
  repo: string | null
  /** The arming's state directory under ~/.claude/state/build-loop/. */
  state: string | null
  /** Whether this session is the build seat (its opening prompt carried the marker). */
  isSeat: boolean
  isStopped: boolean
  /** The pause file's `until`, while it names a time still to come. */
  pausedUntil: string | null
  consecutive: number
  max: number
  total: number
  maxTotal: number
  resumes: number
  windows: FactoryWindow[]
  costUsd: number | null
}

declare module 'claude-code' {
  interface PluginState {
    'factory-live': { snapshot: FactorySnapshot | null; isHidden: boolean }
  }
}
