import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Download, FileText, Captions, Volume2, Film, Clock, RefreshCw,
  AlignLeft, Subtitles,
} from 'lucide-react'
import { api } from '../api/client'
import { Chip, CopyButton, LangBadge } from './ui'

function fmtTime(s) {
  if (s == null) return ''
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function fmtTs(s) {
  const total = Math.max(0, Math.floor(s))
  const m = Math.floor(total / 60)
  const sec = total % 60
  return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
}

export function ResultPanel({ job }) {
  const tabs = useMemo(() => {
    const t = [{ id: 'translation', label: 'Translation', icon: FileText }]
    if (job.source_text) t.push({ id: 'transcript', label: 'Transcript', icon: AlignLeft })
    if (job.segments?.some((s) => s.end > s.start)) t.push({ id: 'subtitles', label: 'Subtitles', icon: Subtitles })
    if (job.input_type === 'video') t.push({ id: 'video', label: 'Video', icon: Film })
    return t
  }, [job])

  const [tab, setTab] = useState('translation')
  const activeTab = tabs.find((t) => t.id === tab) ? tab : 'translation'

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="card overflow-hidden"
    >
      {/* Meta bar */}
      <div className="flex flex-wrap items-center gap-2 px-5 py-4 border-b border-white/10 bg-white/[0.02]">
        <LangBadge code={job.detected_lang || job.source_lang} />
        <span className="text-sand-400/50">›</span>
        <LangBadge code={job.target_lang} />
        {job.duration_sec ? (
          <Chip><Clock className="w-3.5 h-3.5" /> {fmtTime(job.duration_sec)}</Chip>
        ) : null}
        {job.reused && <Chip tone="saffron"><RefreshCw className="w-3.5 h-3.5" /> Reused from memory</Chip>}
        {job.mock && <Chip tone="saffron">Demo output</Chip>}
        <span className="ml-auto" />
        {tabs.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`nav-link !px-3 !py-1.5 flex items-center gap-1.5 ${activeTab === t.id ? 'nav-link-active' : ''}`}
            >
              <Icon className="w-4 h-4" /> {t.label}
            </button>
          )
        })}
      </div>

      <div className="p-5 md:p-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'translation' && <TranslationTab job={job} />}
            {activeTab === 'transcript' && <TranscriptTab job={job} />}
            {activeTab === 'subtitles' && <SubtitlesTab job={job} />}
            {activeTab === 'video' && <VideoTab job={job} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

function TranslationTab({ job }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold flex items-center gap-2">
          <FileText className="w-4 h-4 text-leaf-300" /> Translated text
        </h3>
        <div className="flex gap-2">
          <CopyButton text={job.translated_text} />
          <a className="btn-ghost !py-2 !px-3 text-xs" href={api.fileUrl(job.id, 'text', true)}>
            <Download className="w-4 h-4" /> .txt
          </a>
        </div>
      </div>
      <div className="rounded-2xl bg-ink-900/60 border border-white/10 p-5 font-deva text-lg leading-relaxed whitespace-pre-wrap">
        {job.translated_text || '—'}
      </div>

      {job.has_audio && (
        <div className="rounded-2xl bg-leaf-500/5 border border-leaf-500/20 p-4">
          <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-leaf-200">
            <Volume2 className="w-4 h-4" /> Voice-over ({job.target_lang.toUpperCase()})
          </div>
          <audio controls className="w-full" src={api.fileUrl(job.id, 'audio')} />
          <div className="mt-3">
            <a className="btn-ghost !py-2 !px-3 text-xs" href={api.fileUrl(job.id, 'audio', true)}>
              <Download className="w-4 h-4" /> Download voice (.wav)
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

function TranscriptTab({ job }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold flex items-center gap-2">
          <AlignLeft className="w-4 h-4 text-leaf-300" /> Original transcript
        </h3>
        <div className="flex gap-2">
          <CopyButton text={job.source_text} />
          <a className="btn-ghost !py-2 !px-3 text-xs" href={api.fileUrl(job.id, 'transcript', true)}>
            <Download className="w-4 h-4" /> .txt
          </a>
        </div>
      </div>
      <div className="rounded-2xl bg-ink-900/60 border border-white/10 p-5 font-deva text-base leading-relaxed whitespace-pre-wrap text-sand-200">
        {job.source_text || '—'}
      </div>
    </div>
  )
}

function SubtitlesTab({ job }) {
  const segments = job.segments || []
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold flex items-center gap-2">
          <Captions className="w-4 h-4 text-leaf-300" /> Time-aligned segments
        </h3>
        <div className="flex gap-2">
          {job.has_srt && (
            <a className="btn-ghost !py-2 !px-3 text-xs" href={api.fileUrl(job.id, 'srt', true)}>
              <Download className="w-4 h-4" /> .srt
            </a>
          )}
          {job.has_vtt && (
            <a className="btn-ghost !py-2 !px-3 text-xs" href={api.fileUrl(job.id, 'vtt', true)}>
              <Download className="w-4 h-4" /> .vtt
            </a>
          )}
        </div>
      </div>
      <div className="max-h-[420px] overflow-y-auto rounded-2xl border border-white/10 divide-y divide-white/5">
        {segments.map((s, i) => (
          <div key={i} className="grid grid-cols-[64px_1fr] gap-3 p-3 hover:bg-white/[0.03]">
            <div className="text-xs tabular-nums text-saffron-300/80 pt-1">{fmtTs(s.start)}</div>
            <div>
              <div className="font-deva text-sand-50">{s.translated}</div>
              <div className="text-xs text-sand-400/50 mt-0.5 font-deva">{s.source}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function VideoTab({ job }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold flex items-center gap-2">
          <Film className="w-4 h-4 text-leaf-300" /> Translated video
        </h3>
        {job.has_video && (
          <a className="btn-accent !py-2 !px-3 text-xs" href={api.fileUrl(job.id, 'video', true)}>
            <Download className="w-4 h-4" /> Download video
          </a>
        )}
      </div>
      <div className="rounded-2xl overflow-hidden border border-white/10 bg-black">
        {job.has_video ? (
          <video key="rendered" controls className="w-full max-h-[460px]" crossOrigin="anonymous">
            <source src={api.fileUrl(job.id, 'video')} type="video/mp4" />
            {job.has_vtt && (
              <track kind="subtitles" srcLang={job.target_lang} label="Translated" src={api.fileUrl(job.id, 'vtt')} />
            )}
          </video>
        ) : (
          <video key="original" controls className="w-full max-h-[460px]" crossOrigin="anonymous">
            <source src={api.fileUrl(job.id, 'input')} />
            {job.has_vtt && (
              <track default kind="subtitles" srcLang={job.target_lang} label="Translated" src={api.fileUrl(job.id, 'vtt')} />
            )}
          </video>
        )}

      </div>
      <p className="text-xs text-sand-300/50">
        {job.has_video
        ? 'The video has been rendered with the translated audio and subtitles.'
        : 'The original video is shown here. You can download the rendered video with translated audio and subtitles.'}
      </p>
    </div>
  )
}