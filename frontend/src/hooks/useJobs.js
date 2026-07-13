import { useQuery } from '@tanstack/react-query'

const API_BASE = 'http://localhost:8000'

async function fetchJobs(filters, page, pageSize) {
  const params = new URLSearchParams()

  if (filters.search.trim()) params.set('search', filters.search.trim())
  if (filters.visaOnly) params.set('visa_only', 'true')
  if (filters.salaryMin > 0) params.set('salary_min', filters.salaryMin)
  if (filters.salaryMax < 300000) params.set('salary_max', filters.salaryMax)
  if (filters.datePosted !== 'any') params.set('date_posted', filters.datePosted)
  params.set('sort', filters.sort)
  params.set('page', page)
  params.set('page_size', pageSize)

  filters.skills.forEach((s) => params.append('skills', s))
  filters.workModes.forEach((m) => params.append('work_modes', m))
  filters.experienceLevels.forEach((l) => params.append('experience_levels', l))
  filters.seasons.forEach((s) => params.append('seasons', s))

  const res = await fetch(`${API_BASE}/jobs?${params.toString()}`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export function useJobs(filters, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['jobs', filters, page, pageSize],
    queryFn: () => fetchJobs(filters, page, pageSize),
    staleTime: 30_000,
    placeholderData: (prev) => prev, // keep old data visible while fetching next page
  })
}
