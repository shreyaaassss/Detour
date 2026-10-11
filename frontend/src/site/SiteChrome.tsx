import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'

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
        <nav aria-label="Site" className="sitelinks">
          <NavLink to="/" end>Product</NavLink>
          <NavLink to="/demo">Live demo</NavLink>
          <NavLink to="/dispatch">Dispatcher</NavLink>
          <NavLink to="/about">About</NavLink>
          <NavLink to="/contact">Contact</NavLink>
        </nav>
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
        <div className="footgrid">
          <div>
            <Wordmark />
            <p>Replan the day from where the fleet is, with a person in charge of every decision.</p>
          </div>
          <div>
            <h3>Product</h3>
            <ul>
              <li><Link to="/demo">Live demo</Link></li>
              <li><Link to="/dispatch">Dispatcher</Link></li>
              <li><Link to="/demo/driver">Driver view</Link></li>
              <li><Link to="/demo/head">Head of logistics view</Link></li>
            </ul>
          </div>
          <div>
            <h3>Company</h3>
            <ul>
              <li><Link to="/about">About us</Link></li>
              <li><Link to="/contact">Contact</Link></li>
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
        </div>
        <p className="footnote">Built for VORTEXA 3.0, problem S-01 (ReRoute). All fleet data on this site is fictional.</p>
      </div>
    </footer>
  )
}

/** The frame every public page shares. */
export function SitePage({ children }: { children: ReactNode }) {
  return <div className="site"><SiteNav />{children}<SiteFoot /></div>
}
