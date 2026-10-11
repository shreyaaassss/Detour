import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { SitePage } from './SiteChrome'

const TOPICS = [['question', 'A question'], ['feedback', 'Feedback on the demo'], ['pilot', 'Trying it with a real fleet'], ['other', 'Something else']]

export default function Contact() {
  const [form, setForm] = useState({ name: '', email: '', topic: 'question', message: '' })
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const r = await api.contact({ ...form, name: form.name.trim(), email: form.email.trim(), message: form.message.trim() })
      setSent(r.id)
    } catch (err) {
      setError(err instanceof ApiError
        ? (err.status === 422 ? 'Please check your email address, and write at least a few words.' : err.message)
        : 'Could not reach the server. It may be waking up: try again in a moment.')
    } finally { setBusy(false) }
  }

  return (
    <SitePage>
      <main className="sitemain narrow">
        <section className="split">
          <div>
            <p className="where-pill"><span className="dot-b" /> Contact</p>
            <h1 className="display">Talk to us.</h1>
            <p className="lede">Questions about how DeTour plans, feedback on the demo, or a fleet you would like to try it on.</p>
            <ul className="plainlist">
              <li>Run a fleet? Tell us how many vehicles and what goes wrong most often.</li>
              <li>Found something wrong in the demo? Say what you did and what you saw.</li>
              <li>Judging VORTEXA 3.0? The <Link to="/demo">live demo</Link> walks through the whole problem.</li>
            </ul>
          </div>

          {sent !== null ? (
            <div className="formcard done" role="status">
              <h2>Message received.</h2>
              <p>Thank you, {form.name.split(' ')[0]}. Your message is saved as number {sent}, with {form.email} as the address to reply to.</p>
              <button className="btn-line" onClick={() => { setSent(null); setForm({ ...form, message: '' }) }}>Send another</button>
            </div>
          ) : (
            <form className="formcard" onSubmit={submit} noValidate={false}>
              <label>Your name<input type="text" required maxLength={80} value={form.name} onChange={set('name')} autoComplete="name" /></label>
              <label>Email<input type="email" required maxLength={120} value={form.email} onChange={set('email')} autoComplete="email" /></label>
              <label>What is it about?
                <select value={form.topic} onChange={set('topic')}>{TOPICS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
              </label>
              <label>Message<textarea required minLength={5} maxLength={2000} rows={6} value={form.message} onChange={set('message')} /></label>
              {error && <p className="formerr" role="alert">{error}</p>}
              <button className="btn-black" type="submit" disabled={busy}>{busy ? 'Sending…' : 'Send message'}</button>
              <p className="formnote">This is a hackathon prototype. Your message is kept on our demo server for the team to read, and is not shared with anyone else.</p>
            </form>
          )}
        </section>
      </main>
    </SitePage>
  )
}
