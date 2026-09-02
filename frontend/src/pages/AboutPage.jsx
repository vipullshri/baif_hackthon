import {
  Cpu, WifiOff, Wifi, CheckCircle2, XCircle, Mic, Languages, Volume2, Clapperboard,
  ShieldCheck, Server, HardDrive, Sparkles,
} from 'lucide-react'
import { Chip } from '../components/ui'

const STACK = [
  { stage: 'Speech-to-Text', model: 'faster-whisper', lic: 'MIT', icon: Mic },
  { stage: 'Translation', model: 'AI4Bharat IndicTrans2', lic: 'MIT', icon: Languages },
  { stage: 'Text-to-Speech', model: 'MMS-TTS / Indic Parler-TTS', lic: 'CC-BY-NC / Apache-2.0', icon: Volume2 },
  { stage: 'Media', model: 'FFmpeg', lic: 'LGPL', icon: Clapperboard },
]

function ReadyRow({ icon: Icon, label, ready }) {
  return (
    <div className="flex items-center gap-3 py-2.5">
      <span className="grid place-items-center w-9 h-9 rounded-xl bg-white/5 border border-white/10">
        <Icon className="w-4 h-4 text-leaf-300" />
      </span>
      <span className="text-sm font-medium flex-1">{label}</span>
      {ready
        ? <span className="flex items-center gap-1.5 text-leaf-300 text-sm"><CheckCircle2 className="w-4 h-4" /> Ready</span>
        : <span className="flex items-center gap-1.5 text-sand-400/60 text-sm"><XCircle className="w-4 h-4" /> Demo</span>}
    </div>
  )
}

export function AboutPage({ health }) {
  const ready = health?.ready || {}
  return (
    <div className="space-y-8">
      {/* Status */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-lg flex items-center gap-2"><Server className="w-5 h-5 text-leaf-300" /> Engine status</h3>
            {health?.models_enabled
              ? <Chip tone="leaf">Models enabled</Chip>
              : <Chip tone="saffron">Demo mode</Chip>}
          </div>
          <div className="divide-y divide-white/5">
            <ReadyRow icon={Clapperboard} label="FFmpeg (media)" ready={ready.ffmpeg} />
            <ReadyRow icon={Mic} label="Whisper (transcription)" ready={ready.asr} />
            <ReadyRow icon={Languages} label="IndicTrans2 (translation)" ready={ready.translation} />
            <ReadyRow icon={Volume2} label="Text-to-Speech" ready={ready.tts} />
          </div>
          <div className="flex flex-wrap gap-2 mt-5">
            <Chip><Cpu className="w-3.5 h-3.5" /> {health?.device || 'auto'}</Chip>
            <Chip>Whisper • {health?.whisper_model}</Chip>
            <Chip>MT • {health?.mt_backend}</Chip>
            <Chip>TTS • {health?.tts_backend}</Chip>
            {health?.offline
              ? <Chip tone="leaf"><WifiOff className="w-3.5 h-3.5" /> Offline</Chip>
              : <Chip><Wifi className="w-3.5 h-3.5" /> Online OK</Chip>}
          </div>
        </div>

        <div className="card p-6">
          <h3 className="font-bold text-lg flex items-center gap-2 mb-4">
            <ShieldCheck className="w-5 h-5 text-saffron-300" /> Your translation workspace
          </h3>
          <ul className="space-y-3 text-sm text-sand-200/90">
            <li className="flex gap-2"><Sparkles className="w-4 h-4 text-leaf-300 mt-0.5 shrink-0" />
              100% open-source models — <b>no licensing or usage costs</b>.</li>
            <li className="flex gap-2"><WifiOff className="w-4 h-4 text-leaf-300 mt-0.5 shrink-0" />
              Runs fully <b>on-premises &amp; offline</b> after a one-time model download.</li>
            <li className="flex gap-2"><ShieldCheck className="w-4 h-4 text-leaf-300 mt-0.5 shrink-0" />
              No data leaves the machine — sensitive field recordings stay private.</li>
          </ul>
        </div>
      </div>

      {/* Stack */}
      <div className="card p-6">
        <h3 className="font-bold text-lg mb-1">Open-source model stack</h3>
        <p className="text-sm text-sand-300/60 mb-5">Every component is free and India-ready.</p>
        <div className="grid sm:grid-cols-2 gap-3">
          {STACK.map((s) => {
            const Icon = s.icon
            return (
              <div key={s.stage} className="flex items-center gap-3 rounded-2xl bg-ink-900/50 border border-white/10 p-4">
                <span className="grid place-items-center w-11 h-11 rounded-xl bg-leaf-500/15 border border-leaf-500/25">
                  <Icon className="w-5 h-5 text-leaf-300" />
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-xs label">{s.stage}</div>
                  <div className="font-semibold truncate">{s.model}</div>
                </div>
                <Chip tone="leaf">{s.lic}</Chip>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}