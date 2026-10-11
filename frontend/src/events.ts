// One shared event stream for every screen on the page.
type Handler = (type: string, data: Record<string, unknown>) => void
type Status = (connected: boolean) => void

const TYPES = ['hello', 'state', 'audit', 'incident', 'notify']
const handlers = new Set<Handler>()
const statuses = new Set<Status>()
let es: EventSource | null = null
let connected = false

function setConnected(v: boolean) {
  connected = v
  statuses.forEach((s) => s(v))
}

function open() {
  if (es) return
  es = new EventSource('/events')
  es.onopen = () => setConnected(true)
  es.onerror = () => setConnected(false) // the browser reconnects by itself
  for (const t of TYPES) {
    es.addEventListener(t, (e) => {
      let data: Record<string, unknown> = {}
      try { data = JSON.parse((e as MessageEvent).data) } catch { /* ignore a malformed event */ }
      if (t === 'hello') setConnected(true)
      handlers.forEach((h) => h(t, data))
    })
  }
}

// Browsers allow only about six connections to one server across all tabs, and every open page holds one
// stream. A hidden tab lets its stream go and picks it up again (and refreshes) when it is shown.
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (es) { es.close(); es = null; setConnected(false) }
    } else if (handlers.size > 0) {
      open()
    }
  })
}

export function subscribe(h: Handler, onStatus?: Status): () => void {
  handlers.add(h)
  if (onStatus) { statuses.add(onStatus); onStatus(connected) }
  open()
  return () => {
    handlers.delete(h)
    if (onStatus) statuses.delete(onStatus)
    if (handlers.size === 0 && es) { es.close(); es = null; setConnected(false) }
  }
}
