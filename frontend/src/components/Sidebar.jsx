import { useState } from 'react'

// ── sub-components ────────────────────────────────────────────────────────────

function FilterSection({ title, children }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  )
}

function TechStackInput({ value, onChange }) {
  const [input, setInput] = useState('')

  function addTag() {
    const tag = input.trim().toLowerCase()
    if (tag && !value.includes(tag)) onChange([...value, tag])
    setInput('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag() }
    if (e.key === 'Backspace' && !input && value.length) onChange(value.slice(0, -1))
  }

  return (
    <div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={addTag}
        placeholder='Type + Enter  (e.g. "Python")'
        className="w-full bg-slate-800 text-white placeholder-slate-500 rounded-lg px-3 py-2 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500"
      />
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {value.map((tag) => (
            <button
              key={tag}
              onClick={() => onChange(value.filter((t) => t !== tag))}
              className="inline-flex items-center gap-1 bg-indigo-500/20 text-indigo-300 rounded-full px-2.5 py-0.5 text-xs hover:bg-indigo-500/30 transition-colors"
            >
              {tag} <span className="opacity-60">×</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function CheckboxGroup({ options, value, onChange }) {
  function toggle(opt) {
    onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt])
  }
  return (
    <div className="space-y-2.5">
      {options.map((opt) => (
        <label key={opt.value} onClick={() => toggle(opt.value)} className="flex items-center gap-2.5 cursor-pointer group">
          <div
            className={`w-4 h-4 rounded flex-shrink-0 flex items-center justify-center border transition-colors ${
              value.includes(opt.value) ? 'bg-indigo-600 border-indigo-600' : 'border-slate-600 group-hover:border-slate-400'
            }`}
          >
            {value.includes(opt.value) && (
              <svg className="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            )}
          </div>
          <span className="text-sm text-slate-300 group-hover:text-white transition-colors select-none">{opt.label}</span>
        </label>
      ))}
    </div>
  )
}

function SalarySlider({ salaryMin, salaryMax, onChange }) {
  return (
    <div className="space-y-4">
      <div>
        <div className="flex justify-between text-xs text-slate-400 mb-2">
          <span>Minimum</span>
          <span className="text-white font-medium">
            {salaryMin === 0 ? 'Any' : `$${Math.round(salaryMin / 1000)}k`}
          </span>
        </div>
        <input
          type="range" min={0} max={300000} step={10000}
          value={salaryMin}
          onChange={(e) => onChange(Number(e.target.value), salaryMax)}
          className="w-full accent-indigo-500 cursor-pointer h-1"
        />
      </div>
      <div>
        <div className="flex justify-between text-xs text-slate-400 mb-2">
          <span>Maximum</span>
          <span className="text-white font-medium">
            {salaryMax >= 300000 ? 'Any' : `$${Math.round(salaryMax / 1000)}k`}
          </span>
        </div>
        <input
          type="range" min={0} max={300000} step={10000}
          value={salaryMax}
          onChange={(e) => onChange(salaryMin, Number(e.target.value))}
          className="w-full accent-indigo-500 cursor-pointer h-1"
        />
      </div>
    </div>
  )
}

function StyledSelect({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-slate-800 text-white rounded-lg px-3 py-2 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500 cursor-pointer appearance-none"
    >
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

// ── main sidebar ──────────────────────────────────────────────────────────────

export default function Sidebar({ filters, onChange, onClear, onClose }) {
  const hasActiveFilters =
    filters.search ||
    filters.skills.length ||
    filters.visaOnly ||
    filters.salaryMin > 0 ||
    filters.salaryMax < 300000 ||
    filters.workModes.length ||
    filters.experienceLevels.length ||
    filters.datePosted !== 'any' ||
    filters.seasons.length

  return (
    <div className="p-6 space-y-7">
      {/* Brand + close (mobile) */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-lg font-bold text-white">TechHire</span>
          <span className="ml-2 text-xs text-indigo-400 font-medium">Jobs</span>
        </div>
        <div className="flex items-center gap-3">
          {hasActiveFilters && (
            <button onClick={onClear} className="text-xs text-slate-400 hover:text-white transition-colors underline underline-offset-2">
              Clear all
            </button>
          )}
          <button onClick={onClose} className="lg:hidden text-slate-400 hover:text-white p-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Search */}
      <FilterSection title="Search">
        <div className="relative">
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={filters.search}
            onChange={(e) => onChange('search', e.target.value)}
            placeholder="Title or company..."
            className="w-full bg-slate-800 text-white placeholder-slate-500 rounded-lg pl-9 pr-3 py-2 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500"
          />
          {filters.search && (
            <button onClick={() => onChange('search', '')} className="absolute right-3 top-2.5 text-slate-500 hover:text-white">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </FilterSection>

      {/* Tech Stack */}
      <FilterSection title="Tech Stack">
        <TechStackInput value={filters.skills} onChange={(v) => onChange('skills', v)} />
      </FilterSection>

      {/* Visa Sponsorship */}
      <FilterSection title="Visa Sponsorship">
        <div className="flex rounded-lg overflow-hidden border border-slate-700">
          {[{ label: 'All Jobs', val: false }, { label: '✓ Sponsored Only', val: true }].map(({ label, val }) => (
            <button
              key={String(val)}
              onClick={() => onChange('visaOnly', val)}
              className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                filters.visaOnly === val ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </FilterSection>

      {/* Salary */}
      <FilterSection title="Salary Range">
        <SalarySlider
          salaryMin={filters.salaryMin}
          salaryMax={filters.salaryMax}
          onChange={(min, max) => { onChange('salaryMin', min); onChange('salaryMax', max) }}
        />
      </FilterSection>

      {/* Work Arrangement */}
      <FilterSection title="Work Arrangement">
        <CheckboxGroup
          value={filters.workModes}
          onChange={(v) => onChange('workModes', v)}
          options={[
            { value: 'remote', label: '🌐 Remote' },
            { value: 'hybrid', label: '🏢 Hybrid' },
            { value: 'onsite', label: '📍 On-site' },
          ]}
        />
      </FilterSection>

      {/* Experience Level */}
      <FilterSection title="Experience Level">
        <CheckboxGroup
          value={filters.experienceLevels}
          onChange={(v) => onChange('experienceLevels', v)}
          options={[
            { value: 'intern',  label: '🎓 Intern' },
            { value: 'entry',   label: '🌱 Entry Level' },
            { value: 'mid',     label: '⚡ Mid Level' },
            { value: 'senior',  label: '🚀 Senior' },
          ]}
        />
      </FilterSection>

      {/* Start Season */}
      <FilterSection title="Start Season">
        <CheckboxGroup
          value={filters.seasons}
          onChange={(v) => onChange('seasons', v)}
          options={[
            { value: 'summer', label: '☀️ Summer' },
            { value: 'fall',   label: '🍂 Fall' },
            { value: 'spring', label: '🌸 Spring' },
            { value: 'winter', label: '❄️ Winter' },
          ]}
        />
      </FilterSection>

      {/* Date Posted */}
      <FilterSection title="Date Posted">
        <StyledSelect
          value={filters.datePosted}
          onChange={(v) => onChange('datePosted', v)}
          options={[
            { value: 'any', label: 'Any time' },
            { value: '24h', label: 'Last 24 hours' },
            { value: '7d',  label: 'Last 7 days' },
            { value: '30d', label: 'Last 30 days' },
          ]}
        />
      </FilterSection>

      {/* Sort */}
      <FilterSection title="Sort By">
        <StyledSelect
          value={filters.sort}
          onChange={(v) => onChange('sort', v)}
          options={[
            { value: 'relevant', label: 'Most Relevant' },
            { value: 'newest',   label: 'Newest First' },
            { value: 'salary',   label: 'Salary: High → Low' },
          ]}
        />
      </FilterSection>
    </div>
  )
}
