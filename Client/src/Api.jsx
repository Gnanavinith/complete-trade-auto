/**
 * Complete Trade Auto - API Client & Service Layer
 */

const BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== 'undefined' && window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : 'https://complete-trade-auto-vinith.onrender.com')

export const API = BASE.replace(/\/$/, '')

/**
 * Returns the WebSocket URL for live updates.
 */
export function wsURL() {
  const u = new URL(API)
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  u.pathname = '/ws'
  u.search = ''
  return u.toString()
}

/**
 * Generic JSON fetch helper with detailed error reporting.
 */
export async function fetchJSON(path, options = {}) {
  const r = await fetch(`${API}${path}`, options)
  if (!r.ok) {
    let errMsg = `${path} ${r.status}`
    try {
      const data = await r.json()
      if (data?.detail) errMsg = data.detail
      else if (data?.error) errMsg = typeof data.error === 'string' ? data.error : JSON.stringify(data.error)
    } catch {}
    throw new Error(errMsg)
  }
  return r.json()
}

/**
 * Generic POST request helper.
 */
export async function postJSON(path, body = null) {
  const headers = {}
  let bodyStr
  if (body !== null && body !== undefined) {
    headers['Content-Type'] = 'application/json'
    bodyStr = JSON.stringify(body)
  }
  return fetchJSON(path, {
    method: 'POST',
    headers,
    body: bodyStr,
  })
}

/* -------------------------------------------------------------------------
   Endpoint Services
   ------------------------------------------------------------------------- */

// Status & Market Data
export const getStatus = () => fetchJSON('/status')
export const getConfig = () => fetchJSON('/config')
export const getSymbols = () => fetchJSON('/symbols')
export const getTrades = () => fetchJSON('/trades')

// Backtesting
export const runBacktest = () => fetchJSON('/backtest')

// Engine Controls
export const startEngine = () => postJSON('/start')
export const stopEngine = () => postJSON('/stop')
export const stopAll = () => postJSON('/stop-all')
export const testEntry = () => postJSON('/test-entry')
export const testInstagram = (msg) => postJSON(`/test-instagram${msg ? `?message=${encodeURIComponent(msg)}` : ''}`)

// AI Market Analyst (Google Gemini)
export const getAIAnalysis = () => fetchJSON('/ai-analysis')
export const generateAIAnalysis = (sendNotifications = false) =>
  postJSON(`/ai-analysis/generate?send_notifications=${Boolean(sendNotifications)}`)

const api = {
  API,
  wsURL,
  fetchJSON,
  postJSON,
  getStatus,
  getConfig,
  getSymbols,
  getTrades,
  runBacktest,
  startEngine,
  stopEngine,
  stopAll,
  testEntry,
  testInstagram,
  getAIAnalysis,
  generateAIAnalysis,
}

export default api
