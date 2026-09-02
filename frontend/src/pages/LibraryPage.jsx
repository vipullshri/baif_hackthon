import { useCallback, useEffect, useState } from 'react'
import {
  Type, FileAudio, FileVideo, Trash2, RefreshCw, Library, Search, Clock,
} from 'lucide-react'
import { api } from '../api/client'
import { Chip, EmptyState, LangBadge, Spinner, StatusChip } from '../components/ui'

const ICONS = { text: Type, audio: FileAudio, video: FileVideo }

function timeAgo(iso) {
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return d.toLocaleDateString()
}

export function LibraryPage({ refreshKey, onOpenResult }) {
  const [jobs, setJobs] = useState(null)
  const [query, setQuery] = useState('')
  const [confirmId, setConfirmId] = useState(null)

  const load = useCallback(async () => {
    try {
      const data = await api.listJobs()
      setJobs(data.items)
    } catch {
      setJobs([])
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  const remove = async (id) => {
    setConfirmId(null)
    const prev = jobs
    setJobs((list) => list?.filter((j) => j.id !== id)) // optimistic
    try {
      await api.deleteJob(id)
    } catch {
      setJobs(prev) // rollback on failure
    }
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
        <button type="button" onClick={load} className="btn-ghost"><RefreshCw className="w-4 h-4" /> Refresh</button>
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
              <div key={job.id} className="card p-5 flex flex-col hover:-translate-y-1 hover:shadow-glow transition-all">
                <button type="button" onClick={() => onOpenResult?.(job.id)} className="text-left">
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

                <div className="mt-4 pt-3 border-t border-white/10 flex justify-end">
                  {confirmId === job.id ? (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-sand-300/70">Delete this translation?</span>
                      <button type="button" onClick={() => remove(job.id)}
                              className="btn-ghost !py-1 !px-2 text-red-300 hover:bg-red-500/20">Confirm</button>
                      <button type="button" onClick={() => setConfirmId(null)}
                              className="btn-ghost !py-1 !px-2">Cancel</button>
                    </div>
                  ) : (
                    <button type="button" onClick={() => setConfirmId(job.id)}
                            className="btn-ghost !py-1.5 !px-2.5 text-xs text-red-300 hover:bg-red-500/15">
                      <Trash2 className="w-4 h-4" /> Delete
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}