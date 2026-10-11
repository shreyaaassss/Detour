import { useSecondsLeft } from '../useRescue'

interface Props { deadline: number | null | undefined; total: number; label: string; size?: number }

/** A ring that empties as the server's timer runs down. */
export function Countdown({ deadline, total, label, size = 96 }: Props) {
  const left = useSecondsLeft(deadline)
  if (left == null) return null
  const r = size / 2 - 7
  const circ = 2 * Math.PI * r
  const frac = Math.min(1, left / total)
  const urgent = left <= 10
  return (
    <div role="timer" aria-label={`${Math.ceil(left)} ${label}`} style={{ display: 'inline-grid', placeItems: 'center', position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth="6" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={urgent ? 'var(--broken)' : 'var(--ink)'} strokeWidth="6"
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - frac)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset 0.25s linear' }} />
      </svg>
      <div style={{ position: 'absolute', textAlign: 'center', lineHeight: 1 }}>
        <div className="clock" style={{ fontSize: size * 0.34, color: urgent ? 'var(--broken)' : 'var(--ink)' }}>{Math.ceil(left)}</div>
        <div style={{ fontSize: Math.max(10, size * 0.11), color: 'var(--ink-2)', marginTop: 2 }}>{label}</div>
      </div>
    </div>
  )
}
