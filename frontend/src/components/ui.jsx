import { useState } from 'react'
import { Check, Copy, Loader2 } from 'lucide-react'

export function Toggle({ checked, onChange, label, hint, disabled }) {
  return (
    <label className={`flex items-start gap-3 ${disabled ? 'opacity-40' : 'cursor-pointer'}`}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`mt-0.5 h-6 w-11 shrink-0 rounded-full p-0.5 transition-colors duration-200
          ${checked ? 'bg-leaf-500' : 'bg-white/15'}`}
      >
        <span
          className={`block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200
            ${checked ? 'translate-x-5' : 'translate-x-0'}`}
        />
      </button>
      <span>
        <span className="block text-sm font-medium text-sand-100">{label}</span>
        {hint && <span className="block text-xs text-sand-300/60">{hint}</span>}
      </span>
    </label>
  )
}

export function Chip({ children, tone = 'default', className = '' }) {
  const tones = {
    default: 'border-white/10 bg-white/5 text-sand-200',
    leaf: 'border-leaf-500/30 bg-leaf-500/10 text-leaf-200',
    saffron: 'border-saffron-500/30 bg-saffron-500/10 text-saffron-200',
    danger: 'border-red-500/30 bg-red-500/10 text-red-200',
  }
  return <span className={`chip ${tones[tone]} ${className}`}>{children}</span>
}

export function SectionTitle({ eyebrow, title, subtitle }) {
  return (
    <div className="mb-6">
      {eyebrow && (
        <div className="label text-saffron-300/80 mb-2">{eyebrow}</div>
      )}
      <h2 className="text-2xl md:text-3xl font-bold text-balance">{title}</h2>
      {subtitle && <p className="mt-2 text-sand-300/70 max-w-2xl">{subtitle}</p>}
    </div>
  )
}

export function CopyButton({ text, className = '' }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch { /* ignore */ }
  }

  return (
    <button onClick={copy} className={`btn-ghost !py-2 !px-3 text-xs ${className}`} title="Copy">
      {copied ? <Check className="w-4 h-4 text-leaf-300" /> : <Copy className="w-4 h-4" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

export function Spinner({ className = 'w-5 h-5' }) {
  return <Loader2 className={`animate-spin ${className}`} />
}

export function EmptyState({ icon: Icon, title, subtitle, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      {Icon && (
        <div className="mb-4 grid place-items-center w-16 h-16 rounded-2xl glass">
          <Icon className="w-7 h-7 text-leaf-300" />
        </div>
      )}
      <h3 className="text-lg font-semibold">{title}</h3>
      {subtitle && <p className="mt-1 text-sm text-sand-300/60 max-w-sm">{subtitle}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

const LANG_META = {
  en: { label: 'English', native: 'EN' },
  hi: { label: 'Hindi', native: 'हि' },
  mr: { label: 'Marathi', native: 'म' },
  auto: { label: 'Auto-detect', native: '✨' },
}

export function LangBadge({ code }) {
  const m = LANG_META[code] || { label: code, native: code }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg bg-white/5 border border-white/10 px-2 py-1 text-xs">
      <span className="font-deva text-saffron-300">{m.native}</span>
      <span className="text-sand-200">{m.label}</span>
    </span>
  )
}

// Single source of truth for job status -> user-facing label + chip tone.
export function statusLabel(status) {
  switch (status) {
    case 'completed': return { label: 'Completed', tone: 'leaf' }
    case 'failed': return { label: 'Failed', tone: 'danger' }
    case 'cancelled': return { label: 'Cancelled', tone: 'default' }
    case 'pending':
    case 'processing': return { label: 'In progress', tone: 'saffron' }
    default: return { label: status || 'Unknown', tone: 'default' }
  }
}

export function StatusChip({ status }) {
  const { label, tone } = statusLabel(status)
  return <Chip tone={tone}>{label}</Chip>
}