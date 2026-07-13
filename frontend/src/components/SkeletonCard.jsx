export default function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl p-5 shadow-md animate-pulse">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 space-y-2">
          <div className="h-5 bg-slate-200 rounded-md w-3/4" />
          <div className="h-4 bg-slate-200 rounded-md w-1/2" />
        </div>
        <div className="h-6 w-16 bg-slate-200 rounded-full" />
      </div>
      <div className="flex gap-2 mb-4">
        <div className="h-6 w-16 bg-slate-200 rounded-full" />
        <div className="h-6 w-20 bg-slate-200 rounded-full" />
        <div className="h-6 w-14 bg-slate-200 rounded-full" />
      </div>
      <div className="flex items-center justify-between pt-3 border-t border-slate-100">
        <div className="flex gap-2">
          <div className="h-5 w-16 bg-slate-200 rounded-full" />
          <div className="h-5 w-14 bg-slate-200 rounded-full" />
        </div>
        <div className="space-y-1 text-right">
          <div className="h-4 w-24 bg-slate-200 rounded-md ml-auto" />
          <div className="h-3 w-16 bg-slate-200 rounded-md ml-auto" />
        </div>
      </div>
    </div>
  )
}
