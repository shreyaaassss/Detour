import { useState } from 'react'
import { api } from '../api'
import { useLive } from '../useRescue'
import { StatusChip } from './ui'

export function MessagesPanel() {
  const { data, reload } = useLive(() => api.messages(), ['state'])
  const [copied, setCopied] = useState<string | null>(null)
  if (!data) return <p className="empty">Loading.</p>
  const list = data.messages
  if (list.length === 0) return <p className="empty">No customer needs a message. When a delivery moves or cannot be made, a draft appears here for you to approve.</p>

  async function copy(id: string, text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(id) } catch { setCopied(null) }
  }

  return (
    <div>
      <p className="small muted" style={{ maxWidth: '64ch', marginBottom: 12 }}>
        Drafts are written from the plan's facts only. Approving records your sign-off in the audit log. Nothing is sent from here:
        copy the text into your messaging tool.
      </p>
      <ul className="feed">
        {list.map((m) => (
          <li key={m.delivery_id}>
            <div className="row"><StatusChip status={m.status} /><b>{m.delivery_id}</b><span className="muted">{m.place}</span></div>
            <p style={{ margin: '6px 0 8px', maxWidth: '64ch' }}>{m.text}</p>
            <div className="row">
              {m.approved
                ? <span className="chip ok">Approved</span>
                : <button className="btn primary" onClick={() => api.approveMessage(m.delivery_id).then(reload)}>Approve message</button>}
              <button className="btn" onClick={() => copy(m.delivery_id, m.text)}>{copied === m.delivery_id ? 'Copied' : 'Copy text'}</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
