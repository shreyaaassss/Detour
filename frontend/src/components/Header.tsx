import { useState } from 'react'
import { getActor, setActor } from '../api'
import { hhmm } from '../format'
import type { AppState } from '../types'
import { Glyph } from './ui'

interface Props {
  state: AppState | null
  connected: boolean
  onReset: () => void
  onChecks: () => void
  busy: boolean
}

export function Header({ state, connected, onReset, onChecks, busy }: Props) {
  const [actor, setActorState] = useState(getActor())
  const report = state?.report
  return (
    <header className="topbar">
      <div className="brand">
        <svg viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 21h6a4 4 0 004-4V9a4 4 0 014-4h6" />
          <path d="M20 2l3 3-3 3" />
        </svg>
        DeTour
      </div>
      <div className="where">
        <strong>{state?.scenario.name ?? 'Loading'}</strong>
        <span>{state ? `${state.scenario.vehicles.length} vehicles, ${state.scenario.deliveries.length} deliveries` : ''}</span>
      </div>
      <div className="clock" title="The simulated time the current plan is based on">
        {state ? hhmm(state.as_of ?? state.scenario.day_start) : '--:--'}
        <small>{state?.as_of != null ? 'plan as of' : 'day starts'}</small>
      </div>
      <div className="spacer" />
      {report && (
        <button className={`chip ${report.valid ? 'ok' : 'bad'}`} onClick={onChecks}
          title="Checked by a separate module that shares no code with the planner">
          <Glyph name={report.valid ? 'ok' : 'bad'} size={13} />
          {report.valid ? `Plan valid (${report.checks.length} checks)` : `${report.violations.length} problems found`}
        </button>
      )}
      <span className="live" role="status">
        <span className={`dot ${connected ? 'on' : ''}`} />
        {connected ? 'Live' : 'Reconnecting'}
      </span>
      <label className="actor">
        Acting as
        <input type="text" value={actor} aria-label="Your name for the audit log"
          onChange={(e) => { setActorState(e.target.value); setActor(e.target.value || 'dispatcher') }} />
      </label>
      <button className="btn" onClick={onReset} disabled={busy}>Reset demo</button>
    </header>
  )
}
