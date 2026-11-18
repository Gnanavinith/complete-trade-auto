const BASE = import.meta.env.VITE_API_BASE || (typeof window !== 'undefined' && window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://complete-trade-auto-vinith.onrender.com')
export const API = BASE.replace(/\/$/, '')

export async function fetchJSON(path){
  const r = await fetch(`${API}${path}`)
  if(!r.ok) throw new Error(`${path} ${r.status}`)
  return r.json()
}
export function wsURL(){
  const u = new URL(API)
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  u.pathname = '/ws'
  u.search = ''
  return u.toString()
}
