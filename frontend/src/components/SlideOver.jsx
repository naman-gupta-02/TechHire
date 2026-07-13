import { useEffect, useState, useRef } from 'react'
import { formatSalary, getSkillClass, timeAgo, SOURCE_CLASS, SOURCE_LABEL, WORK_MODE_CLASS } from '../utils/format'

const API_BASE = 'http://localhost:8000'

function Section({ title, children }) {
  return (
    <div className="mb-6">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{title}</h3>
      {children}
    </div>
  )
}

function BulletList({ items }) {
  if (!items?.length) return null
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-slate-600">
          <span className="text-indigo-400 mt-0.5 flex-shrink-0">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

function VisaPill({ value }) {
  if (value === true) return <span className="inline-flex items-center gap-1 text-xs font-medium bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">✓ Visa Sponsored</span>
  if (value === false) return <span className="inline-flex items-center gap-1 text-xs font-medium bg-red-100 text-red-600 px-3 py-1 rounded-full">✗ No Sponsorship</span>
  return <span className="inline-flex items-center gap-1 text-xs font-medium bg-slate-100 text-slate-500 px-3 py-1 rounded-full">? Visa Unknown</span>
}

function AiSummary({ jobId }) {
  const [state, setState] = useState('idle') // idle | loading | done | error | unconfigured
  const [summary, setSummary] = useState(null)
  const [cached, setCached] = useState(false)
  const fetchedFor = useRef(null)

  useEffect(() => {
    if (!jobId || fetchedFor.current === jobId) return
    fetchedFor.current = jobId
    setState('loading')
    setSummary(null)

    fetch(`${API_BASE}/jobs/${jobId}/summary`)
      .then((r) => {
        if (r.status === 503) { setState('unconfigured'); return null }
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (!d) return
        setSummary(d.summary)
        setCached(d.cached)
        setState('done')
      })
      .catch(() => setState('error'))
  }, [jobId])

  if (state === 'idle') return null

  if (state === 'loading') {
    return (
      <Section title="AI Summary">
        <div className="space-y-3 animate-pulse">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-slate-400">Generating summary with Claude AI…</span>
          </div>
          {[80, 95, 70].map((w, i) => (
            <div key={i} className={`h-3 bg-slate-100 rounded-full w-[${w}%]`} />
          ))}
          <div className="h-3 bg-slate-100 rounded-full w-[85%]" />
          <div className="h-3 bg-slate-100 rounded-full w-[60%]" />
        </div>
      </Section>
    )
  }

  if (state === 'unconfigured') {
    return (
      <Section title="AI Summary">
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <span className="text-lg flex-shrink-0">🔑</span>
          <div>
            <p className="text-sm font-medium text-amber-800">API key not configured</p>
            <p className="text-xs text-amber-700 mt-1">
              Add your <code className="bg-amber-100 px-1 rounded">GROQ_API_KEY</code> to{' '}
              <code className="bg-amber-100 px-1 rounded">.env</code> and restart the API server.
              Get a free key at <span className="underline font-medium">console.groq.com</span>.
            </p>
          </div>
        </div>
      </Section>
    )
  }

  if (state === 'error') {
    return (
      <Section title="AI Summary">
        <p className="text-sm text-slate-400 italic">Could not generate summary.</p>
      </Section>
    )
  }

  // done
  return (
    <Section title="AI Summary">
      <div className="bg-gradient-to-br from-indigo-50 to-slate-50 border border-indigo-100 rounded-xl p-4">
        {/* Badge row */}
        <div className="flex items-center gap-2 mb-3">
          <span className="inline-flex items-center gap-1 text-xs font-medium bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
            ✦ Claude AI
          </span>
          {cached && (
            <span className="text-xs text-slate-400">cached</span>
          )}
        </div>

        {/* Summary paragraphs */}
        <div className="space-y-3">
          {summary.split('\n\n').filter(Boolean).map((para, i) => (
            <p key={i} className="text-sm text-slate-700 leading-relaxed">
              {para}
            </p>
          ))}
        </div>

        {/* Refresh button */}
        <button
          onClick={() => {
            fetchedFor.current = null
            setState('loading')
            setSummary(null)
            fetch(`${API_BASE}/jobs/${jobId}/summary?refresh=true`)
              .then((r) => r.json())
              .then((d) => { setSummary(d.summary); setCached(false); setState('done') })
              .catch(() => setState('error'))
          }}
          className="mt-3 text-xs text-indigo-400 hover:text-indigo-600 transition-colors flex items-center gap-1"
        >
          ↻ Regenerate
        </button>
      </div>
    </Section>
  )
}

function FullDescription({ text }) {
  const [expanded, setExpanded] = useState(false)
  if (!text) return null
  const paragraphs = text.split('\n\n').filter(Boolean)
  const preview = paragraphs.slice(0, 2)
  const rest = paragraphs.slice(2)

  return (
    <Section title="Full Description">
      <div className="space-y-3">
        {preview.map((para, i) => (
          <p key={i} className="text-sm text-slate-600 leading-relaxed">
            {para.split('\n').map((line, j, arr) => (
              <span key={j}>{line}{j < arr.length - 1 && <br />}</span>
            ))}
          </p>
        ))}
        {rest.length > 0 && (
          <>
            {expanded && rest.map((para, i) => (
              <p key={i} className="text-sm text-slate-600 leading-relaxed">
                {para.split('\n').map((line, j, arr) => (
                  <span key={j}>{line}{j < arr.length - 1 && <br />}</span>
                ))}
              </p>
            ))}
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-indigo-500 hover:text-indigo-700 font-medium transition-colors"
            >
              {expanded ? '↑ Show less' : `↓ Show full description (${rest.length} more section${rest.length > 1 ? 's' : ''})`}
            </button>
          </>
        )}
      </div>
    </Section>
  )
}

export default function SlideOver({ job, onClose }) {
  const isOpen = job != null

  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  useEffect(() => {
    const handler = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const salary = job ? formatSalary(job.salary_min, job.salary_max) : null

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 bg-black/50 z-40 transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      />

      {/* Panel */}
      <div
        className={`fixed right-0 top-0 bottom-0 w-full sm:w-[620px] bg-white z-50 flex flex-col shadow-2xl transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {job && (
          <>
            {/* Sticky header */}
            <div className="flex items-start justify-between gap-4 p-6 border-b border-slate-100 flex-shrink-0">
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-bold text-slate-900 leading-snug">{job.title}</h2>
                <p className="text-slate-500 mt-1 text-sm">
                  {job.company}
                  {job.city && ` · ${job.city}, ${job.state}`}
                </p>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0"
                aria-label="Close"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Meta badges */}
            <div className="px-6 py-3 border-b border-slate-100 flex flex-wrap gap-2 flex-shrink-0">
              <span className={`text-xs font-medium px-3 py-1 rounded-full ${SOURCE_CLASS[job.source] ?? 'bg-slate-100 text-slate-600'}`}>
                {SOURCE_LABEL[job.source] ?? job.source}
              </span>
              <span className={`text-xs font-medium px-3 py-1 rounded-full capitalize ${WORK_MODE_CLASS[job.work_mode] ?? 'bg-slate-100 text-slate-600'}`}>
                {job.work_mode}
              </span>
              <VisaPill value={job.visa_sponsorship} />
              {salary && (
                <span className="text-xs font-semibold bg-slate-900 text-white px-3 py-1 rounded-full">
                  {salary} / yr
                </span>
              )}
              <span className="text-xs text-slate-400 self-center">
                Posted {timeAgo(job.posted_at)}
              </span>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto p-6">
              {/* Skills */}
              {job.required_skills?.length > 0 && (
                <Section title="Required Skills">
                  <div className="flex flex-wrap gap-2">
                    {job.required_skills.map((s) => (
                      <span key={s} className={`text-xs font-medium px-2.5 py-1 rounded-full ${getSkillClass(s)}`}>{s}</span>
                    ))}
                  </div>
                </Section>
              )}

              {/* AI Summary — auto-loads on open */}
              <AiSummary jobId={job.id} />

              {/* Full description — collapsed by default */}
              <FullDescription text={job.description} />

              {/* Responsibilities */}
              {job.responsibilities?.length > 0 && (
                <Section title="Responsibilities">
                  <BulletList items={job.responsibilities} />
                </Section>
              )}

              {/* Qualifications */}
              {job.qualifications?.length > 0 && (
                <Section title="Qualifications">
                  <BulletList items={job.qualifications} />
                </Section>
              )}

              {/* Benefits */}
              {job.benefits?.length > 0 && (
                <Section title="Benefits">
                  <BulletList items={job.benefits} />
                </Section>
              )}
            </div>

            {/* Sticky footer */}
            <div className="px-6 py-4 border-t border-slate-100 flex-shrink-0">
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                Apply Now
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
          </>
        )}
      </div>
    </>
  )
}
