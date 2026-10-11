import { Link } from 'react-router-dom'
import { HeroMap } from './Art'
import { SiteFoot, SiteNav } from './SiteChrome'

const STEPS = [
  ['Plan the day', 'Deliveries are assigned to vehicles within capacity and time windows. Every stop shows its arrival time and any waiting.'],
  ['Report a change', 'A road closure, a vehicle failure or an urgent delivery, typed in plain words or picked from a form. You confirm before anything changes.'],
  ['See what changed', 'The original and revised plans side by side. Every delivery is kept, moved or broken, with a reason you can give a customer.'],
]

export default function Landing() {
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
            </div>
          </div>
          <div className="mapframe"><HeroMap /></div>
        </section>

        <section aria-labelledby="what-h">
          <h2 id="what-h" className="sh">Three things, done properly</h2>
          <ol className="steps three">
            {STEPS.map(([t, d], i) => (
              <li key={t}><span className="stepn">{i + 1}</span><div><h3>{t}</h3><p>{d}</p></div></li>
            ))}
          </ol>
        </section>
      </main>
      <SiteFoot />
    </div>
  )
}
