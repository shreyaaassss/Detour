import { useState } from 'react'
import { api } from '../api'
import type { Report } from '../types'
import { Glyph } from './ui'

export function ChecksPanel({ report, onRun }: { report: Report | null; onRun: () => void }) {
  const [result, setResult] = useState<Report | null>(null)
  const [busy, setBusy] = useState(false)
  const shown = result ?? report
  if (!shown) return <p className="empty">There is no plan to check yet.</p>

  async function run() {
    setBusy(true)
    try { setResult(await api.validate()); onRun() } finally { setBusy(false) }
  }

  return (
    <div>
      <div className="row" style={{ marginBottom: 10 }}>
        <span className={`chip ${shown.valid ? 'ok' : 'bad'}`}>
          <Glyph name={shown.valid ? 'ok' : 'bad'} size={12} />{shown.valid ? 'Every check passed' : `${shown.violations.length} problems found`}
        </span>
        <button className="btn" onClick={run} disabled={busy}>Run the checks again</button>
      </div>
      <p className="small muted" style={{ maxWidth: '62ch', marginBottom: 12 }}>
        A separate module re-times every route from scratch. It shares no code with the planner, so it cannot repeat the planner's mistakes.
        A plan that fails is never shown as valid.
      </p>
      {shown.violations.length > 0 && (
        <ul className="stack" style={{ padding: 0, margin: '0 0 14px' }}>
          {shown.violations.map((v, i) => <li key={i} className="notice err" style={{ listStyle: 'none' }}><b>{v.code}</b> {v.message}</li>)}
        </ul>
      )}
      <ul className="stack" style={{ padding: 0, margin: 0 }}>
        {shown.checks.map((c) => (
          <li key={c} style={{ listStyle: 'none', display: 'flex', gap: 8 }}>
            <span style={{ color: shown.valid ? 'var(--kept)' : 'var(--ink-3)' }}><Glyph name="ok" /></span>{c}
          </li>
        ))}
      </ul>
    </div>
  )
}
