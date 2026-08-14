import { useCallback, useEffect, useState } from 'react'
import {
  Type, FileAudio, FileVideo, Trash2, RefreshCw, Library, X, Search, Clock,
} from 'lucide-react'
import { api } from '../api/client'
import { ResultPanel } from '../components/ResultPanel'
import { Chip, EmptyState, LangBadge, Spinner } from '../components/ui'

const ICONS = { text: Type, audio: FileAudio, video: FileVideo }

function timeAgo(iso) {
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return `just now`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return d.toLocaleDateString()
}

export function LibraryPage({ refreshKey }) {
  const [jobs, setJobs] = useState(null)
  const [selected, setSelected] = useState(null)
  const [query, setQuery] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await api.listJobs()
      setJobs(data.items)
    } catch {
      setJobs([])
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const remove = async (e, id) => {
    e.stopPropagation()
    await api.deleteJob(id)
    setJobs((prev) => prev?.filter((j) => j.id !== id))
  }

  const open = async (job) => {
    if (job.status !== 'completed') return
    const full = await api.getJob(job.id)
    setSelected(full)
  }

  const filtered = jobs?.filter((j) =>
    !query || (j.title || '').toLowerCase().includes(query.toLowerCase())
  )

  if (jobs === null) {
    return <div className="grid place-items-center py-24"><Spinner className="w-8 h-8 text-leaf-300" /></div>
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-sand-400/50" />
          <input value={query} onChange={(e) => setQuery(e.target.value)}
                 placeholder="Search library…" className="input pl-10" />
        </div>
        <button onClick={load} className="btn-ghost"><RefreshCw className="w-4 h-4" /> Refresh</button>
        <span className="ml-auto text-sm text-sand-300/60">{filtered.length} item(s)</span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={Library} title="No translations yet"
                    subtitle="Completed translations are saved here for instant reuse, exactly as BAIF requires." />
      ) : (
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((job) => {
            const Icon = ICONS[job.input_type] || Type
            return (
              <button key={job.id} onClick={() => open(job)}
                      className="card p-5 text-left hover:-translate-y-1 hover:shadow-glow transition-all group">
                <div className="flex items-start gap-3">
                  <span className="grid place-items-center w-11 h-11 rounded-xl bg-leaf-500/15 border border-leaf-500/25 shrink-0">
                    <Icon className="w-5 h-5 text-leaf-300" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold truncate">{job.title || 'Untitled'}</div>
                    <div className="flex items-center gap-1.5 mt-0.5 text-xs text-sand-300/50">
                      <Clock className="w-3 h-3" /> {timeAgo(job.created_at)}
                    </div>
                  </div>
                  <span onClick={(e) => remove(e, job.id)}
                        className="opacity-0 group-hover:opacity-100 transition p-1.5 rounded-lg hover:bg-red-500/20 text-red-300">
                    <Trash2 className="w-4 h-4" />
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2 mt-4">
                  <LangBadge code={job.detected_lang || job.source_lang} />
                  <span className="text-sand-400/40">→</span>
                  <LangBadge code={job.target_lang} />
                </div>
                <div className="flex flex-wrap gap-1.5 mt-3">
                  <StatusChip status={job.status} />
                  {job.reused && <Chip tone="saffron"><RefreshCw className="w-3 h-3" /> Reused</Chip>}
                  {job.mock && <Chip>Demo</Chip>}
                </div>
              </button>
            )
          })}
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 bg-black/70 backdrop-blur-sm"
             onClick={() => setSelected(null)}>
          <div className="w-full max-w-3xl max-h-[88vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-end mb-2">
              <button onClick={() => setSelected(null)} className="btn-ghost !p-2.5"><X className="w-5 h-5" /></button>
            </div>
            <ResultPanel job={selected} />
          </div>
        </div>
      )}
    </div>
  )
}

function StatusChip({ status }) {
  const map = {
    completed: ['leaf', 'Completed'],
    processing: ['saffron', 'Processing'],
    pending: ['saffron', 'Queued'],
    failed: ['danger', 'Failed'],
  }
  const [tone, label] = map[status] || ['default', status]
  return <Chip tone={tone}>{label}</Chip>
}