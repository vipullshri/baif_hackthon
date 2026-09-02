import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Languages, Library, BookMarked, Activity, WifiOff, Github, Mic, FileVideo, Type,
} from 'lucide-react'
import { api } from './api/client'
import { Logo, BridgeIcon } from './components/Logo'
import { TranslatePage } from './pages/TranslatePage'
import { LibraryPage } from './pages/LibraryPage'
import { GlossaryPage } from './pages/GlossaryPage'
import { AboutPage } from './pages/AboutPage'
import { ResultPage } from './pages/ResultPage'

const NAV = [
  { id: 'translate', label: 'Translate', icon: Languages },
  { id: 'library', label: 'Library', icon: Library },
  { id: 'glossary', label: 'Glossary', icon: BookMarked },
  { id: 'about', label: 'System', icon: Activity },
]

// Minimal hash router: parses "#/view" or "#/result/:id" into { view, id }.
function parseHash() {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const [view, id] = raw.split('/')
  if (view === 'result' && id) return { view: 'result', id }
  const known = NAV.map((n) => n.id)
  return { view: known.includes(view) ? view : 'translate', id: null }
}

function navigate(view, id) {
  window.location.hash = view === 'result' && id ? `/result/${id}` : `/${view}`
}

export default function App() {
  const [route, setRoute] = useState(parseHash)
  const [languages, setLanguages] = useState([])
  const [health, setHealth] = useState(null)
  const [libKey, setLibKey] = useState(0)
  const { view, id } = route

  useEffect(() => {
    const onHash = () => setRoute(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    api.languages().then(setLanguages).catch(() => setLanguages([
      { code: 'en', name: 'English', native: 'English' },
      { code: 'hi', name: 'Hindi', native: 'हिन्दी' },
      { code: 'mr', name: 'Marathi', native: 'मराठी' },
    ]))
    api.health().then(setHealth).catch(() => {})
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      {/* --- Nav --- */}
      <header className="sticky top-0 z-40 glass border-b border-white/10">
        <div className="mx-auto max-w-6xl px-4 h-16 flex items-center gap-4">
          <button onClick={() => navigate('translate')}><Logo compact /></button>
          <nav className="hidden md:flex items-center gap-1 ml-4">
            {NAV.map((n) => {
              const Icon = n.icon
              return (
                <button key={n.id} onClick={() => navigate(n.id)}
                  className={`nav-link flex items-center gap-1.5 ${view === n.id ? 'nav-link-active' : ''}`}>
                  <Icon className="w-4 h-4" /> {n.label}
                </button>
              )
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <StatusPill health={health} />
          </div>
        </div>
        {/* Mobile nav */}
        <nav className="md:hidden flex items-center justify-around border-t border-white/10 px-2 py-1.5">
          {NAV.map((n) => {
            const Icon = n.icon
            return (
              <button key={n.id} onClick={() => navigate(n.id)}
                className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg text-[11px]
                  ${view === n.id ? 'text-saffron-300' : 'text-sand-300/60'}`}>
                <Icon className="w-5 h-5" /> {n.label}
              </button>
            )
          })}
        </nav>
      </header>

      <main className="flex-1 mx-auto max-w-6xl w-full px-4 py-8">
        {view === 'translate' && <Hero />}

        <motion.div
          key={view + (id || '')}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {view === 'translate' && (
            <TranslatePage
              languages={languages}
              onJobDone={() => setLibKey((k) => k + 1)}
              onOpenResult={(jobId) => navigate('result', jobId)}
            />
          )}
          {view === 'library' && (
            <LibraryPage refreshKey={libKey} onOpenResult={(jobId) => navigate('result', jobId)} />
          )}
          {view === 'result' && (
            <ResultPage id={id} onBack={() => navigate('library')} />
          )}
          {view === 'glossary' && <GlossaryPage languages={languages} />}
          {view === 'about' && <AboutPage health={health} />}
        </motion.div>
      </main>

      <footer className="border-t border-white/10 mt-8">
        <div className="mx-auto max-w-6xl px-4 py-6 flex flex-wrap items-center gap-3 text-sm text-sand-500/50">
          <BridgeIcon className="w-6 h-6" />
          <span>BhashaSetu - media translation.</span>
          <span className="ml-auto flex items-center gap-1.5">
            <Github className="w-4 h-4" /> Marathi · Hindi · English
          </span>
        </div>
      </footer>
    </div>
  )
}

function StatusPill({ health }) {
  if (!health) {
    return <span className="chip"><span className="w-2 h-2 rounded-full bg-sand-400/50" /> Connecting...</span>
  }
  const demo = !health.models_enabled
  return (
    <div className="flex items-center gap-2">
      {health.offline && (
        <span className="chip border-leaf-500/30 bg-leaf-500/10 text-leaf-200">
          <WifiOff className="w-3.5 h-3.5" /> Offline
        </span>
      )}
      <span className={`chip ${demo ? 'border-saffron-500/30 bg-saffron-500/10 text-saffron-200' : 'border-leaf-500/30 bg-leaf-500/10 text-leaf-200'}`}>
        <span className={`w-2 h-2 rounded-full ${demo ? 'bg-saffron-400' : 'bg-leaf-400'} animate-pulse`} />
        {demo ? 'Demo mode' : 'Live'}
      </span>
    </div>
  )
}

function Hero() {
  return (
    <section className="relative mb-10 overflow-hidden rounded-3xl card p-8 md:p-12 deva-watermark">
      <div className="relative z-10 max-w-2xl">
        <div className="chip mb-5 border-saffron-500/30 bg-saffron-500/10 text-saffron-200">
          <span className="w-2 h-2 rounded-full bg-saffron-400 animate-pulse" /> Built to bring languages closer
        </div>
        <h1 className="text-4xl md:text-5xl font-extrabold leading-[1.1] text-balance">
          Language without barriers.<br />
          <span className="gradient-text">Connect with clarity.</span>
        </h1>
        <p className="mt-4 text-lg text-sand-200/80 max-w-xl">
          Transcribe, translate, voice-over and caption <b>text, audio &amp; video</b> across
          Marathi, Hindi &amp; English - using only free, open-source models, fully offline.
        </p>
        <div className="flex flex-wrap gap-2 mt-6">
          <span className="chip"><Type className="w-3.5 h-3.5 text-leaf-300" /> Text</span>
          <span className="chip"><Mic className="w-3.5 h-3.5 text-leaf-300" /> Audio</span>
          <span className="chip"><FileVideo className="w-3.5 h-3.5 text-leaf-300" /> Video</span>
        </div>
      </div>
      <div className="pointer-events-none absolute -right-10 -bottom-10 opacity-20 md:opacity-30">
        <div className="animate-floaty"><BridgeIcon className="w-64 h-64" /></div>
      </div>
    </section>
  )
}