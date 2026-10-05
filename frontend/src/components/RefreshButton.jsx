import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { API_BASE } from '../utils/api'

const POLL_MS = 3000
const ADMIN_KEY_STORAGE = 'techhire_admin_key'

function getStoredAdminKey() {
  try {
    return localStorage.getItem(ADMIN_KEY_STORAGE) || ''
  } catch {
    return ''
  }
}

export default function RefreshButton() {
  const [state, setState] = useState('idle') // idle | running | done | error
  const [result, setResult] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [showKeyPrompt, setShowKeyPrompt] = useState(false)
  const [keyInput, setKeyInput] = useState('')
  const pollRef = useRef(null)
  const queryClient = useQueryClient()

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  function pollStatus() {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/scrape/status`)
        const data = await res.json()

        if (data.status === 'done') {
          stopPolling()
          setResult(data.result)
          setState('done')
          queryClient.invalidateQueries({ queryKey: ['jobs'] })
          setTimeout(() => setState('idle'), data.result?.quota_exceeded ? 10000 : 4000)
        } else if (data.status === 'error') {
          stopPolling()
          setState('error')
          setTimeout(() => setState('idle'), 4000)
        }
      } catch {
        stopPolling()
        setState('error')
        setTimeout(() => setState('idle'), 4000)
      }
    }, POLL_MS)
  }

  async function handleClick() {
    if (state === 'running') return
    setState('running')
    setResult(null)
    setErrorMessage('')
    try {
      const adminKey = getStoredAdminKey()
      const res = await fetch(`${API_BASE}/scrape/refresh`, {
        method: 'POST',
        headers: adminKey ? { 'X-Admin-Key': adminKey } : {},
      })

      if (res.status === 401) {
        setState('idle')
        setShowKeyPrompt(true)
        return
      }
      if (res.status === 429) {
        const data = await res.json().catch(() => null)
        setState('error')
        setErrorMessage(data?.detail || 'Refresh is on cooldown — try again soon.')
        setTimeout(() => setState('idle'), 5000)
        return
      }

      const data = await res.json()
      if (data.status === 'already_running') {
        pollStatus()
        return
      }
      pollStatus()
    } catch {
      setState('error')
      setErrorMessage('Refresh failed')
      setTimeout(() => setState('idle'), 4000)
    }
  }

  function submitKey(e) {
    e.preventDefault()
    if (!keyInput.trim()) return
    try {
      localStorage.setItem(ADMIN_KEY_STORAGE, keyInput.trim())
    } catch {
      // localStorage unavailable — key just won't persist across reloads
    }
    setShowKeyPrompt(false)
    setKeyInput('')
    handleClick()
  }

  useEffect(() => () => stopPolling(), [])

  const quotaExceeded = state === 'done' && result?.quota_exceeded

  const label =
    state === 'running' ? 'Fetching new jobs…' :
    quotaExceeded       ? '⚠ JSearch quota exceeded' :
    state === 'done'    ? `✓ ${result?.saved ?? 0} new job${result?.saved === 1 ? '' : 's'} added` :
    state === 'error'   ? (errorMessage || 'Refresh failed') :
    'Refresh'

  if (showKeyPrompt) {
    return (
      <form onSubmit={submitKey} className="flex items-center gap-1.5">
        <input
          type="password"
          autoFocus
          value={keyInput}
          onChange={(e) => setKeyInput(e.target.value)}
          placeholder="Admin key"
          className="w-32 bg-slate-800 border border-slate-700 text-slate-200 text-sm px-3 py-2 rounded-lg placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-3 py-2 rounded-lg transition-colors"
        >
          Unlock
        </button>
        <button
          type="button"
          onClick={() => { setShowKeyPrompt(false); setKeyInput('') }}
          className="text-slate-500 hover:text-slate-300 text-sm px-2"
        >
          Cancel
        </button>
      </form>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={handleClick}
        disabled={state === 'running'}
        className={`flex items-center gap-2 border px-4 py-2 rounded-lg text-sm font-medium transition-colors
          ${quotaExceeded ? 'bg-amber-600/20 border-amber-600/40 text-amber-300' :
            state === 'done' ? 'bg-emerald-600/20 border-emerald-600/40 text-emerald-300' :
            state === 'error' ? 'bg-red-600/20 border-red-600/40 text-red-300' :
            'bg-slate-800 hover:bg-slate-700 border-slate-700 text-slate-300'}
          disabled:cursor-not-allowed`}
      >
        <svg
          className={`w-4 h-4 ${state === 'running' ? 'animate-spin' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        {label}
      </button>
      {quotaExceeded && (
        <p className="absolute top-full mt-1 right-0 text-xs text-amber-400/80 whitespace-nowrap">
          JSearch's free monthly request limit is used up — try again later.
        </p>
      )}
    </div>
  )
}
