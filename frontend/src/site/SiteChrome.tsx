import { Link } from 'react-router-dom'

export function Wordmark() {
  return (
    <Link to="/" className="wordmark" aria-label="DeTour home">
      <svg viewBox="0 0 26 26" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 21h6a4 4 0 004-4V9a4 4 0 014-4h6" />
        <path d="M20 2l3 3-3 3" />
      </svg>
      DeTour
    </Link>
  )
}

export function SiteNav() {
  return (
    <header className="sitenav">
      <div className="sitenav-in">
        <Wordmark />
        <nav aria-label="Screens" className="sitelinks">
          <Link to="/dispatch">Dispatcher</Link>
          <Link to="/head">Head of logistics</Link>
          <Link to="/driver?as=Meera">Driver</Link>
        </nav>
        <span className="grow" />
        <Link to="/dispatch" className="pill">Open the demo</Link>
      </div>
    </header>
  )
}

export function SiteFoot() {
  return (
    <footer className="sitefoot">
      <div className="sitefoot-in">
        <div className="footgrid">
          <div>
            <Wordmark />
            <p>Replan the day from where the fleet actually is, with a person in charge.</p>
          </div>
          <div>
            <h3>Screens</h3>
            <ul>
              <li><Link to="/dispatch">Dispatcher</Link></li>
              <li><Link to="/head">Head of logistics</Link></li>
              <li><Link to="/driver?as=Ravi">Stranded driver</Link></li>
              <li><Link to="/driver?as=Meera">Rescue driver</Link></li>
            </ul>
          </div>
          <div>
            <h3>The rule</h3>
            <ul>
              <li>The engine decides.</li>
              <li>AI assists.</li>
              <li>People approve.</li>
            </ul>
          </div>
          <div>
            <h3>About</h3>
            <ul>
              <li>VORTEXA 3.0</li>
              <li>Problem S-01: ReRoute</li>
              <li>All data is fictional.</li>
            </ul>
          </div>
        </div>
      </div>
    </footer>
  )
}
