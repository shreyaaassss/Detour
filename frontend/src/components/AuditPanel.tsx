import { hhmm } from '../format'
import type { AuditEntry, AuditView } from '../types'
import { Glyph } from './ui'

const LABEL: Record<string, string> = {
  server_started: 'Server started',
  scenario_loaded: 'Scenario loaded',
  plan_built: 'Plan built',
  plan_rejected: 'Plan rejected by the validator',
  disruption_previewed: 'Change reviewed',
  disruption_applied: 'Change applied',
  disruption_refused: 'Change refused',
  validation_run: 'Validator run',
  audit_log_archived: 'Old audit log archived',
}

function summary(e: AuditEntry): string {
  const d = e.details as Record<string, unknown>
  switch (e.action) {
    case 'disruption_applied': {
      const c = d.counts as Record<string, number> | undefined
      return `${d.cause}${c ? `. Kept ${c.kept}, moved ${c.moved}, broken ${c.broken}${c.new ? `, new ${c.new}` : ''}.` : ''}${d.confirmed_by ? ` Confirmed by ${d.confirmed_by}.` : ''}`
    }
    case 'disruption_previewed': return `${d.cause}`
    case 'disruption_refused': return String(d.reason)
    case 'plan_rejected': return ((d.violations as string[]) ?? []).slice(0, 2).join('; ')
    case 'plan_built': return `${d.mode} plan, ${Math.round(Number(d.total_travel_min))} min of driving${(d.unplaced as unknown[])?.length ? `, ${(d.unplaced as unknown[]).length} undeliverable` : ''}`
    case 'scenario_loaded': return `${d.name}: ${d.vehicles} vehicles, ${d.deliveries} deliveries`
    case 'validation_run': return d.valid ? 'All checks passed' : `${(d.violations as unknown[]).length} problems found`
    default: return ''
  }
}

export function AuditPanel({ audit, onVerify }: { audit: AuditView | null; onVerify: () => void }) {
  if (!audit) return <p className="empty">Loading the audit log.</p>
  const entries = [...audit.entries].reverse()
  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <span className={`chip ${audit.chain.valid ? 'ok' : 'bad'}`}>
          <Glyph name={audit.chain.valid ? 'ok' : 'bad'} size={12} />
          {audit.chain.valid ? `Chain intact, ${audit.total} entries` : `Chain broken at entry ${audit.chain.broken_at}: ${audit.chain.reason}`}
        </span>
        <button className="btn quiet" onClick={onVerify}>Check again</button>
      </div>
      <p className="small muted" style={{ marginBottom: 10, maxWidth: '60ch' }}>
        Every change, refusal and check is recorded with who did it. Each entry is linked to the one before, so an edited or removed entry shows up here.
      </p>
      <ul className="audit" style={{ margin: 0, padding: 0 }}>
        {entries.map((e) => (
          <li key={e.id} className={e.action.endsWith('refused') || e.action === 'plan_rejected' ? 'refused' : ''}>
            <span className="muted">#{e.id}</span>
            <span className="who">{e.actor}<br /><span className="small">{e.sim_time != null ? `plan ${hhmm(e.sim_time)}` : new Date(e.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span></span>
            <span><b>{LABEL[e.action] ?? e.action}</b><br /><span className="muted small">{summary(e)}</span></span>
          </li>
        ))}
      </ul>
    </div>
  )
}
