import { useState } from 'react'
import { API_BASE } from '../utils/api'

const EXAMPLES = [
  'Which roles involve building ML models for fraud detection?',
  'Remote backend roles that use Go and Kubernetes?',
  'Which companies mention visa sponsorship for new grads?',
  'What do security engineering roles here require?',
]

const CITATION = /\[(\d+(?:\s*,\s*\d+)*)\]/g

// Renders **bold** and [n] citations inside one line of answer text.
function InlineText({ text, onCite, activeSource }) {
  const parts = []
  let last = 0
  for (const m of text.matchAll(CITATION)) {
    parts.push(text.slice(last, m.index))
    const nums = m[1].split(',').map((n) => parseInt(n.trim(), 10))
    parts.push(
      <span key={m.index} className="whitespace-nowrap">
        {nums.map((n) => (
          <button
            key={n}
            onClick={() => onCite(n)}
            className={`mx-0.5 text-[10px] font-semibold align-super px-1.5 py-0.5 rounded transition-colors ${
              activeSource === n ? 'bg-indigo-500 text-white' : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
            }`}
          >
            {n}
          </button>
        ))}
      </span>,
    )
    last = m.index + m[0].length
  }
  parts.push(text.slice(last))

  return parts.map((p, i) =>
    typeof p !== 'string' ? p : p.split(/(\*\*[^*]+\*\*)/g).map((s, j) =>
      s.startsWith('**') && s.endsWith('**')
        ? <strong key={`${i}-${j}`} className="font-semibold text-slate-900">{s.slice(2, -2)}</strong>
        : <span key={`${i}-${j}`}>{s}</span>,
    ),
  )
}

function Answer({ text, onCite, activeSource }) {
  const lines = text.split('\n').filter((l) => l.trim())
  return (
    <div className="space-y-2 text-sm text-slate-700 leading-relaxed">
      {lines.map((line, i) => {
        const bullet = line.match(/^\s*[-*•]\s+(.*)/)
        return bullet ? (
          <div key={i} className="flex gap-2">
            <span className="text-indigo-400 flex-shrink-0">•</span>
            <p><InlineText text={bullet[1]} onCite={onCite} activeSource={activeSource} /></p>
          </div>
        ) : (
          <p key={i}><InlineText text={line} onCite={onCite} activeSource={activeSource} /></p>
        )
      })}
    </div>
  )
}

function SourceCard({ source, active, onOpenJob }) {
  return (
    <div
      id={`source-${source.n}`}
      className={`rounded-xl border p-4 transition-colors ${
        active ? 'border-indigo-400 bg-indigo-50/60' : source.cited ? 'border-slate-200 bg-white' : 'border-slate-100 bg-slate-50/60'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-slate-400">
            <span className="font-semibold text-indigo-600">[{source.n}]</span> · {source.section}
            {!source.cited && <span className="ml-1 text-slate-400">· retrieved, not cited</span>}
          </p>
          <button
            onClick={() => onOpenJob(source.job_id)}
            className="text-sm font-semibold text-slate-900 hover:text-indigo-600 text-left transition-colors"
          >
            {source.title} <span className="font-normal text-slate-500">at {source.company}</span>
          </button>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500 leading-relaxed line-clamp-4 whitespace-pre-line">{source.snippet}</p>
    </div>
  )
}

export default function AskTechHire({ onBack, onOpenJob }) {
  const [question, setQuestion] = useState('')
  const [state, setState] = useState('idle') // idle | loading | done | error
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [activeSource, setActiveSource] = useState(null)

  async function ask(q) {
    const text = (q ?? question).trim()
    if (text.length < 3) return
    setQuestion(text)
    setState('loading')
    setResult(null)
    setError(null)
    setActiveSource(null)
    try {
      const r = await fetch(`${API_BASE}/rag/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(d.detail || `Request failed (${r.status})`)
      setResult(d)
      setState('done')
    } catch (e) {
      setError(e.message)
      setState('error')
    }
  }

  function cite(n) {
    setActiveSource(n)
    document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const noAnswer = result && (result.status === 'abstained' || result.status === 'no_results')

  return (
    <div className="min-h-screen bg-[#0f172a]">
      {/* Header */}
      <div className="sticky top-0 z-30 bg-[#0f172a]/90 backdrop-blur border-b border-slate-800 px-6 py-4 flex items-center gap-4">
        <button onClick={onBack} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Jobs
        </button>
        <div className="h-5 w-px bg-slate-800" />
        <div>
          <h1 className="text-white font-bold text-base">Ask TechHire</h1>
          <p className="text-slate-400 text-xs">Questions answered from real job postings, with sources</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Question box */}
        <form
          onSubmit={(e) => { e.preventDefault(); ask() }}
          className="bg-slate-900 rounded-2xl border border-slate-800 p-5 space-y-3"
        >
          <div className="flex gap-3">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              maxLength={500}
              placeholder="e.g. Which roles involve building data pipelines with Spark?"
              className="flex-1 bg-slate-800 text-white placeholder-slate-500 rounded-xl px-4 py-3 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={state === 'loading' || question.trim().length < 3}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors"
            >
              {state === 'loading' ? 'Searching…' : 'Ask'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => ask(q)}
                disabled={state === 'loading'}
                className="text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 rounded-full transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </form>

        {state === 'loading' && (
          <div className="bg-white rounded-2xl p-6 space-y-3 animate-pulse">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-slate-400">Retrieving postings and checking citations…</span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full w-[90%]" />
            <div className="h-3 bg-slate-100 rounded-full w-[75%]" />
            <div className="h-3 bg-slate-100 rounded-full w-[82%]" />
          </div>
        )}

        {state === 'error' && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-700">{error}</div>
        )}

        {state === 'done' && result && (
          <>
            <div className="bg-white rounded-2xl p-6">
              {result.status === 'ungrounded' && (
                <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-800">
                  This answer's citations couldn't be verified against the retrieved postings — double-check it against the sources below.
                </div>
              )}
              {noAnswer ? (
                <p className="text-sm text-slate-500 italic">{result.answer}</p>
              ) : (
                <Answer text={result.answer} onCite={cite} activeSource={activeSource} />
              )}
            </div>

            {result.sources.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Sources · {result.sources.filter((s) => s.cited).length} cited of {result.sources.length} retrieved
                </h2>
                {[...result.sources]
                  .sort((a, b) => Number(b.cited) - Number(a.cited))
                  .map((s) => (
                    <SourceCard key={s.n} source={s} active={activeSource === s.n} onOpenJob={onOpenJob} />
                  ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
