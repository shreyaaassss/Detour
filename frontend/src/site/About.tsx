import { Link } from 'react-router-dom'
import { SitePage } from './SiteChrome'

const VALUES = [
  ['Checkable before clever', 'The planner is a heuristic we can explain: cheapest insertion, then local search. A separate validator that shares no code with it re-times every route before a plan is shown.'],
  ['People stay in charge', 'A typed report is only a proposal until the dispatcher confirms it. A rescue is only offered once the head of logistics approves, and only committed once a driver accepts.'],
  ['Honest about limits', 'The solver does not promise the best possible plan. Travel times are simulated. When a delivery cannot be made, the system says so and gives the reason.'],
]
const LIMITS = [
  'The solver is a heuristic. It finds good plans quickly, not provably optimal ones.',
  'Travel times come from a simulated matrix. No live map or GPS service is used.',
  'The demo keeps its state in one server process and is shared by everyone using it.',
  'It has been tested on a fictional fleet, not yet with a real operator.',
]

export default function About() {
  return (
    <SitePage>
      <main className="sitemain narrow">
        <section>
          <p className="where-pill"><span className="dot-b" /> About us</p>
          <h1 className="display">We built the tool a dispatcher needs at 2 pm, when the morning plan stops being true.</h1>
          <p className="lede">DeTour began as an answer to one problem statement at VORTEXA 3.0: ReRoute, dynamic fleet and delivery replanning. Planning a delivery day is a solved problem. Repairing it halfway through, without breaking what is already done, is where dispatchers are left with a spreadsheet and experience.</p>
        </section>

        <section aria-labelledby="believe-h">
          <h2 id="believe-h" className="sh">What we believe</h2>
          <div className="cards3">
            {VALUES.map(([t, d]) => <article key={t} className="fcard"><h3>{t}</h3><p>{d}</p></article>)}
          </div>
        </section>

        <section aria-labelledby="built-h" className="split">
          <div>
            <h2 id="built-h" className="sh">How it is built</h2>
            <p className="body">A planning engine in Python decides every route. An independent validator checks capacity, time windows, completed stops and failed vehicles on every plan. A language model reads typed and spoken reports into a fixed form, and a strict rule reader cross-checks it. The screens are React and update live.</p>
            <p className="body">Nothing here needs a paid service. With every outside service switched off, the rule reader works alone and the whole demo still runs.</p>
          </div>
          <div>
            <h2 className="sh">What it does not do yet</h2>
            <ul className="plainlist">{LIMITS.map((l) => <li key={l}>{l}</li>)}</ul>
          </div>
        </section>

        <section aria-labelledby="team-h">
          <h2 id="team-h" className="sh">The team</h2>
          <p className="body">We are a team of undergraduate engineering students who built DeTour in a 12-hour hackathon. We would like to hear from dispatchers and fleet operators about what a real day looks like.</p>
          <div className="ctas" style={{ marginTop: 20 }}>
            <Link to="/contact" className="btn-black">Get in touch</Link>
            <Link to="/demo" className="btn-line">Start the live demo</Link>
          </div>
        </section>
      </main>
    </SitePage>
  )
}
