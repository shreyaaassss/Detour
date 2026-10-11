import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CardArt, HeroArt } from './Art'
import { SiteFoot, SiteNav } from './SiteChrome'

const ROLES = [
  { art: 'board' as const, title: 'Dispatcher', to: '/dispatch', text: 'See the whole day on one board. Report a road closure, a vehicle failure or an urgent delivery, preview the change, then confirm it.' },
  { art: 'approve' as const, title: 'Head of logistics', to: '/head', text: 'Get a ranked shortlist of rescue drivers with times and the effect on every other delivery. Approve up to three.' },
  { art: 'phone' as const, title: 'Driver', to: '/driver?as=Meera', text: 'Report a breakdown in your own language, or receive a rescue offer with a 60-second countdown. Accept or decline.' },
]

const CASES = [
  { id: 'fail', label: 'Vehicle breakdown', head: 'A van breaks down with urgent medicine aboard.', text: 'The driver reports it. The head approves a shortlist. The nearest driver who can still make the 15:00 window is asked first. Only when someone accepts does the plan change.', to: '/dispatch' },
  { id: 'road', label: 'Road closure', head: 'A road slows down for two hours.', text: 'Only the legs that leave inside the closure are slower. The rest of the plan stays put, and every delivery is marked kept, moved or broken, with the reason.', to: '/dispatch' },
  { id: 'urgent', label: 'Urgent delivery', head: 'A new priority parcel arrives mid-day.', text: 'It is slotted in where it disturbs the least. Stops already completed never change, and a separate checker proves the new plan is valid.', to: '/dispatch' },
]

const STEPS = [
  ['The driver reports', 'By voice or text, in their own language. The system reads it back and waits for a yes.'],
  ['The head approves', 'A ranked shortlist with arrival times and the cost to other deliveries. Nothing happens until a person decides.'],
  ['One driver is asked', 'A 60-second offer in the app. If nobody answers in time, it moves on to an escalation.'],
  ['The plan changes', 'Only once someone accepts. The stranded driver is then told help is coming, and not before.'],
]

export default function Landing() {
  const [tab, setTab] = useState(CASES[0].id)
  const c = CASES.find((x) => x.id === tab) ?? CASES[0]
  return (
    <div className="site">
      <SiteNav />
      <main className="sitemain">
        <section className="hero">
          <div>
            <p className="where-pill"><span className="dot-b" /> Pune demo fleet · 5 vehicles · 12 deliveries</p>
            <h1 className="display">Replan the day from where the fleet is.</h1>
            <p className="lede">A road slows, a van breaks down, an urgent parcel arrives. DeTour fixes the plan without undoing what is already done, proves the result is valid, and explains every change.</p>
            <div className="ctas">
              <Link to="/dispatch" className="btn-black">Open the dispatcher</Link>
              <a href="#how" className="btn-line">How a rescue works</a>
            </div>
          </div>
          <div className="artpanel"><HeroArt /></div>
        </section>

        <section aria-labelledby="roles-h">
          <h2 id="roles-h" className="sh">Pick a screen</h2>
          <div className="cards3">
            {ROLES.map((r) => (
              <article key={r.title} className="scard">
                <div>
                  <h3>{r.title}</h3>
                  <p>{r.text}</p>
                  <Link to={r.to} className="details">Open</Link>
                </div>
                <CardArt kind={r.art} />
              </article>
            ))}
          </div>
        </section>

        <section id="how" aria-labelledby="how-h">
          <h2 id="how-h" className="sh">A breakdown, step by step</h2>
          <ol className="steps">
            {STEPS.map(([t, d], i) => (
              <li key={t}><span className="stepn">{i + 1}</span><div><h3>{t}</h3><p>{d}</p></div></li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="try-h">
          <h2 id="try-h" className="sh">What it handles</h2>
          <div className="tabstrip" role="tablist" aria-label="Disruptions">
            {CASES.map((x) => (
              <button key={x.id} role="tab" aria-selected={tab === x.id} onClick={() => setTab(x.id)}>{x.label}</button>
            ))}
          </div>
          <div className="casepanel">
            <h3>{c.head}</h3>
            <p>{c.text}</p>
            <Link to={c.to} className="btn-black">Try it</Link>
          </div>
        </section>

        <section className="rule">
          <h2 className="sh">The engine decides. AI assists. People approve.</h2>
          <p className="lede">Plans come from plain, checkable code and are verified by a separate module before they are shown. Language models only read what a person types. They never decide.</p>
        </section>
      </main>
      <SiteFoot />
    </div>
  )
}
