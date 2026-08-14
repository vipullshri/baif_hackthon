// Brand mark: a bridge ("setu") arc over a river, echoing "connecting languages".
export function BridgeIcon({ className = 'w-9 h-9' }) {
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="bsGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#379046" />
          <stop offset="100%" stopColor="#205d2e" />
        </linearGradient>
      </defs>
      <rect width="100" height="100" rx="26" fill="url(#bsGrad)" />
      <path d="M18 66 C 36 38, 64 38, 82 66" stroke="#fe8316" strokeWidth="7.5" fill="none" strokeLinecap="round" />
      <path d="M18 66 L18 76 M82 66 L82 76" stroke="#fe8316" strokeWidth="7.5" strokeLinecap="round" />
      <path d="M34 50 L34 62 M50 45 L50 62 M66 50 L66 62" stroke="#dcf0de" strokeWidth="4.5" strokeLinecap="round" opacity="0.9" />
      <path d="M14 78 Q 50 70, 86 78" stroke="#8ecb97" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.7" />
    </svg>
  )
}

export function Logo({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <div className="animate-floaty drop-shadow-lg">
        <BridgeIcon />
      </div>
      <div className="leading-none">
        <div className="text-xl font-extrabold tracking-tight">
          <span className="gradient-text">Bhasha</span>
          <span className="text-white">Setu</span>
        </div>
        {!compact && (
          <div className="font-deva text-[11px] text-sand-300/70 mt-1 tracking-wide">
            भाषासेतु • Language Bridge
          </div>
        )}
      </div>
    </div>
  )
}