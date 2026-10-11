import { useState } from 'react'
import { Link } from 'react-router-dom'
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
import { RouteLanes } from '../components/RouteLanes'
import { RescuePanel } from '../components/RescuePanel'
import type { Disruption, ParseInfo, PreviewResult } from '../types'
import { useDetour } from '../useDetour'
import { useLive, useOverview } from '../useRescue'
import { api as rescueApi } from '../api'

type Tab = 'plan' | 'compare' | 'timeline' | 'map' | 'rescues' | 'messages' | 'audit' | 'checks'
const MAIN: Tab[] = ['plan', 'compare']

export default function Dispatch() {
  const { state, presets, audit, connected, error, refresh, refreshAudit } = useDetour()
  const rescue = useOverview()
  const messages = useLive(() => rescueApi.messages(), ['state'])
  const [tab, setTab] = useState<Tab>(() => (new URLSearchParams(location.search).get('tab') as Tab | null) ?? 'plan')
  const [selected, setSelected] = useState<string | null>(null)
  const [showOriginal, setShowOriginal] = useState(true)
  const [pendingPreview, setPreview] = useState<PreviewResult | null>(null)
  const [parse, setParse] = useState<ParseInfo | null>(null)
  const [prefill, setPrefill] = useState<Disruption | null>(null)
  const [busy, setBusy] = useState(false)
  const [more, setMore] = useState(false)
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
      setParse(null)
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
    try { await api.reset(); setPreview(null); setSelected(null); setTab('plan') } finally { setBusy(false) }
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
  const open = rescue.data?.incidents.filter((i) => !['COMMITTED', 'EXHAUSTED', 'CANCELLED', 'REJECTED'].includes(i.state)).length ?? 0
  const tabs: [Tab, string, number | null][] = [
    ['plan', 'Plan', null],
    ['compare', 'What changed', counts ? counts.moved + counts.broken + counts.new : null],
    ['timeline', 'Timeline', null],
    ['map', 'Map', null],
    ['rescues', 'Rescues', open],
    ['messages', 'Messages', messages.data?.messages.filter((m) => !m.approved).length ?? null],
    ['audit', 'Audit log', null],
    ['checks', 'Checks', null],
  ]
  const shown = tabs.filter(([id]) => MAIN.includes(id) || more || id === tab)
  const step = preview ? 3 : state.applied.length > 0 ? 4 : 2
  const STEPS = ['Plan the day', 'Report a change', 'Review and confirm', 'See what changed']

  return (
    <div className="app mvp">
      <Header state={state} connected={connected} onReset={reset} onChecks={() => setTab('checks')} busy={busy} />
      <ol className="stepper" aria-label="Where you are">
        {STEPS.map((t, i) => (
          <li key={t} className={i + 1 < step ? 'past' : i + 1 === step ? 'now' : ''} aria-current={i + 1 === step ? 'step' : undefined}>
            <span>{i + 1}</span>{t}
          </li>
        ))}
      </ol>
      <div className="main">
        <aside className="rail" aria-label="Controls">
          {preview
            ? <PreviewPanel preview={preview} scenario={scenario} stale={stale} busy={busy} error={applyError}
                parse={parse} onApply={apply} onDiscard={() => { setPreview(null); setParse(null); setApplyError(null) }}
                onEdit={() => { setPrefill(parse?.disruption ?? null); setPreview(null); setParse(null) }} />
            : <DisruptionPanel key={prefill ? 'edit' : 'new'} scenario={scenario} presets={presets} now={now} disabled={!plan} prefill={prefill}
                onPreview={(p, info) => { setPreview(p); setParse(info ?? null); setPrefill(null); setApplyError(null); setTab('plan') }} />}
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
          <div className="tabs" role="tablist">
            {shown.map(([id, label, n]) => (
              <button key={id} role="tab" className="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
                {label}{n ? <span className="n">{n}</span> : null}
              </button>
            ))}
            <span className="spacer" />
            {more && <><Link to="/driver" className="small">Driver app</Link><Link to="/head" className="small">Head console</Link></>}
            <button className="btn quiet" aria-expanded={more} onClick={() => setMore(!more)}>{more ? 'Less' : 'More'}</button>
          </div>
          {preview && <p className="banner" role="status">This is a preview of the change. Nothing is applied until you confirm it on the left.</p>}
          <div className="tabbody" role="tabpanel">
            {!plan && (
              <div><p className="empty">No plan yet.</p>
                <button className="btn primary" onClick={() => api.buildPlan('auto')}>Build the plan</button></div>
            )}
            {tab === 'plan' && plan && (
              <>
                <RouteLanes key={`${state.version}-${preview?.preview_id ?? ''}`} scenario={scenario} plan={plan} changes={(preview?.diff ?? diff)?.changes} />
                <section className="how" aria-labelledby="how-h">
                  <h2 className="h" id="how-h">How this plan is built, and its limits</h2>
                  <p>{plan.solver}. Total driving: {Math.round(plan.total_travel)} min.</p>
                  <ul>{plan.limits.map((l) => <li key={l}>{l}</li>)}</ul>
                </section>
                <details className="timetable">
                  <summary>Full timetable: arrival, waiting, service, departure and load at every stop</summary>
                  <PlanTable scenario={scenario} plan={plan} selected={null} onSelect={() => {}} />
                </details>
              </>
            )}
            {tab === 'compare' && <ComparePanel state={state} />}
            {tab === 'timeline' && plan && (
              <Board scenario={scenario} plan={plan} original={original} showOriginal={showOriginal}
                onToggleOriginal={setShowOriginal} selected={selected} onSelect={setSelected} />
            )}
            {tab === 'map' && plan && (
              <div style={{ maxWidth: 720 }}>
                <MapView scenario={scenario} plan={plan} original={original} showOriginal={showOriginal} selected={selected} onSelect={setSelected} />
              </div>
            )}
            {tab === 'rescues' && <RescuePanel ov={rescue.data} reload={rescue.reload} />}
            {tab === 'messages' && <MessagesPanel />}
            {tab === 'audit' && <AuditPanel audit={audit} onVerify={refreshAudit} />}
            {tab === 'checks' && <ChecksPanel report={report} onRun={refreshAudit} />}
          </div>
        </main>
      </div>
    </div>
  )
}
