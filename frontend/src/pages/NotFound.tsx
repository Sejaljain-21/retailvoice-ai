import { Bot, Home, MessageSquare, ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

export function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-ink-950 px-6 text-center relative overflow-hidden">
      {/* Ambient glow blobs */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-brand-600/10 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-[500px] w-[500px] rounded-full bg-violet-600/10 blur-[120px]" />

      {/* 404 Display */}
      <div className="relative z-10 flex flex-col items-center">
        {/* Icon */}
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-tr from-brand-600 to-violet-500 shadow-2xl shadow-brand-500/30 ring-1 ring-white/10">
          <Bot className="h-10 w-10 text-white" />
        </div>

        {/* Big 404 */}
        <div className="relative mb-2">
          <span className="select-none text-[9rem] font-black leading-none tracking-tighter text-white/5">
            404
          </span>
          <span className="absolute inset-0 flex items-center justify-center text-[4.5rem] font-black leading-none tracking-tighter bg-gradient-to-br from-brand-400 to-violet-400 bg-clip-text text-transparent">
            404
          </span>
        </div>

        <h1 className="text-2xl font-bold text-white mb-2">Page Not Found</h1>
        <p className="text-sm text-ink-400 max-w-sm leading-relaxed mb-8">
          Aura looked everywhere but couldn't find the page you're looking for. It may have been moved,
          deleted, or you may have followed an outdated link.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-800 px-4 py-2.5 text-sm font-medium text-ink-200 transition hover:bg-ink-700 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Go Back
          </button>

          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:from-brand-700 hover:to-violet-700 active:scale-95"
          >
            <Home className="h-4 w-4" />
            Return Home
          </Link>

          <Link
            to="/help"
            className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-800 px-4 py-2.5 text-sm font-medium text-ink-200 transition hover:bg-ink-700 hover:text-white"
          >
            <MessageSquare className="h-4 w-4" />
            Help Centre
          </Link>
        </div>

        {/* Subtle brand footer */}
        <p className="mt-12 text-[11px] text-ink-600">
          RetailVoice · Powered by Aura AI
        </p>
      </div>
    </div>
  )
}
