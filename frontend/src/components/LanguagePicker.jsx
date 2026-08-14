import { ArrowLeftRight } from 'lucide-react'

function Select({ value, onChange, options, includeAuto }) {
  return (
    <div className="relative flex-1">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input appearance-none pr-10 cursor-pointer font-medium"
      >
        {includeAuto && <option value="auto">✨ Auto-detect</option>}
        {options.map((l) => (
          <option key={l.code} value={l.code}>
            {l.native} — {l.name}
          </option>
        ))}
      </select>
      <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-sand-300/60"
        viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.17l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
      </svg>
    </div>
  )
}

export function LanguagePicker({ languages, source, target, onSource, onTarget, allowAuto = true }) {
  const swap = () => {
    if (source === 'auto') return
    onSource(target)
    onTarget(source)
  }

  return (
    <div className="flex items-end gap-2">
      <div className="flex-1">
        <div className="label mb-1.5">From</div>
        <Select value={source} onChange={onSource} options={languages} includeAuto={allowAuto} />
      </div>
      <button
        type="button"
        onClick={swap}
        disabled={source === 'auto'}
        title="Swap languages"
        className="btn-ghost !p-3 mb-0.5 disabled:opacity-30"
      >
        <ArrowLeftRight className="w-5 h-5" />
      </button>
      <div className="flex-1">
        <div className="label mb-1.5">To</div>
        <Select value={target} onChange={onTarget} options={languages} includeAuto={false} />
      </div>
    </div>
  )
}