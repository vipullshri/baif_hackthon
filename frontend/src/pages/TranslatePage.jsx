import { useEffect, useRef, useState } from 'react'
import { Type, FileAudio, FileVideo, Sparkles, AlertCircle, Wand2, RotateCcw } from 'lucide-react'
import { api, streamJob } from '../api/client'
import { LanguagePicker } from '../components/LanguagePicker'
import { Dropzone } from '../components/Dropzone'
import { ProgressTracker } from '../components/ProgressTracker'
import { ResultPanel } from '../components/ResultPanel'
import { Toggle, Spinner } from '../components/ui'

const MODES = [
  { id: 'text', label: 'Text', icon: Type },
  { id: 'audio', label: 'Audio', icon: FileAudio },
  { id: 'video', label: 'Video', icon: FileVideo },
]

const SAMPLE = 'The crossbred cow needs vaccination and green fodder every day. BAIF farmers should follow this training for better milk yield.'

export function TranslatePage({ languages, onJobDone }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('auto')
  const [target, setTarget] = useState('hi')
  const [opts, setOpts] = useState({ tts: true, subs: true, burn: false })
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const stopRef = useRef(null)

  useEffect(() => () => stopRef.current?.(), [])

  const reset = () => {
    stopRef.current?.()
    setJob(null)
    setError('')
  }

  const switchMode = (m) => {
    setMode(m)
    setFile(null)
    reset()
  }

  const canSubmit = !busy && (mode === 'text' ? text.trim().length > 0 : !!file)

  async function handleSubmit() {
    reset()
    setBusy(true)
    try {
      if (mode === 'text') {
        const result = await api.translateText({
          text, source_lang: source, target_lang: target, generate_tts: opts.tts,
        })
        setJob(result)
        onJobDone?.()
      } else {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('source_lang', source)
        fd.append('target_lang', target)
        fd.append('generate_tts', String(opts.tts))
        fd.append('generate_subtitles', String(opts.subs))
        fd.append('burn_subtitles', String(mode === 'video' && opts.burn))
        const created = await api.createMediaJob(fd)
        setJob(created)
        if (created.status !== 'completed' && created.status !== 'failed') {
          stopRef.current = streamJob(created.id, (j) => {
            setJob(j)
            if (j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled') {
              setBusy(false)
              onJobDone?.()
            }
          })
          return
        }
        onJobDone?.()
      }
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      if (mode === 'text') setBusy(false)
    }
  }

  async function handleCancel() {
    if (!job?.id) return
    try {
      const updated = await api.cancelJob(job.id)
      setJob(updated)
      if (updated.status === 'cancelled') {
        stopRef.current?.()
        setBusy(false)
      }
    } catch (err) {
      setError(err.message || 'Could not cancel the job')
    }
  }

  const processing = job && (job.status === 'pending' || job.status === 'processing')
  const completed = job && job.status === 'completed'
  const cancelled = job && job.status === 'cancelled'
  const failed = (job && job.status === 'failed') || !!error

  return (
    <div className="grid lg:grid-cols-2 gap-6 items-start">
      {/* --- Input column --- */}
      <div className="card p-6 space-y-5">
        {/* Mode tabs */}
        <div className="flex gap-2 p-1 rounded-2xl bg-ink-900/60 border border-white/10">
          {MODES.map((m) => {
            const Icon = m.icon
            return (
              <button
                key={m.id}
                onClick={() => switchMode(m.id)}
                className={`flex-1 flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium transition
                  ${mode === m.id ? 'bg-leaf-600 text-white shadow-leaf' : 'text-sand-300/70 hover:text-white hover:bg-white/5'}`}
              >
                <Icon className="w-4 h-4" /> {m.label}
              </button>
            )
          })}
        </div>

        {/* Input */}
        {mode === 'text' ? (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="label">Source text</span>
              <button onClick={() => setText(SAMPLE)} className="text-xs text-saffron-300 hover:text-saffron-200 flex items-center gap-1">
                <Wand2 className="w-3.5 h-3.5" /> Use sample
              </button>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={7}
              placeholder="Type or paste text in Marathi, Hindi or English..."
              className="input resize-y font-deva text-base"
            />
          </div>
        ) : (
          <Dropzone mode={mode} file={file} onFile={setFile} onClear={() => setFile(null)} />
        )}

        {/* Languages */}
        <LanguagePicker
          languages={languages}
          source={source}
          target={target}
          onSource={setSource}
          onTarget={setTarget}
          allowAuto={mode !== 'text'}
        />

        {/* Options */}
        <div className="grid sm:grid-cols-2 gap-3 rounded-2xl bg-ink-900/40 border border-white/10 p-4">
          <Toggle checked={opts.tts} onChange={(v) => setOpts({ ...opts, tts: v })}
            label="Voice-over" hint="Text-to-speech in target language" />
          <Toggle checked={opts.subs} onChange={(v) => setOpts({ ...opts, subs: v })}
            label="Subtitles" hint="Generate SRT / VTT" disabled={mode === 'text'} />
          {mode === 'video' && (
            <Toggle checked={opts.burn} onChange={(v) => setOpts({ ...opts, burn: v })}
              label="Burn-in captions" hint="Hard-coded into the video (needs FFmpeg)" />
          )}
        </div>

        <button onClick={handleSubmit} disabled={!canSubmit} className="btn-primary w-full text-base">
          {busy ? <Spinner /> : <Sparkles className="w-5 h-5" />}
          {busy ? 'Translating...' : 'Translate'}
        </button>

        {failed && (
          <div className="flex items-start gap-2 rounded-xl bg-red-500/10 border border-red-500/25 px-4 py-3 text-sm text-red-200">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span className="flex-1">{error || job?.error || 'Translation failed.'}</span>
            <button onClick={handleSubmit} disabled={!canSubmit} className="btn-ghost !py-1 !px-2 text-xs shrink-0">
              <RotateCcw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        )}

        {cancelled && (
          <div className="flex items-start gap-2 rounded-xl bg-white/5 border border-white/15 px-4 py-3 text-sm text-sand-200">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span className="flex-1">Job cancelled.</span>
            <button onClick={handleSubmit} disabled={!canSubmit} className="btn-ghost !py-1 !px-2 text-xs shrink-0">
              <RotateCcw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        )}
      </div>

      {/* --- Output column --- */}
      <div className="space-y-6 lg:sticky lg:top-24">
        {!job && !busy && <IdleHint />}
        {(processing || (busy && !completed && !cancelled)) && (
          <ProgressTracker job={job || { progress: 5, status: 'processing' }} inputType={mode} onCancel={handleCancel} />
        )}
        {completed && (
          <>
            {job.error && (
              <div className="flex items-start gap-2 rounded-xl bg-saffron-500/10 border border-saffron-500/25 px-4 py-3 text-sm text-saffron-100">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{job.error}</span>
              </div>
            )}
            <ResultPanel job={job} />
          </>
        )}
      </div>
    </div>
  )
}

function IdleHint() {
  return (
    <div className="card p-8 text-center relative overflow-hidden deva-watermark">
      <div className="relative z-10">
        <div className="mx-auto mb-4 grid place-items-center w-16 h-16 rounded-2xl bg-saffron-500/10 border border-saffron-500/20 animate-floaty">
          <Sparkles className="w-8 h-8 text-saffron-300" />
        </div>
        <h3 className="text-xl font-bold">Your translation appears here</h3>
        <p className="mt-2 text-sand-300/60 max-w-sm mx-auto">
          Choose text, audio or video, pick your languages, and Bhasha Saathi will transcribe, translate,
          voice and caption it - all on this machine.
        </p>
      </div>
    </div>
  )
}