// Thin fetch wrapper around the BhashaSetu API.
// Same-origin in production (FastAPI serves the UI); proxied via Vite in dev.

const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: options.body && !(options.body instanceof FormData)
      ? { 'Content-Type': 'application/json' }
      : undefined,
    ...options,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  health: () => request('/health'),
  languages: () => request('/languages'),

  translateText: (payload) =>
    request('/translate/text', { method: 'POST', body: JSON.stringify(payload) }),

  createMediaJob: (formData) =>
    request('/jobs', { method: 'POST', body: formData }),

  getJob: (id) => request(`/jobs/${id}`),
  listJobs: (limit = 60) => request(`/jobs?limit=${limit}`),
  deleteJob: (id) => request(`/jobs/${id}`, { method: 'DELETE' }),

  glossary: () => request('/glossary'),
  addGlossary: (entry) =>
    request('/glossary', { method: 'POST', body: JSON.stringify(entry) }),
  deleteGlossary: (id) => request(`/glossary/${id}`, { method: 'DELETE' }),

  fileUrl: (jobId, kind, download = false) =>
    `${BASE}/jobs/${jobId}/file/${kind}${download ? '?download=true' : ''}`,
}

// Poll a job until it reaches a terminal state, invoking onUpdate on each tick.
export function pollJob(id, onUpdate, { interval = 900 } = {}) {
  let active = true
  async function tick() {
    if (!active) return
    try {
      const job = await api.getJob(id)
      onUpdate(job)
      if (job.status === 'completed' || job.status === 'failed') return
    } catch (err) {
      onUpdate({ status: 'failed', error: err.message })
      return
    }
    if (active) setTimeout(tick, interval)
  }
  tick()
  return () => { active = false }
}