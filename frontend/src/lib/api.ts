export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
export const TOKEN_KEY = 'finpilot_token'

export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...init, headers })
  if (response.status === 401) {
    setToken(null)
    window.dispatchEvent(new Event('finpilot:auth-expired'))
  }
  if (!response.ok) {
    let message = `Erreur ${response.status}`
    try { const body = await response.json(); message = body.detail || message } catch { /* non-JSON error */ }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  const type = response.headers.get('content-type') || ''
  return (type.includes('application/json') ? response.json() : response.blob()) as Promise<T>
}

export function queryString(values: Record<string, string | number | undefined | null | false>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== false) params.set(key, String(value))
  })
  const out = params.toString()
  return out ? `?${out}` : ''
}

export async function download(path: string, filename: string) {
  const blob = await api<Blob>(path)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url; anchor.download = filename; anchor.click()
  URL.revokeObjectURL(url)
}

export const money = (value: number | null | undefined, currency = 'XOF') =>
  (() => {
    const selected = localStorage.getItem('finpilot_currency') || currency
    const rate = Number(localStorage.getItem('finpilot_fx_rate') || '1')
    const converted = selected === 'XOF' ? (value || 0) : (value || 0) / (rate > 0 ? rate : 1)
    const formatted = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: selected === 'XOF' ? 0 : 2 }).format(converted)
    return `${formatted} ${selected === 'XOF' ? 'FCFA' : selected}`
  })()

export const shortMoney = (value: number) => {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace('.', ',')} M`
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(0)} k`
  return String(value)
}

export const dateLabel = (value?: string) => value ? new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${value.slice(0, 10)}T12:00:00`)) : '—'

