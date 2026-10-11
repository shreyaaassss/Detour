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
        <span className="grow" />
        <Link to="/demo" className="pill">Start the demo</Link>
      </div>
    </header>
  )
}

export function SiteFoot() {
  return (
    <footer className="sitefoot">
      <div className="sitefoot-in">
        <div className="footline">
          <Wordmark />
          <p>The engine decides. AI assists. People approve. VORTEXA 3.0, problem S-01. All data is fictional.</p>
        </div>
      </div>
    </footer>
  )
}
