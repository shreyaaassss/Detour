import type { ReactNode } from 'react'
import type { IncidentState, Status } from '../types'
import { STATE_LABEL, STATUS_LABEL } from '../labels'

type GlyphName = Status | 'ok' | 'bad' | 'lock' | 'breakdown' | 'closure' | 'urgent'

const PATHS: Record<GlyphName, ReactNode> = {
  kept: <path d="M3 8.5l3.2 3L13 4.5" />,
  ok: <path d="M3 8.5l3.2 3L13 4.5" />,
  moved: <path d="M2.5 5.5h9m-2.5-3 3 3-3 3M13.5 10.5h-9m2.5-3-3 3 3 3" />,
  broken: <path d="M4 4l8 8M12 4l-8 8" />,
  bad: <path d="M4 4l8 8M12 4l-8 8" />,
  new: <path d="M8 3v10M3 8h10" />,
  lock: <path d="M5 7V5.5a3 3 0 016 0V7M4 7h8v6H4z" />,
  breakdown: <path d="M8 2.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM8 5v3.5M8 10.6v.4" />,
  closure: <path d="M2 4h12v3H2zM2 9h12v3H2zM5 4l-2 3m5-3L6 7m5-3L9 7m4-3l-2 3" />,
  urgent: <path d="M9 1.8L3.5 9H8l-1 5.2L12.5 7H8z" />,
}

export function Glyph({ name, size = 14 }: { name: GlyphName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flex: 'none' }}>
      {PATHS[name]}
    </svg>
  )
}

export function StatusChip({ status, count }: { status: Status; count?: number }) {
  return (
    <span className={`chip ${status}`}>
      <Glyph name={status} size={12} />
      {STATUS_LABEL[status]}
      {count !== undefined && <span className="nums">{count}</span>}
    </span>
  )
}

const GOOD = new Set<IncidentState>(['COMMITTED'])
const BAD = new Set<IncidentState>(['EXHAUSTED', 'CANCELLED', 'REJECTED'])

/** Where a rescue stands, in plain words and with a colour that matches how it is going. */
export function StateChip({ state }: { state: IncidentState }) {
  const cls = GOOD.has(state) ? 'kept' : BAD.has(state) ? 'broken' : 'moved'
  return <span className={`chip ${cls}`}>{STATE_LABEL[state]}</span>
}
