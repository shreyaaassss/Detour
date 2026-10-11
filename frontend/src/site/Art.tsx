/* Flat editorial illustrations. The interface stays black and white; the colour lives here, as in the design system. */

export function HeroArt() {
  return (
    <svg viewBox="0 0 480 400" role="img" aria-label="A delivery route with a broken-down van and a rescue van taking over its parcels" className="art">
      <rect width="480" height="400" fill="#f1e6d4" />
      <rect x="0" y="300" width="480" height="100" fill="#e7d6b8" />
      <path d="M30 330 C 120 250, 190 330, 260 250 S 400 170, 450 110" fill="none" stroke="#fff" strokeWidth="26" strokeLinecap="round" />
      <path d="M30 330 C 120 250, 190 330, 260 250 S 400 170, 450 110" fill="none" stroke="#2a6f7f" strokeWidth="4" strokeLinecap="round" strokeDasharray="2 12" />
      <path d="M90 90 C 150 140, 240 120, 300 60" fill="none" stroke="#fff" strokeWidth="18" strokeLinecap="round" />
      <g>
        <rect x="60" y="262" width="92" height="52" rx="6" fill="#c4481a" />
        <rect x="124" y="274" width="34" height="40" rx="5" fill="#a63a14" />
        <rect x="130" y="280" width="22" height="14" rx="2" fill="#cfe7ec" />
        <circle cx="86" cy="318" r="12" fill="#222" /><circle cx="86" cy="318" r="5" fill="#bbb" />
        <circle cx="140" cy="318" r="12" fill="#222" /><circle cx="140" cy="318" r="5" fill="#bbb" />
        <path d="M90 250 l12 -22 l12 22" fill="none" stroke="#222" strokeWidth="5" strokeLinejoin="round" />
        <path d="M70 216 l16 -16 M86 216 l-16 -16" stroke="#222" strokeWidth="5" strokeLinecap="round" />
      </g>
      <g>
        <rect x="300" y="170" width="92" height="52" rx="6" fill="#276ef1" />
        <rect x="364" y="182" width="34" height="40" rx="5" fill="#1d55bd" />
        <rect x="370" y="188" width="22" height="14" rx="2" fill="#dbe8ff" />
        <circle cx="326" cy="226" r="12" fill="#222" /><circle cx="326" cy="226" r="5" fill="#bbb" />
        <circle cx="380" cy="226" r="12" fill="#222" /><circle cx="380" cy="226" r="5" fill="#bbb" />
        <rect x="312" y="150" width="22" height="20" rx="2" fill="#e9b872" /><rect x="338" y="154" width="18" height="16" rx="2" fill="#d79c4e" />
      </g>
      <g fill="#222"><circle cx="238" cy="262" r="9" /><circle cx="238" cy="262" r="3" fill="#f1e6d4" /></g>
      <path d="M160 270 C 210 230, 250 240, 296 200" fill="none" stroke="#222" strokeWidth="3" strokeDasharray="6 7" strokeLinecap="round" />
      <path d="M290 196 l12 3 -6 9z" fill="#222" />
      <g transform="translate(400 60)"><rect width="56" height="56" rx="6" fill="#222" /><path d="M14 30 l10 10 18-22" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" /></g>
    </svg>
  )
}

export function CardArt({ kind }: { kind: 'board' | 'approve' | 'phone' }) {
  return (
    <svg viewBox="0 0 120 100" aria-hidden="true" className="cardart">
      {kind === 'board' && (<g>
        <rect x="8" y="14" width="104" height="72" rx="6" fill="#fff" />
        <rect x="16" y="26" width="52" height="9" rx="3" fill="#2a6f7f" /><rect x="72" y="26" width="30" height="9" rx="3" fill="#e9b872" />
        <rect x="16" y="44" width="30" height="9" rx="3" fill="#c4481a" /><rect x="50" y="44" width="52" height="9" rx="3" fill="#276ef1" />
        <rect x="16" y="62" width="64" height="9" rx="3" fill="#2a6f7f" />
        <path d="M60 18 V82" stroke="#222" strokeWidth="2" strokeDasharray="3 3" />
      </g>)}
      {kind === 'approve' && (<g>
        <rect x="14" y="12" width="92" height="76" rx="6" fill="#fff" />
        <circle cx="34" cy="34" r="9" fill="#e9b872" /><rect x="50" y="29" width="46" height="10" rx="3" fill="#ddd" />
        <circle cx="34" cy="62" r="9" fill="#2a6f7f" /><rect x="50" y="57" width="30" height="10" rx="3" fill="#ddd" />
        <path d="M84 62 l6 6 12-14" fill="none" stroke="#222" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      </g>)}
      {kind === 'phone' && (<g>
        <rect x="34" y="6" width="52" height="88" rx="9" fill="#222" />
        <rect x="39" y="16" width="42" height="68" rx="3" fill="#fff" />
        <rect x="44" y="24" width="32" height="8" rx="2" fill="#ddd" /><rect x="44" y="38" width="32" height="8" rx="2" fill="#ddd" />
        <rect x="44" y="56" width="32" height="12" rx="3" fill="#222" /><rect x="44" y="72" width="32" height="8" rx="3" fill="#276ef1" />
      </g>)}
    </svg>
  )
}
