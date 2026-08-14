import { useEffect, useMemo, useState } from 'react'
import { BookMarked, Plus, Trash2, Search, Sprout } from 'lucide-react'
import { api } from '../api/client'
import { EmptyState, Spinner } from '../components/ui'

const BLANK = { category: 'general', en: '', hi: '', mr: '', note: '' }

export function GlossaryPage() {
  const [entries, setEntries] = useState(null)
  const [form, setForm] = useState(BLANK)
  const [saving, setSaving] = useState(false)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    try { setEntries(await api.glossary()) } catch { setEntries([]) }
  }
  useEffect(() => { load() }, [])

  const add = async (e) => {
    e.preventDefault()
    if (!form.en || !form.hi || !form.mr) {
      setError('English, Hindi and Marathi forms are all required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.addGlossary(form)
      setForm(BLANK)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    await api.deleteGlossary(id)
    setEntries((prev) => prev.filter((e) => e.id !== id))
  }

  const grouped = useMemo(() => {
    if (!entries) return {}
    const q = query.toLowerCase()
    const filtered = entries.filter((e) =>
      !q || [e.en, e.hi, e.mr, e.category].some((v) => v?.toLowerCase().includes(q)))
    return filtered.reduce((acc, e) => {
      (acc[e.category] ||= []).push(e)
      return acc
    }, {})
  }, [entries, query])

  return (
    <div className="grid lg:grid-cols-[1fr_360px] gap-6 items-start">
      {/* Table */}
      <div>
        <div className="flex items-center gap-3 mb-5">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-sand-400/50" />
            <input value={query} onChange={(e) => setQuery(e.target.value)}
                   placeholder="Search terms…" className="input pl-10" />
          </div>
          <span className="ml-auto text-sm text-sand-300/60">{entries?.length ?? 0} terms</span>
        </div>

        {entries === null ? (
          <div className="grid place-items-center py-24"><Spinner className="w-8 h-8 text-leaf-300" /></div>
        ) : Object.keys(grouped).length === 0 ? (
          <EmptyState icon={BookMarked} title="No matching terms" />
        ) : (
          <div className="space-y-6">
            {Object.entries(grouped).map(([cat, items]) => (
              <div key={cat}>
                <div className="flex items-center gap-2 mb-2">
                  <Sprout className="w-4 h-4 text-leaf-300" />
                  <h3 className="font-semibold capitalize">{cat}</h3>
                  <span className="text-xs text-sand-400/50">({items.length})</span>
                </div>
                <div className="card overflow-hidden divide-y divide-white/5">
                  <div className="grid grid-cols-[1fr_1fr_1fr_36px] gap-3 px-4 py-2.5 text-xs label bg-white/[0.02]">
                    <span>English</span><span>हिन्दी</span><span>मराठी</span><span></span>
                  </div>
                  {items.map((e) => (
                    <div key={e.id} className="grid grid-cols-[1fr_1fr_1fr_36px] gap-3 px-4 py-3 items-center hover:bg-white/[0.03] group">
                      <span className="text-sand-100">{e.en}</span>
                      <span className="font-deva text-sand-100">{e.hi}</span>
                      <span className="font-deva text-sand-100">{e.mr}</span>
                      <button onClick={() => remove(e.id)}
                              className="opacity-0 group-hover:opacity-100 transition p-1.5 rounded-lg hover:bg-red-500/20 text-red-300">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add form */}
      <form onSubmit={add} className="card p-6 space-y-4 lg:sticky lg:top-24">
        <div className="flex items-center gap-2">
          <Plus className="w-5 h-5 text-saffron-300" />
          <h3 className="font-bold text-lg">Add a term</h3>
        </div>
        <p className="text-sm text-sand-300/60">
          Keep BAIF vocabulary consistent across every translation — crop names, breeds, schemes and more.
        </p>
        <div>
          <span className="label">Category</span>
          <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
                 className="input mt-1" placeholder="e.g. livestock" />
        </div>
        <div>
          <span className="label">English</span>
          <input value={form.en} onChange={(e) => setForm({ ...form, en: e.target.value })}
                 className="input mt-1" placeholder="crossbred cow" />
        </div>
        <div>
          <span className="label">हिन्दी (Hindi)</span>
          <input value={form.hi} onChange={(e) => setForm({ ...form, hi: e.target.value })}
                 className="input mt-1 font-deva" placeholder="संकर गाय" />
        </div>
        <div>
          <span className="label">मराठी (Marathi)</span>
          <input value={form.mr} onChange={(e) => setForm({ ...form, mr: e.target.value })}
                 className="input mt-1 font-deva" placeholder="संकरित गाय" />
        </div>
        {error && <p className="text-sm text-red-300">{error}</p>}
        <button disabled={saving} className="btn-accent w-full">
          {saving ? <Spinner /> : <><Plus className="w-5 h-5" /> Add term</>}
        </button>
      </form>
    </div>
  )
}