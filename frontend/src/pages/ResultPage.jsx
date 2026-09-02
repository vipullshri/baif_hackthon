import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, AlertCircle, FileQuestion } from 'lucide-react'
import { api, streamJob } from '../api/client'
import { ResultPanel } from '../components/ResultPanel'
import { ProgressTracker } from '../components/ProgressTracker'
import { EmptyState, LangBadge, Spinner, StatusChip } from '../components/ui'

const TERMINAL = new Set(['completed', 'failed', 'cancelled'])

export function ResultPage({ id, onBack }) {
  const [job, setJob] = useState(null)
  const [state, setState] = useState('loading') // loading | ready | notfound | error
  const stopRef = useRef(null)

  useEffect(() => {
    let active = true
    setState('loading')
    setJob(null)
    stopRef.current?.()

    api.getJob(id)
      .then((data) => {
        if (!active) return
        setJob(data)
        setState('ready')
        // Live-follow jobs that are still running.
        if (!TERMINAL.has(data.status)) {
          stopRef.current = streamJob(id, (j) => active && setJob(j))
        }
      })
      .catch((err) => {
        if (!active) return
        setState(/404|not found/i.test(err.message) ? 'notfound' : 'error')
      })

    return () => {
      active = false
      stopRef.current?.()
    }
  }, [id])

  const back = (
    <button type="button" onClick={onBack} className="btn-ghost">
      <ArrowLeft className="w-4 h-4" /> Back to Library
    </button>
  )

  if (state === 'loading') {
    return (
      <div>
        <div className="mb-6">{back}</div>
        <div className="grid place-items-center py-24"><Spinner className="w-8 h-8 text-leaf-300" /></div>
      </div>
    )
  }

  if (state === 'notfound') {
    return (
      <div>
        <div className="mb-6">{back}</div>
        <EmptyState icon={FileQuestion} title="Translation not found"
                    subtitle="It may have been deleted or the link is no longer valid." />
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div>
        <div className="mb-6">{back}</div>
        <EmptyState icon={AlertCircle} title="Couldn't load this translation"
                    subtitle="Please try again in a moment." />
      </div>
    )
  }

  const processing = job.status === 'pending' || job.status === 'processing'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        {back}
        <div className="flex items-center gap-2 min-w-0">
          <h2 className="text-xl font-bold truncate max-w-[40vw]">{job.title || 'Translation'}</h2>
          <StatusChip status={job.status} />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <LangBadge code={job.detected_lang || job.source_lang} />
          <span className="text-sand-400/40">{'->'}</span>
          <LangBadge code={job.target_lang} />
        </div>
      </div>

      {processing && (
        <ProgressTracker
          job={job}
          inputType={job.input_type}
          opts={{ tts: job.generate_tts, subs: job.generate_subtitles, burn: job.burn_subtitles }}
        />
      )}

      {job.status === 'failed' && (
        <div className="flex items-start gap-2 rounded-xl bg-red-500/10 border border-red-500/25 px-4 py-3 text-sm text-red-200">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{job.error || 'Translation failed.'}</span>
        </div>
      )}

      {job.status === 'cancelled' && (
        <div className="flex items-start gap-2 rounded-xl bg-white/5 border border-white/15 px-4 py-3 text-sm text-sand-200">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>This job was cancelled.</span>
        </div>
      )}

      {job.status === 'completed' && (
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
  )
}