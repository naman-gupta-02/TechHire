import { formatSalary, getSkillClass, timeAgo, SOURCE_CLASS, SOURCE_LABEL, WORK_MODE_CLASS, JOB_TYPE_LABEL, JOB_TYPE_CLASS } from '../utils/format'

function VisaBadge({ value }) {
  if (value === true) return (
    <span className="inline-flex items-center gap-1 text-xs font-medium bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full whitespace-nowrap">
      ✓ Visa
    </span>
  )
  if (value === false) return (
    <span className="inline-flex items-center gap-1 text-xs font-medium bg-red-100 text-red-600 px-2 py-0.5 rounded-full whitespace-nowrap">
      ✗ No Visa
    </span>
  )
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full whitespace-nowrap">
      ? Visa
    </span>
  )
}

function SkillBadge({ skill }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${getSkillClass(skill)}`}>
      {skill}
    </span>
  )
}

export default function JobCard({ job, onClick }) {
  const visibleSkills = job.required_skills.slice(0, 4)
  const extraCount = job.required_skills.length - 4
  const salary = formatSalary(job.salary_min, job.salary_max)

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl p-5 shadow-md hover:shadow-xl transition-all duration-200 cursor-pointer hover:-translate-y-0.5 group border border-transparent hover:border-indigo-100 flex flex-col"
    >
      {/* Title row */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-900 text-[0.93rem] leading-snug group-hover:text-indigo-700 transition-colors line-clamp-2">
            {job.title}
          </h3>
          <p className="text-slate-500 text-sm mt-0.5 truncate">
            {job.company}
            {job.city && ` · ${job.city}, ${job.state}`}
          </p>
        </div>
        <VisaBadge value={job.visa_sponsorship} />
      </div>

      {/* Skill badges */}
      {visibleSkills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {visibleSkills.map((s) => <SkillBadge key={s} skill={s} />)}
          {extraCount > 0 && (
            <span className="text-xs text-slate-400 self-center">+{extraCount} more</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="mt-auto flex items-end justify-between pt-3 border-t border-slate-100">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SOURCE_CLASS[job.source] ?? 'bg-slate-100 text-slate-600'}`}>
            {SOURCE_LABEL[job.source] ?? job.source}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${WORK_MODE_CLASS[job.work_mode] ?? 'bg-slate-100 text-slate-600'}`}>
            {job.work_mode}
          </span>
          {job.job_type && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${JOB_TYPE_CLASS[job.job_type] ?? 'bg-slate-100 text-slate-600'}`}>
              {JOB_TYPE_LABEL[job.job_type] ?? job.job_type}
            </span>
          )}
          {job.start_date_text && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              {job.start_date_text}
            </span>
          )}
        </div>
        <div className="text-right flex-shrink-0 ml-2">
          {salary ? (
            <p className="text-sm font-semibold text-slate-800">{salary}</p>
          ) : (
            <p className="text-xs text-slate-400">Not listed</p>
          )}
          <p className="text-xs text-slate-400">{timeAgo(job.posted_at)}</p>
        </div>
      </div>
    </div>
  )
}
