import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Wordmark } from '../site/SiteChrome'
import { DemoProvider } from './DemoContext'
import { useDemo } from './store'

const PAGES = [
  { to: '/demo/plan', label: 'Plan', who: 'The day, as planned' },
  { to: '/demo/driver', label: 'Driver', who: 'Ravi reports a breakdown' },
  { to: '/demo/head', label: 'Head of logistics', who: 'Approves who to ask' },
  { to: '/demo/rescue', label: 'Rescue driver', who: 'Accepts or declines' },
  { to: '/demo/changes', label: 'What changed', who: 'Both plans, with reasons' },
  { to: '/demo/dispatcher', label: 'Dispatcher', who: 'Reports other changes' },
] as const

/** Which page the story is waiting on, and the line that sends you there. */
function useNext(): { to: string; text: string; go: string } {
  const d = useDemo()
  const who = d.offer?.driver ?? 'the driver'
  if (d.phase <= 2) return { to: '/demo/driver', text: d.phase === 0 ? 'The day is planned. Next, a driver calls in with a problem.' : 'Ravi is still on the line.', go: 'Go to Driver' }
  if (d.phase === 3) return { to: '/demo/head', text: 'Ravi confirmed the report. The head of logistics now decides who to ask.', go: 'Go to Head of logistics' }
  if (d.phase === 4) return { to: '/demo/rescue', text: `Approved. The offer is on ${who}'s phone, with 60 seconds to answer.`, go: 'Go to Rescue driver' }
  if (!d.seenChanges) return { to: '/demo/changes', text: d.incident?.state === 'COMMITTED' ? 'The rescue is committed and the plan has changed.' : 'Nobody could take it. See what that means for the plan.', go: 'See what changed' }
  return { to: '/demo/dispatcher', text: 'Later that afternoon, the dispatcher reports more changes.', go: 'Go to Dispatcher' }
}

function Shell() {
  const d = useDemo()
  const { pathname } = useLocation()
  const next = useNext()
  const [closed, setClosed] = useState<string | null>(null)
  const done = (to: string) =>
    (to === '/demo/plan' && (d.phase > 0 || pathname !== to)) || (to === '/demo/driver' && d.phase >= 3) || (to === '/demo/head' && d.phase >= 4)
    || (to === '/demo/rescue' && d.phase >= 5) || (to === '/demo/changes' && d.seenChanges)
  // the settled rescue page already carries the one button onward
  const showToast = d.state !== null && pathname !== next.to && closed !== next.to + d.phase && !(pathname === '/demo/rescue' && d.phase === 5)
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  return (
    <div className="demo">
      <header className="sitenav">
        <div className="sitenav-in wide">
          <Wordmark />
          <span className="show-tag">Live demo</span>
          <span className="grow" />
          <button className="show-top" aria-pressed={d.sound} onClick={() => d.setSound(!d.sound)}>{d.sound ? 'Voice on' : 'Voice off'}</button>
          <button className="show-top" onClick={d.restart} disabled={d.busy}>Restart</button>
          <Link to="/" className="show-top as-link">Exit</Link>
        </div>
      </header>

      <div className="demo-body">
        <nav className="dnav" aria-label="Demo pages">
          <p className="dnav-h">One breakdown, six views</p>
          {PAGES.map((p, i) => (
            <NavLink key={p.to} to={p.to} className={({ isActive }) => `dnav-item ${isActive ? 'active' : ''} ${done(p.to) ? 'done' : ''} ${next.to === p.to ? 'next' : ''}`}>
              <span className="n">{done(p.to) ? '✓' : i + 1}</span>
              <span className="t"><b>{p.label}</b><small>{p.who}</small></span>
              {next.to === p.to && pathname !== p.to && <span className="dot" aria-label="Waiting for you" />}
            </NavLink>
          ))}
          <div className="dnav-foot">
            <Link to="/dispatch">Open the full dispatcher</Link>
          </div>
        </nav>

        <main className="demo-main">
          {d.state ? <Outlet /> : <p className="muted">{d.loading}</p>}
          {d.error && (
            <div className="turn sys refuse" role="alert" style={{ marginTop: 16 }}>
              <p className="turn-who">That did not go through</p>
              <p className="turn-big">{d.error}</p>
              <div className="turn-actions"><button className="btn" onClick={d.clearError}>Dismiss</button><button className="btn" onClick={d.restart}>Restart the demo</button></div>
            </div>
          )}
        </main>
      </div>

      {showToast && (
        <div className="dtoast" role="status" key={next.to + d.phase}>
          <span className="dtoast-pulse" aria-hidden="true" />
          <p>{next.text}</p>
          <Link to={next.to} className="pill">{next.go}</Link>
          <button className="dtoast-x" aria-label="Dismiss" onClick={() => setClosed(next.to + d.phase)}>✕</button>
        </div>
      )}
    </div>
  )
}

export default function DemoLayout() {
  return <DemoProvider><Shell /></DemoProvider>
}
