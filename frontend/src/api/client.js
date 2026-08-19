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
  cancelJob: (id) => request(`/jobs/${id}/cancel`, { method: 'POST' }),

  glossary: () => request('/glossary'),
  addGlossary: (entry) =>
    request('/glossary', { method: 'POST', body: JSON.stringify(entry) }),
  deleteGlossary: (id) => request(`/glossary/${id}`, { method: 'DELETE' }),

  fileUrl: (jobId, kind, download = false) =>
    `${BASE}/jobs/${jobId}/file/${kind}${download ? '?download=true' : ''}`,
}

const TERMINAL = new Set(['completed', 'failed', 'cancelled'])

// Poll a job until it reaches a terminal state, invoking onUpdate on each tick.
export function pollJob(id, onUpdate, { interval = 900 } = {}) {
  let active = true
  async function tick() {
    if (!active) return
    try {
      const job = await api.getJob(id)
      onUpdate(job)
      if (TERMINAL.has(job.status)) return
    } catch (err) {
      onUpdate({ status: 'failed', error: err.message })
      return
    }
    if (active) setTimeout(tick, interval)
  }
  tick()
  return () => { active = false }
}

// Stream job progress over a WebSocket, falling back to polling if the socket
// cannot be established or drops before the job reaches a terminal state.
export function streamJob(id, onUpdate, { interval = 900 } = {}) {
  let active = true
  let ws = null
  let stopPoll = null
  let gotTerminal = false

  const fallbackToPolling = () => {
    if (!active || gotTerminal || stopPoll) return
    stopPoll = pollJob(id, onUpdate, { interval })
  }

  try {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${window.location.host}${BASE}/jobs/${id}/ws`)
    ws.onmessage = (ev) => {
      if (!active) return
      let job
      try { job = JSON.parse(ev.data) } catch { return }
      if (job.error === 'not_found') { onUpdate({ status: 'failed', error: 'Job not found' }); return }
      onUpdate(job)
      if (TERMINAL.has(job.status)) gotTerminal = true
    }
    ws.onerror = () => { try { ws.close() } catch { /* ignore */ } }
    ws.onclose = () => { fallbackToPolling() }
  } catch {
    fallbackToPolling()
  }

  return () => {
    active = false
    if (ws) { try { ws.close() } catch { /* ignore */ } }
    if (stopPoll) stopPoll()
  }
}