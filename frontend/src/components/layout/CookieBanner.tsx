import { Cookie, X, Check, Settings2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const STORAGE_KEY = 'rv_cookie_consent'

type ConsentState = 'pending' | 'all' | 'essential'

export function CookieBanner() {
  const [state, setState] = useState<ConsentState>('pending')
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) {
      // Small delay so page loads first
      const timer = setTimeout(() => setVisible(true), 800)
      return () => clearTimeout(timer)
    }
    setState(stored as ConsentState)
  }, [])

  const accept = (choice: 'all' | 'essential') => {
    localStorage.setItem(STORAGE_KEY, choice)
    setState(choice)
    setVisible(false)
  }

  if (!visible || state !== 'pending') return null

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label="Cookie consent"
      className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-xl animate-slide-up"
    >
      <div className="rounded-2xl border border-ink-200 bg-white/95 p-5 shadow-2xl ring-1 ring-black/5 backdrop-blur-md">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
            <Cookie className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink-900">We use cookies 🍪</p>
            <p className="mt-0.5 text-xs text-ink-500 leading-relaxed">
              We use essential cookies to keep the platform working and, with your consent, analytics cookies to
              improve your experience. See our{' '}
              <Link to="/privacy" className="text-brand-600 hover:underline font-medium">
                Privacy Policy
              </Link>{' '}
              for details.
            </p>
          </div>
          <button
            onClick={() => accept('essential')}
            className="shrink-0 rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-600 transition"
            aria-label="Accept essential cookies only and close"
            title="Decline optional cookies"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button
            id="cookie-essential-btn"
            onClick={() => accept('essential')}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-ink-200 bg-ink-50 px-3 py-2 text-xs font-medium text-ink-700 transition hover:bg-ink-100"
          >
            <Settings2 className="h-3.5 w-3.5" />
            Essential Only
          </button>
          <button
            id="cookie-accept-all-btn"
            onClick={() => accept('all')}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:from-brand-700 hover:to-violet-700 active:scale-95"
          >
            <Check className="h-3.5 w-3.5" />
            Accept All
          </button>
        </div>
      </div>
    </div>
  )
}
