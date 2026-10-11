/* The landing page's one visual: a dark map render of the fictional demo network, drawn here (no map service is used). */

const MINOR = Array.from({ length: 15 }, (_, i) => -160 + i * 62)
const MAJOR = [-40, 210, 458, 706]

const PLACES: [number, number, string, 'l' | 'r'][] = [
  [300, 372, 'Swargate Depot', 'r'],
  [452, 318, 'Hadapsar', 'r'],
  [150, 276, 'Kothrud Clinic', 'l'],
  [206, 150, 'Aundh', 'r'],
  [430, 132, 'Viman Nagar', 'r'],
  [528, 196, 'Kharadi', 'l'],
  [352, 262, 'Camp', 'r'],
]

const RESCUE = 'M430 132 L404 196 L452 318 L352 262 L236 300 L150 276'

export function HeroMap() {
  return (
    <svg viewBox="0 0 600 500" role="img" className="art" preserveAspectRatio="xMidYMid slice"
      aria-label="A dark map of the demo delivery network. One van has broken down at Hadapsar and another drives over to collect its parcels and deliver them to Kothrud Clinic.">
      <rect width="600" height="500" fill="#0c111b" />
      <g transform="rotate(-17 300 250)">
        <path d="M-80 420 C 120 380, 260 470, 420 430 S 640 360, 720 400" fill="none" stroke="#0a1a2c" strokeWidth="46" />
        <path d="M-80 420 C 120 380, 260 470, 420 430 S 640 360, 720 400" fill="none" stroke="#0d2136" strokeWidth="1.5" />
        {MINOR.map((v) => <line key={`h${v}`} x1="-200" x2="800" y1={v} y2={v} stroke="#161e2c" strokeWidth="2" />)}
        {MINOR.map((v) => <line key={`v${v}`} y1="-200" y2="700" x1={v + 120} x2={v + 120} stroke="#161e2c" strokeWidth="2" />)}
        {MAJOR.map((v) => <line key={`mh${v}`} x1="-200" x2="800" y1={v * 0.62 + 40} y2={v * 0.62 + 40} stroke="#1f2a3c" strokeWidth="7" />)}
        {MAJOR.map((v) => <line key={`mv${v}`} y1="-200" y2="700" x1={v} x2={v} stroke="#1f2a3c" strokeWidth="7" />)}
        <path d="M-120 60 C 140 120, 300 40, 760 180" fill="none" stroke="#243146" strokeWidth="10" />
        <rect x="250" y="120" width="96" height="58" rx="6" fill="#0f1d1c" />
        <rect x="520" y="300" width="70" height="92" rx="6" fill="#0f1d1c" />
      </g>

      {/* the other routes of the day, quiet */}
      <g fill="none" stroke="#566171" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" opacity="0.9">
        <path d="M300 372 L206 150" />
        <path d="M300 372 L528 196" />
        <path d="M300 372 L352 262 L430 132" strokeDasharray="2 7" />
      </g>

      {/* the rescue: from Viman Nagar to the broken-down van, then on to the clinic */}
      <path d={RESCUE} fill="none" stroke="#9dcdd6" strokeWidth="9" opacity="0.14" strokeLinejoin="round" strokeLinecap="round" />
      <path d={RESCUE} className="map-route" pathLength={1} fill="none" stroke="#9dcdd6" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      <circle r="6" fill="#ffffff" className="map-van" style={{ offsetPath: `path('${RESCUE}')` }} />

      {PLACES.map(([x, y, name, side]) => (
        <g key={name}>
          <circle cx={x} cy={y} r="4.5" fill="#0c111b" stroke="#a0aaba" strokeWidth="1.6" />
          <text x={side === 'r' ? x + 10 : x - 10} y={y + 4} textAnchor={side === 'r' ? 'start' : 'end'} className="map-label">{name}</text>
        </g>
      ))}
      <rect x="292" y="364" width="16" height="16" transform="rotate(45 300 372)" fill="#ffffff" />

      {/* the breakdown */}
      <g className="map-pulse"><circle cx="452" cy="318" r="15" fill="none" stroke="#ffffff" strokeWidth="1.5" /></g>
      <circle cx="452" cy="318" r="9" fill="#ffffff" />
      <path d="M448 314l8 8M456 314l-8 8" stroke="#0c111b" strokeWidth="2.2" strokeLinecap="round" />

      {/* what the dispatcher reads */}
      <g transform="translate(24 24)">
        <rect width="252" height="92" rx="12" fill="#121927" stroke="#243146" />
        <text x="16" y="28" className="map-card-k">Rescue committed</text>
        <text x="16" y="52" className="map-card-v">D7 to Kothrud Clinic</text>
        <text x="16" y="74" className="map-card-s">Due 15:00. Arrives 14:50 with Meera.</text>
      </g>
    </svg>
  )
}
