import { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'

// ── PDF / file helpers ────────────────────────────────────────────────────────

async function extractTextFromFile(file) {
  // Always use the backend for extraction — pdfplumber handles LaTeX PDFs,
  // custom fonts, and ligatures far better than any JS library.
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/resume/extract-text`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Server returned ${res.status}`)
  }
  const { text } = await res.json()
  return text
}

// ── Score gauge (SVG circle) ──────────────────────────────────────────────────

function ScoreGauge({ score }) {
  const r    = 52
  const circ = 2 * Math.PI * r
  const fill = circ - (score / 100) * circ
  const color =
    score >= 75 ? '#16a34a' :
    score >= 50 ? '#d97706' : '#dc2626'
  const label =
    score >= 75 ? 'Strong Match' :
    score >= 50 ? 'Moderate Match' : 'Weak Match'

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="136" height="136" viewBox="0 0 136 136">
        <circle cx="68" cy="68" r={r} fill="none" stroke="#e2e8f0" strokeWidth="12" />
        <circle
          cx="68" cy="68" r={r}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeDasharray={circ}
          strokeDashoffset={fill}
          strokeLinecap="round"
          transform="rotate(-90 68 68)"
          style={{ transition: 'stroke-dashoffset 1.2s ease' }}
        />
        <text x="68" y="64" textAnchor="middle" fontSize="26" fontWeight="700" fill="#0f172a">{score}</text>
        <text x="68" y="84" textAnchor="middle" fontSize="12" fill="#64748b">out of 100</text>
      </svg>
      <span
        className="text-xs font-semibold px-3 py-1 rounded-full"
        style={{ backgroundColor: `${color}20`, color }}
      >
        {label}
      </span>
    </div>
  )
}

// ── Skill pill ────────────────────────────────────────────────────────────────

function Pill({ label, variant }) {
  const cls =
    variant === 'match'   ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' :
    variant === 'missing' ? 'bg-red-100 text-red-600 border border-red-200' :
                            'bg-indigo-50 text-indigo-700 border border-indigo-200'
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full ${cls}`}>
      {variant === 'match' && <span className="mr-1">✓</span>}
      {variant === 'missing' && <span className="mr-1">✗</span>}
      {label}
    </span>
  )
}

// ── Before / after rewrite card ───────────────────────────────────────────────

function RewriteCard({ before, after, reason }) {
  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden text-sm">
      <div className="grid grid-cols-2 divide-x divide-slate-200">
        <div className="p-3 bg-red-50">
          <p className="text-xs font-semibold text-red-500 uppercase tracking-wider mb-1.5">Before</p>
          <p className="text-slate-700 leading-relaxed">{before}</p>
        </div>
        <div className="p-3 bg-emerald-50">
          <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-1.5">After</p>
          <p className="text-slate-700 leading-relaxed">{after}</p>
        </div>
      </div>
      {reason && (
        <div className="px-3 py-2 bg-slate-50 border-t border-slate-200">
          <p className="text-xs text-slate-500"><span className="font-medium text-slate-600">Why: </span>{reason}</p>
        </div>
      )}
    </div>
  )
}

// ── Section card ──────────────────────────────────────────────────────────────

function SectionCard({ icon, title, found, issues, children }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{icon}</span>
          <div>
            <span className="font-semibold text-slate-800 text-sm">{title}</span>
            {!found && (
              <span className="ml-2 text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Not detected</span>
            )}
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-slate-100">
          {issues && (
            <div className="flex gap-2 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mt-4">
              <span className="flex-shrink-0 text-amber-500 mt-0.5">⚠</span>
              <p className="text-sm text-amber-800">{issues}</p>
            </div>
          )}
          {children}
        </div>
      )}
    </div>
  )
}

// ── Job picker ────────────────────────────────────────────────────────────────

function JobPicker({ onSelect }) {
  const [jobs, setJobs]   = useState([])
  const [query, setQuery] = useState('')
  const [open, setOpen]   = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/jobs?page_size=60&sort=newest`)
      .then((r) => r.json())
      .then((d) => setJobs(d.jobs || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    function handler(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = jobs.filter((j) =>
    `${j.title} ${j.company}`.toLowerCase().includes(query.toLowerCase())
  ).slice(0, 12)

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left bg-slate-800 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 text-sm hover:border-indigo-500 transition-colors flex items-center justify-between"
      >
        <span>Pick from recent jobs…</span>
        <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden">
          <div className="p-2 border-b border-slate-800">
            <input
              autoFocus
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search jobs…"
              className="w-full bg-slate-800 text-white placeholder-slate-500 rounded-lg px-3 py-1.5 text-sm outline-none border border-slate-700 focus:border-indigo-500"
            />
          </div>
          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 && (
              <li className="px-4 py-3 text-slate-500 text-sm">No jobs found</li>
            )}
            {filtered.map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  onClick={() => { onSelect(j); setOpen(false); setQuery('') }}
                  className="w-full text-left px-4 py-2.5 hover:bg-slate-800 transition-colors"
                >
                  <p className="text-sm text-white font-medium truncate">{j.title}</p>
                  <p className="text-xs text-slate-400 truncate">{j.company}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Results view ──────────────────────────────────────────────────────────────

function Results({ data }) {
  const { score, score_reasoning, matched_skills = [], missing_skills = [], sections = {}, top_suggestions = [] } = data
  const { summary, skills, experience, education, projects } = sections

  return (
    <div className="space-y-6">
      {/* Score + skills grid */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="flex flex-col sm:flex-row items-center gap-8">
          <ScoreGauge score={score} />
          <div className="flex-1 space-y-4">
            {score_reasoning && (
              <p className="text-slate-600 text-sm leading-relaxed italic">"{score_reasoning}"</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Matched Skills ({matched_skills.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {matched_skills.length > 0
                    ? matched_skills.map((s) => <Pill key={s} label={s} variant="match" />)
                    : <span className="text-xs text-slate-400">None detected</span>}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Missing Skills ({missing_skills.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {missing_skills.length > 0
                    ? missing_skills.map((s) => <Pill key={s} label={s} variant="missing" />)
                    : <span className="text-xs text-slate-400">None — great coverage!</span>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Top suggestions */}
      {top_suggestions.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-2xl p-5">
          <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-3">Top Suggestions</p>
          <ol className="space-y-2">
            {top_suggestions.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-indigo-900">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-bold mt-0.5">{i + 1}</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Section breakdown */}
      <div>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Section-by-Section Analysis</h3>
        <div className="space-y-3">

          {/* Summary */}
          <SectionCard icon="📝" title="Summary / Objective" found={summary?.found ?? true} issues={summary?.issues}>
            {summary?.rewrite && (
              <div className="mt-4 space-y-2">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Suggested Rewrite</p>
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-slate-700 leading-relaxed">
                  {summary.rewrite}
                </div>
              </div>
            )}
          </SectionCard>

          {/* Skills section */}
          <SectionCard icon="⚡" title="Skills Section" found={skills?.found ?? true} issues={skills?.issues}>
            {skills?.to_add?.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Add These Skills</p>
                <div className="flex flex-wrap gap-1.5">
                  {skills.to_add.map((s) => <Pill key={s} label={s} variant="add" />)}
                </div>
              </div>
            )}
            {skills?.suggestion && (
              <p className="mt-3 text-sm text-slate-600 bg-slate-50 rounded-xl p-3">{skills.suggestion}</p>
            )}
          </SectionCard>

          {/* Experience */}
          <SectionCard icon="💼" title="Work Experience" found={experience?.found ?? true} issues={experience?.issues}>
            {experience?.rewrites?.length > 0 && (
              <div className="mt-4 space-y-3">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Bullet Point Rewrites</p>
                {experience.rewrites.map((r, i) => (
                  <RewriteCard key={i} before={r.before} after={r.after} reason={r.reason} />
                ))}
              </div>
            )}
          </SectionCard>

          {/* Education */}
          <SectionCard icon="🎓" title="Education" found={education?.found ?? true} issues={education?.issues}>
            {education?.suggestion && (
              <p className="mt-4 text-sm text-slate-600 bg-slate-50 rounded-xl p-3">{education.suggestion}</p>
            )}
          </SectionCard>

          {/* Projects */}
          <SectionCard icon="🔨" title="Projects" found={projects?.found ?? true} issues={projects?.issues}>
            {projects?.suggestion && (
              <p className="mt-4 text-sm text-slate-600 bg-slate-50 rounded-xl p-3">{projects.suggestion}</p>
            )}
          </SectionCard>

        </div>
      </div>
    </div>
  )
}

// ── File drop zone ────────────────────────────────────────────────────────────

function DropZone({ onFile, fileName }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  function handle(file) {
    if (!file) return
    if (!['application/pdf', 'text/plain'].includes(file.type) &&
        !file.name.endsWith('.pdf') && !file.name.endsWith('.txt')) {
      alert('Please upload a PDF or .txt file.')
      return
    }
    onFile(file)
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); handle(e.dataTransfer.files[0]) }}
      onClick={() => inputRef.current?.click()}
      className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors
        ${dragging ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 hover:border-indigo-500/60 hover:bg-slate-800/60'}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,application/pdf,text/plain"
        className="hidden"
        onChange={(e) => handle(e.target.files[0])}
      />
      {fileName ? (
        <>
          <span className="text-2xl">📄</span>
          <p className="text-sm font-medium text-emerald-400">{fileName}</p>
          <p className="text-xs text-slate-500">Click to replace</p>
        </>
      ) : (
        <>
          <span className="text-2xl">☁️</span>
          <p className="text-sm text-slate-300">Drop your resume here</p>
          <p className="text-xs text-slate-500">PDF or TXT · or click to browse</p>
        </>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ResumeChecker({ onBack }) {
  const [resumeText, setResumeText]     = useState('')
  const [resumeFile, setResumeFile]     = useState(null)
  const [fileError, setFileError]       = useState(null)
  const [jobDesc, setJobDesc]           = useState('')
  const [selectedJob, setSelectedJob]   = useState(null)
  const [state, setState]               = useState('idle') // idle | loading | done | error
  const [result, setResult]             = useState(null)
  const [errorMsg, setErrorMsg]         = useState('')
  const resultsRef = useRef(null)

  async function handleFile(file) {
    setFileError(null)
    setResumeFile(file)
    try {
      const text = await extractTextFromFile(file)
      setResumeText(text)
    } catch {
      setFileError('Could not read the file. Try pasting your resume as text below.')
    }
  }

  function handleJobSelect(job) {
    setSelectedJob(job)
    // Pre-fill with title + company so user sees something; actual description fetched on analyze
    setJobDesc(`[Fetching description for: ${job.title} at ${job.company}]`)
    // Fetch full description
    fetch(`${API_BASE}/jobs/${job.id}`)
      .then((r) => r.json())
      .then((j) => setJobDesc(j.description || `${j.title} at ${j.company}`))
      .catch(() => setJobDesc(`${job.title} at ${job.company}`))
  }

  async function analyze() {
    if (!resumeText.trim()) { alert('Please upload or paste your resume first.'); return }
    if (!jobDesc.trim())    { alert('Please provide a job description.'); return }

    setState('loading')
    setResult(null)

    try {
      const res = await fetch(`${API_BASE}/resume/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_text: resumeText,
          job_description: jobDesc,
          job_id: selectedJob?.id ?? null,
        }),
      })

      if (res.status === 503) { setErrorMsg('GROQ_API_KEY not configured — add it to .env'); setState('error'); return }
      if (!res.ok) { const d = await res.json(); setErrorMsg(d.detail || 'Analysis failed'); setState('error'); return }

      const data = await res.json()
      setResult(data)
      setState('done')
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
    } catch {
      setErrorMsg('Could not reach the API server.')
      setState('error')
    }
  }

  return (
    <div className="min-h-screen bg-[#0f172a]">
      {/* Header */}
      <div className="sticky top-0 z-30 bg-[#0f172a]/90 backdrop-blur border-b border-slate-800 px-6 py-4 flex items-center gap-4">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Jobs
        </button>
        <div className="h-5 w-px bg-slate-800" />
        <div>
          <h1 className="text-white font-bold text-base">Resume Compatibility Checker</h1>
          <p className="text-slate-400 text-xs">See how well your resume matches a job description</p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">

        {/* Input section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* Resume panel */}
          <div className="bg-slate-900 rounded-2xl border border-slate-800 p-5 space-y-4">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Your Resume</h2>
            <DropZone onFile={handleFile} fileName={resumeFile?.name} />
            {fileError && <p className="text-xs text-red-400">{fileError}</p>}
            <div>
              <p className="text-xs text-slate-500 mb-2">Or paste resume text</p>
              <textarea
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                rows={10}
                placeholder="Paste your resume here…"
                className="w-full bg-slate-800 text-white placeholder-slate-600 rounded-xl px-4 py-3 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500 resize-none leading-relaxed"
              />
              {resumeText && (
                <p className="text-xs text-slate-500 mt-1 text-right">{resumeText.length.toLocaleString()} chars</p>
              )}
            </div>
          </div>

          {/* Job description panel */}
          <div className="bg-slate-900 rounded-2xl border border-slate-800 p-5 space-y-4">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Job Description</h2>
            <JobPicker onSelect={handleJobSelect} />
            <div>
              <p className="text-xs text-slate-500 mb-2">Or paste a job description</p>
              <textarea
                value={jobDesc}
                onChange={(e) => { setJobDesc(e.target.value); setSelectedJob(null) }}
                rows={14}
                placeholder="Paste the full job description here…"
                className="w-full bg-slate-800 text-white placeholder-slate-600 rounded-xl px-4 py-3 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500 resize-none leading-relaxed"
              />
              {selectedJob && (
                <p className="text-xs text-emerald-400 mt-1">
                  ✓ Using: {selectedJob.title} at {selectedJob.company}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Analyze button */}
        <div className="flex justify-center">
          <button
            onClick={analyze}
            disabled={state === 'loading'}
            className="flex items-center gap-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold px-10 py-3.5 rounded-xl transition-colors shadow-lg shadow-indigo-900/30"
          >
            {state === 'loading' ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analyzing with AI…
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                </svg>
                Analyze Compatibility
              </>
            )}
          </button>
        </div>

        {/* Error */}
        {state === 'error' && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-5 py-4 text-sm text-red-300">
            ✗ {errorMsg}
          </div>
        )}

        {/* Results */}
        {state === 'done' && result && (
          <div ref={resultsRef}>
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Analysis Results</h2>
            <Results data={result} />
          </div>
        )}
      </div>
    </div>
  )
}
