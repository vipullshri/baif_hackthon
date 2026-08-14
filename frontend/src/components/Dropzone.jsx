import { useCallback, useRef, useState } from 'react'
import { FileAudio, FileVideo, UploadCloud, X } from 'lucide-react'

const AUDIO_EXTS = ['mp3', 'wav', 'aac', 'm4a', 'flac', 'wma', 'ogg']
const VIDEO_EXTS = ['mp4', 'mov', 'avi', 'wmv', 'mkv', 'flv', 'webm']

function prettySize(bytes) {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  return mb < 1 ? `${(bytes / 1024).toFixed(0)} KB` : `${mb.toFixed(1)} MB`
}

export function Dropzone({ mode, file, onFile, onClear }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')

  const exts = mode === 'video' ? VIDEO_EXTS : AUDIO_EXTS
  const accept = exts.map(e => `.${e}`).join(',')

  const validate = useCallback((f) => {
    const ext = f.name.split('.').pop()?.toLowerCase()
    if (!exts.includes(ext)) {
      setError(`Unsupported ${mode} format ".${ext}". Allowed: ${exts.join(', ')}`)
      return false
    }
    setError('')
    return true
  }, [exts, mode])

  const handleFiles = (files) => {
    const f = files?.[0]
    if (f && validate(f)) onFile(f)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  if (file) {
    const Icon = mode === 'video' ? FileVideo : FileAudio
    return (
      <div className="card p-5 flex items-center gap-4 animate-fadeUp">
        <div className="grid place-items-center w-14 h-14 rounded-2xl bg-leaf-500/15 border border-leaf-500/25">
          <Icon className="w-7 h-7 text-leaf-300" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold truncate">{file.name}</div>
          <div className="text-sm text-sand-300/60">{prettySize(file.size)} • ready to translate</div>
        </div>
        <button onClick={onClear} className="btn-ghost !p-2.5" title="Remove">
          <X className="w-5 h-5" />
        </button>
      </div>
    )
  }

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative cursor-pointer rounded-3xl border-2 border-dashed p-10 text-center transition-all
          ${dragging
            ? 'border-saffron-400 bg-saffron-500/10 scale-[1.01]'
            : 'border-white/15 hover:border-leaf-500/50 hover:bg-white/[0.03]'}`}
      >
        <div className="mx-auto mb-4 grid place-items-center w-16 h-16 rounded-2xl bg-leaf-500/10 border border-leaf-500/20">
          <UploadCloud className={`w-8 h-8 ${dragging ? 'text-saffron-300' : 'text-leaf-300'}`} />
        </div>
        <p className="text-lg font-semibold">
          Drop your {mode} here, or <span className="text-saffron-300">browse</span>
        </p>
        <p className="mt-1 text-sm text-sand-300/60">
          {mode === 'video' ? 'MP4, MOV, AVI, WMV, MKV, FLV, WebM • up to 200 MB' : 'MP3, WAV, AAC, M4A, FLAC, WMA, OGG • up to 150 MB'}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
    </div>
  )
}