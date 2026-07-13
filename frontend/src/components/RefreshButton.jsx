import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const API_BASE = 'http://localhost:8000'
const POLL_MS = 3000

export default function RefreshButton() {
  const [state, setState] = useState('idle') // idle | running | done | error
  const [result, setResult] = useState(null)
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
    try {
      const res = await fetch(`${API_BASE}/scrape/refresh`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'already_running') {
        pollStatus()
        return
      }
      pollStatus()
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 4000)
    }
  }

  useEffect(() => () => stopPolling(), [])

  const quotaExceeded = state === 'done' && result?.quota_exceeded

  const label =
    state === 'running' ? 'Fetching new jobs…' :
    quotaExceeded       ? '⚠ JSearch quota exceeded' :
    state === 'done'    ? `✓ ${result?.saved ?? 0} new job${result?.saved === 1 ? '' : 's'} added` :
    state === 'error'   ? 'Refresh failed' :
    'Refresh'

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
