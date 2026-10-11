import { useState } from 'react'
import { api, ApiError, getActor } from '../api'
import { AuditPanel } from '../components/AuditPanel'
import { Board } from '../components/Board'
import { ChecksPanel } from '../components/ChecksPanel'
import { ComparePanel } from '../components/ComparePanel'
import { DisruptionPanel } from '../components/DisruptionPanel'
import { Header } from '../components/Header'
import { MapView } from '../components/MapView'
import { MessagesPanel } from '../components/MessagesPanel'
import { PlanTable } from '../components/PlanTable'
import { PreviewPanel } from '../components/PreviewPanel'
import { RescuePanel } from '../components/RescuePanel'
import type { PreviewResult } from '../types'
import { useDetour } from '../useDetour'
import { useLive, useOverview } from '../useRescue'
import { api as rescueApi } from '../api'

type Tab = 'compare' | 'rescues' | 'messages' | 'plan' | 'audit' | 'checks'

export default function Dispatch() {
  const { state, presets, audit, connected, error, refresh, refreshAudit } = useDetour()
  const rescue = useOverview()
  const messages = useLive(() => rescueApi.messages(), ['state'])
  const [tab, setTab] = useState<Tab>('compare')
  const [selected, setSelected] = useState<string | null>(null)
  const [showOriginal, setShowOriginal] = useState(true)
  const [pendingPreview, setPreview] = useState<PreviewResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)

  // a preview is only good for the plan it was built on
  const preview = state?.plan ? pendingPreview : null
  const stale = preview !== null && state !== null && state.version !== preview.base_version

  async function apply() {
    if (!preview) return
    setBusy(true)
    setApplyError(null)
    try {
      await api.confirm(preview.preview_id, getActor())
      setPreview(null)
      await refresh()
      setTab('compare')
    } catch (e) {
      setApplyError(e instanceof ApiError ? e.message : 'Could not reach the server')
    } finally {
      setBusy(false)
      void refreshAudit()
    }
  }

  async function reset() {
    setBusy(true)
    try { await api.reset(); setPreview(null); setSelected(null) } finally { setBusy(false) }
  }

  if (!state) {
    return (
      <div className="app"><Header state={null} connected={connected} onReset={reset} onChecks={() => {}} busy />
        <p className="empty" style={{ padding: 24 }}>{error ? `Cannot reach the server: ${error}. Start the backend and reload.` : 'Loading.'}</p>
      </div>
    )
  }

  const { original, report, diff } = state
  // while a change is being reviewed, draw the proposal instead of the current plan
  const scenario = preview?.scenario ?? state.scenario
  const plan = preview?.plan ?? state.plan
  const now = state.as_of ?? scenario.day_start
  const counts = diff?.counts
  const tabs: [Tab, string, number | null][] = [
    ['compare', 'What changed', counts ? counts.moved + counts.broken + counts.new : null],
    ['rescues', 'Rescues', rescue.data?.incidents.filter((i) => !['COMMITTED', 'EXHAUSTED', 'CANCELLED', 'REJECTED'].includes(i.state)).length ?? null],
    ['messages', 'Messages', messages.data?.messages.filter((m) => !m.approved).length ?? null],
    ['plan', 'Routes', null],
    ['audit', 'Audit log', audit?.total ?? null],
    ['checks', 'Checks', null],
  ]

  return (
    <div className="app">
      <Header state={state} connected={connected} onReset={reset} onChecks={() => setTab('checks')} busy={busy} />
      <div className="main">
        <aside className="rail" aria-label="Controls">
          {preview
            ? <PreviewPanel preview={preview} scenario={scenario} stale={stale} busy={busy} error={applyError}
                onApply={apply} onDiscard={() => { setPreview(null); setApplyError(null) }} />
            : <DisruptionPanel scenario={scenario} presets={presets} now={now} disabled={!plan} onPreview={(p) => { setPreview(p); setApplyError(null) }} />}

          {plan && (
            <section className="sec" aria-labelledby="how-h">
              <details>
                <summary id="how-h">How this plan is built</summary>
                <p className="small muted" style={{ marginTop: 8 }}>{plan.solver}. Total driving: {Math.round(plan.total_travel)} min.</p>
                <ul>{plan.limits.map((l) => <li key={l}>{l}</li>)}</ul>
              </details>
            </section>
          )}
          {state.applied.length > 0 && (
            <section className="sec" aria-labelledby="done-h">
              <h2 className="h" id="done-h">Applied so far</h2>
              <ol className="small" style={{ margin: 0, paddingLeft: 18 }}>
                {state.applied.map((a) => <li key={a.n}>{a.cause.charAt(0).toUpperCase() + a.cause.slice(1)}</li>)}
              </ol>
            </section>
          )}
        </aside>

        <main className="work">
          <div>
            {preview && <p className="banner" role="status">Previewing a change. Nothing is applied yet.</p>}
            {plan ? (
              <Board scenario={scenario} plan={plan} original={original} showOriginal={showOriginal}
                onToggleOriginal={setShowOriginal} selected={selected} onSelect={setSelected} />
            ) : (
              <div className="board"><p className="empty">No plan yet.</p>
                <button className="btn primary" onClick={() => api.buildPlan('auto')}>Build the plan</button></div>
            )}
          </div>
          <div className="lower">
            <div className="mapwrap">
              {plan && <MapView scenario={scenario} plan={plan} original={original} showOriginal={showOriginal}
                selected={selected} onSelect={setSelected} />}
            </div>
            <div className="tabsarea">
              <div className="tabs" role="tablist">
                {tabs.map(([id, label, n]) => (
                  <button key={id} role="tab" className="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
                    {label}{n ? <span className="n">{n}</span> : null}
                  </button>
                ))}
              </div>
              <div className="tabbody" role="tabpanel">
                {tab === 'compare' && <ComparePanel state={state} />}
                {tab === 'rescues' && <RescuePanel ov={rescue.data} reload={rescue.reload} />}
                {tab === 'messages' && <MessagesPanel />}
                {tab === 'plan' && state.plan && <PlanTable scenario={state.scenario} plan={state.plan} selected={selected} onSelect={setSelected} />}
                {tab === 'audit' && <AuditPanel audit={audit} onVerify={refreshAudit} />}
                {tab === 'checks' && <ChecksPanel report={report} onRun={refreshAudit} />}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
