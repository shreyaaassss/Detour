import { Link } from 'react-router-dom'
import { HeroMap } from './Art'
import { SitePage } from './SiteChrome'

const FEATURES = [
  ['Plans the day', 'Assigns deliveries to vehicles within capacity and time windows. Every stop shows its arrival time and any waiting before a window opens.'],
  ['Replans from where the fleet is', 'A road closure, a vehicle failure or an urgent delivery. Completed stops stay fixed, and a failed vehicle gets no stops after it failed.'],
  ['Explains every change', 'The original and revised plans side by side. Every delivery is kept, moved or broken, with a reason you can give a customer.'],
]
const STEPS = [
  ['The driver reports', 'By voice or text. The system reads it back and waits for a yes. A place it does not know is refused, not guessed.'],
  ['A person approves', 'The engine ranks who can collect the parcels and still deliver on time. The head of logistics chooses who to ask.'],
  ['One driver is asked', 'A 60-second offer on their phone. If they decline or do not answer, the next driver is asked.'],
  ['The plan changes', 'Only once someone accepts. The stranded driver is told help is coming then, and not before.'],
]
const FACTS = [
  ['2 ms', 'to plan the demo day of 5 vehicles and 12 deliveries'],
  ['267', 'automated tests on the planning engine and its checker'],
  ['18,000', 'random disruption sequences tried, every resulting plan valid'],
  ['0', 'changes applied without a person confirming them'],
]
const VIEWS = [
  ['/demo/driver', 'Driver', 'Report a breakdown in your own words and confirm the read-back.'],
  ['/demo/head', 'Head of logistics', 'See who can rescue the parcels in time, and approve who to ask.'],
  ['/demo/rescue', 'Rescue driver', 'Get the offer with a 60-second countdown. Accept or decline.'],
  ['/demo/dispatcher', 'Dispatcher', 'Describe a road closure or urgent delivery and confirm the effect.'],
]

export default function Landing() {
  return (
    <SitePage>
      <section className="hero-dark">
        <div className="hero-in">
          <div className="hero-copy">
            <p className="where-pill dark"><span className="dot-w" /> Fleet and delivery replanning</p>
            <h1 className="display">Replan the day from where the fleet is.</h1>
            <p className="lede">A road slows, a van breaks down, an urgent parcel arrives. DeTour fixes the plan without undoing what is already done, proves the result is valid, and explains every change.</p>
            <div className="ctas">
              <Link to="/demo" className="btn-white">Start the live demo</Link>
              <Link to="/dispatch" className="btn-ghost">Open the dispatcher</Link>
            </div>
          </div>
          <div className="heromap"><HeroMap /></div>
        </div>
      </section>

      <main className="sitemain">
        <section aria-label="In numbers">
          <dl className="facts">
            {FACTS.map(([n, t]) => <div key={t}><dt>{n}</dt><dd>{t}</dd></div>)}
          </dl>
        </section>

        <section aria-labelledby="does-h">
          <h2 id="does-h" className="sh">What it does</h2>
          <div className="cards3">
            {FEATURES.map(([t, d]) => <article key={t} className="fcard"><h3>{t}</h3><p>{d}</p></article>)}
          </div>
        </section>

        <section aria-labelledby="how-h">
          <h2 id="how-h" className="sh">A breakdown, handled in four steps</h2>
          <ol className="steps">
            {STEPS.map(([t, d], i) => <li key={t}><span className="stepn">{i + 1}</span><div><h3>{t}</h3><p>{d}</p></div></li>)}
          </ol>
        </section>

        <section aria-labelledby="views-h">
          <h2 id="views-h" className="sh">One breakdown, seen by everyone involved</h2>
          <div className="cards4">
            {VIEWS.map(([to, t, d]) => (
              <Link key={to} to={to} className="vcard"><h3>{t}</h3><p>{d}</p><span className="details">Open this view</span></Link>
            ))}
          </div>
        </section>
      </main>

      <section className="band">
        <div className="band-in">
          <h2>The engine decides. AI assists. People approve.</h2>
          <p>Plans come from plain, checkable code and are verified by a separate module before they are shown. Language models only read what a person says or types. They never decide.</p>
          <Link to="/demo" className="btn-white">See it handle a breakdown</Link>
        </div>
      </section>
    </SitePage>
  )
}
