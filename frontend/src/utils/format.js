export function timeAgo(dateStr) {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const mins = Math.floor(diff / 60_000)
  const hours = Math.floor(diff / 3_600_000)
  const days = Math.floor(diff / 86_400_000)
  if (mins < 60) return mins <= 1 ? 'Just now' : `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return '1 day ago'
  if (days < 7) return `${days} days ago`
  const weeks = Math.floor(days / 7)
  if (weeks === 1) return '1 week ago'
  if (weeks < 5) return `${weeks} weeks ago`
  const months = Math.floor(days / 30)
  return `${months} month${months !== 1 ? 's' : ''} ago`
}

export function formatSalary(min, max) {
  if (!min && !max) return null
  const fmt = (n) => `$${Math.round(n / 1000)}k`
  if (min && max) return `${fmt(min)} – ${fmt(max)}`
  if (min) return `${fmt(min)}+`
  return `Up to ${fmt(max)}`
}

// Full class strings so Tailwind includes them in the build
const SKILL_CATEGORY_CLASSES = {
  language:  'bg-blue-100 text-blue-700',
  framework: 'bg-emerald-100 text-emerald-700',
  cloud:     'bg-amber-100 text-amber-700',
  database:  'bg-violet-100 text-violet-700',
  ml:        'bg-rose-100 text-rose-700',
  default:   'bg-slate-100 text-slate-600',
}

const SKILL_CATEGORIES = {
  language:  ['python', 'java', 'javascript', 'typescript', 'go', 'golang', 'rust', 'kotlin', 'swift', 'scala', 'c++', 'c#', 'ruby', 'php', 'r', 'bash', 'objective-c'],
  framework: ['react', 'next.js', 'angular', 'vue', 'svelte', 'django', 'flask', 'fastapi', 'node.js', 'express', 'spring', 'rails', 'laravel'],
  cloud:     ['aws', 'gcp', 'azure', 'docker', 'kubernetes', 'terraform', 'ansible', 'jenkins', 'ci/cd', 'linux', 'github actions', 'xcode', 'ios', 'android'],
  database:  ['postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch', 'cassandra', 'dynamodb', 'snowflake', 'databricks'],
  ml:        ['tensorflow', 'pytorch', 'scikit-learn', 'machine learning', 'deep learning', 'nlp', 'computer vision', 'cuda', 'pandas', 'numpy', 'spark', 'kafka', 'airflow', 'dbt'],
}

export function getSkillClass(skill) {
  const s = skill.toLowerCase()
  for (const [cat, keys] of Object.entries(SKILL_CATEGORIES)) {
    if (keys.some((k) => s === k || s.includes(k))) return SKILL_CATEGORY_CLASSES[cat]
  }
  return SKILL_CATEGORY_CLASSES.default
}

export const SOURCE_LABEL = {
  lever: 'Lever', indeed: 'Indeed', glassdoor: 'Glassdoor', handshake: 'Handshake',
}

// Full class strings for each source badge (Tailwind scan)
export const SOURCE_CLASS = {
  lever:     'bg-cyan-100 text-cyan-700',
  indeed:    'bg-blue-100 text-blue-700',
  glassdoor: 'bg-green-100 text-green-700',
  handshake: 'bg-purple-100 text-purple-700',
}

export const WORK_MODE_CLASS = {
  remote: 'bg-emerald-100 text-emerald-700',
  hybrid: 'bg-amber-100 text-amber-700',
  onsite: 'bg-slate-100 text-slate-600',
}

export const JOB_TYPE_LABEL = {
  FULLTIME: 'Full-time',
  INTERN:   'Internship',
  CONTRACT: 'Contract',
  PARTTIME: 'Part-time',
}

export const JOB_TYPE_CLASS = {
  FULLTIME: 'bg-indigo-50 text-indigo-700',
  INTERN:   'bg-pink-100 text-pink-700',
  CONTRACT: 'bg-orange-100 text-orange-700',
  PARTTIME: 'bg-teal-100 text-teal-700',
}
