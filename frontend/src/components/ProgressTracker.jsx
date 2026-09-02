import { motion } from 'framer-motion'
import { Check, Loader2, Mic, Languages, Volume2, Captions, Film, Sparkles, X } from 'lucide-react'

// Ordered pipeline stages. Each maps to the backend `stage` strings it covers.
// `needs` decides whether the step is shown for the current mode + chosen options.
const STAGES = [
  { key: 'transcribe', label: 'Transcribe speech', icon: Mic,
    match: ['starting', 'extracting-audio', 'transcribing'], needs: (t) => t !== 'text' },
  { key: 'translate', label: 'Translate + glossary', icon: Languages,
    match: ['translating', 'translated'], needs: () => true },
  { key: 'voice', label: 'Generate voice-over', icon: Volume2,
    match: ['synthesizing-voice'], needs: (t, o) => o.tts },
  { key: 'subs', label: 'Build subtitles', icon: Captions,
    match: ['building-subtitles'], needs: (t, o) => t !== 'text' && o.subs },
  { key: 'dub', label: 'Dub video', icon: Film,
    match: ['dubbing-video'], needs: (t, o) => t === 'video' && o.tts },
  { key: 'captions', label: 'Burn captions', icon: Film,
    match: ['burning-captions'], needs: (t, o) => t === 'video' && o.burn },
]

// Flat order of backend stage strings, used to decide done/active/pending.
const STAGE_ORDER = [
  'starting', 'extracting-audio', 'transcribing', 'translating', 'translated',
  'synthesizing-voice', 'building-subtitles', 'dubbing-video', 'burning-captions', 'done',
]

export function ProgressTracker({ job, inputType, opts = { tts: true, subs: true, burn: false }, onCancel }) {
  const progress = job?.progress ?? 0
  const stage = job?.stage
  const completed = job?.status === 'completed'
  const failed = job?.status === 'failed'
  const cancelling = stage === 'cancelling'
  const currentIdx = STAGE_ORDER.indexOf(stage)

  const visible = STAGES.filter((s) => s.needs(inputType, opts))
  const activeStep = visible.find((s) => s.match.includes(stage))
  const currentLabel = completed ? 'Translation complete'
    : cancelling ? 'Cancelling…'
    : activeStep ? `${activeStep.label}…`
    : 'Working on your translation…'

  return (
    <div className="card p-6 animate-fadeUp">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 font-semibold">
          <Sparkles className="w-5 h-5 text-saffron-300" />
          {currentLabel}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm tabular-nums text-sand-300/70">{progress}%</span>
          {onCancel && job?.status === 'processing' && (
            <button
              onClick={onCancel}
              disabled={cancelling}
              className="btn-ghost !p-1.5 text-sand-300/70 hover:text-red-200 disabled:opacity-50"
              title="Cancel job"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="h-2.5 w-full rounded-full bg-white/10 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundImage: 'linear-gradient(90deg,#379046,#ffc171,#fe8316)' }}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ ease: 'easeOut', duration: 0.5 }}
        />
      </div>

      <div className="mt-5 grid gap-2.5">
        {visible.map((s) => {
          // A step's position is the earliest backend stage it covers.
          const stepIdx = Math.min(...s.match.map((m) => STAGE_ORDER.indexOf(m)))
          const done = completed || (currentIdx >= 0 && currentIdx > stepIdx)
          const active = !done && !failed && s.match.includes(stage)
          const Icon = s.icon
          return (
            <div key={s.key} className="flex items-center gap-3">
              <span className={`grid place-items-center w-8 h-8 rounded-xl border transition
                ${done ? 'bg-leaf-500/20 border-leaf-500/40 text-leaf-200'
                  : active ? 'bg-saffron-500/15 border-saffron-500/40 text-saffron-200'
                  : 'bg-white/5 border-white/10 text-sand-400/50'}`}>
                {done ? <Check className="w-4 h-4" />
                  : active ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <Icon className="w-4 h-4" />}
              </span>
              <span className={`text-sm ${done ? 'text-sand-100' : active ? 'text-saffron-100' : 'text-sand-300/50'}`}>
                {s.label}
              </span>
            </div>
          )
        })}
      </div>

      {job?.mock && (
        <p className="mt-5 text-xs text-saffron-200/80 bg-saffron-500/10 border border-saffron-500/20 rounded-xl px-3 py-2">
          Demo mode: results are simulated. Enable the open-source models to produce real output.
        </p>
      )}
    </div>
  )
}