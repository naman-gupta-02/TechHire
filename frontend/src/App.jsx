import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import JobCard from './components/JobCard'
import SkeletonCard from './components/SkeletonCard'
import SlideOver from './components/SlideOver'
import RefreshButton from './components/RefreshButton'
import ResumeChecker from './components/ResumeChecker'
import { useJobs } from './hooks/useJobs'

const DEFAULT_FILTERS = {
  search: '',
  skills: [],
  visaOnly: false,
  salaryMin: 0,
  salaryMax: 300000,
  workModes: [],
  experienceLevels: [],
  datePosted: 'any',
  seasons: [],
  sort: 'newest',
}

const PAGE_SIZE = 20

function EmptyState({ onClear }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center px-4">
      <div className="text-5xl mb-4">🔍</div>
      <h3 className="text-white text-xl font-semibold mb-2">No jobs found</h3>
      <p className="text-slate-400 text-sm mb-6 max-w-xs">
        Try adjusting your filters — maybe broaden your tech stack, salary range, or experience level.
      </p>
      <button
        onClick={onClear}
        className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
      >
        Clear all filters
      </button>
    </div>
  )
}

function Pagination({ page, totalPages, total, pageSize, onChange }) {
  if (totalPages <= 1) return null

  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  // Build page number list with ellipsis
  function getPages() {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1)
    const pages = []
    if (page <= 4) {
      pages.push(1, 2, 3, 4, 5, '...', totalPages)
    } else if (page >= totalPages - 3) {
      pages.push(1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages)
    } else {
      pages.push(1, '...', page - 1, page, page + 1, '...', totalPages)
    }
    return pages
  }

  return (
    <div className="flex flex-col items-center gap-4 py-8">
      <p className="text-slate-400 text-sm">
        Showing <span className="text-white font-medium">{start}–{end}</span> of{' '}
        <span className="text-white font-medium">{total}</span> jobs
      </p>
      <div className="flex items-center gap-1.5">
        {/* Prev */}
        <button
          onClick={() => onChange(page - 1)}
          disabled={page === 1}
          className="px-3 py-1.5 rounded-lg text-sm font-medium border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          ← Prev
        </button>

        {/* Page numbers */}
        {getPages().map((p, i) =>
          p === '...' ? (
            <span key={`ellipsis-${i}`} className="px-2 py-1.5 text-slate-500 text-sm select-none">…</span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`w-9 h-9 rounded-lg text-sm font-medium border transition-colors ${
                p === page
                  ? 'bg-indigo-600 border-indigo-600 text-white'
                  : 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              {p}
            </button>
          )
        )}

        {/* Next */}
        <button
          onClick={() => onChange(page + 1)}
          disabled={page === totalPages}
          className="px-3 py-1.5 rounded-lg text-sm font-medium border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState('jobs') // 'jobs' | 'resume'
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)
  const [selectedJob, setSelectedJob] = useState(null)
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)

  const { data, isPending, isFetching } = useJobs(filters, page, PAGE_SIZE)

  const jobs = data?.jobs ?? []
  const total = data?.total ?? 0
  const totalPages = data?.total_pages ?? 1

  // Reset to page 1 whenever filters change
  useEffect(() => {
    setPage(1)
  }, [filters])

  // Scroll to top on page change
  function goToPage(p) {
    setPage(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function updateFilter(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  function clearFilters() {
    setFilters(DEFAULT_FILTERS)
  }

  if (view === 'resume') {
    return <ResumeChecker onBack={() => setView('jobs')} />
  }

  return (
    <div className="min-h-screen bg-[#0f172a]">
      {/* Mobile backdrop */}
      {mobileFiltersOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setMobileFiltersOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed left-0 right-0 bottom-0 lg:top-0 lg:right-auto
          lg:w-72 w-full
          bg-slate-900 border-t lg:border-t-0 lg:border-r border-slate-800
          overflow-y-auto z-50 lg:z-auto
          transition-transform duration-300 ease-in-out
          ${mobileFiltersOpen ? 'translate-y-0' : 'translate-y-full lg:translate-y-0'}
          max-h-[88vh] lg:max-h-none lg:h-screen
          rounded-t-2xl lg:rounded-none
        `}
      >
        <Sidebar
          filters={filters}
          onChange={updateFilter}
          onClear={clearFilters}
          onClose={() => setMobileFiltersOpen(false)}
        />
      </aside>

      {/* Main area */}
      <main className="lg:ml-72 min-h-screen flex flex-col">
        {/* Top bar */}
        <div className="sticky top-0 z-30 bg-[#0f172a]/90 backdrop-blur border-b border-slate-800 px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <p className="text-slate-400 text-sm">
              {isPending
                ? 'Searching...'
                : (
                  <>
                    <span className="text-white font-semibold">{total}</span> jobs found
                    {totalPages > 1 && (
                      <span className="ml-2 text-slate-500">· page {page} of {totalPages}</span>
                    )}
                  </>
                )
              }
            </p>
            {isFetching && !isPending && (
              <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            )}
          </div>

          <div className="flex items-center gap-2">
            <RefreshButton />

            <button
              onClick={() => setView('resume')}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Resume Check
            </button>

            {/* Mobile filters button */}
            <button
              onClick={() => setMobileFiltersOpen(true)}
              className="lg:hidden flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z" />
              </svg>
              Filters
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6">
          {isPending ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : !jobs.length ? (
            <EmptyState onClear={clearFilters} />
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {jobs.map((job) => (
                  <JobCard key={job.id} job={job} onClick={() => setSelectedJob(job)} />
                ))}
              </div>
              <Pagination
                page={page}
                totalPages={totalPages}
                total={total}
                pageSize={PAGE_SIZE}
                onChange={goToPage}
              />
            </>
          )}
        </div>
      </main>

      {/* Slide-over detail panel */}
      <SlideOver job={selectedJob} onClose={() => setSelectedJob(null)} />
    </div>
  )
}
