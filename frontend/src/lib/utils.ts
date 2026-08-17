import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}

export function formatMoney(amount: number, currency = 'INR'): string {
  const locale = currency === 'INR' ? 'en-IN' : 'en-US'
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    maximumFractionDigits: amount % 1 === 0 ? 0 : 2,
  }).format(amount)
}

export function formatDate(value?: string | null, withTime = false): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  })
}

export function formatTime(value?: string | null): string {
  if (!value) return ''
  return new Date(value).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Thresholds in seconds, paired with the unit they convert to. */
const AGO_UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

export function timeAgo(value?: string | null): string {
  if (!value) return '—'
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) return '—'

  const seconds = (Date.now() - then) / 1000
  const magnitude = Math.abs(seconds)
  if (magnitude < 45) return seconds >= 0 ? 'just now' : 'in a moment'

  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  for (const [unit, unitSeconds] of AGO_UNITS) {
    if (magnitude >= unitSeconds) {
      // Negative = past, which is what RelativeTimeFormat expects.
      return formatter.format(-Math.round(seconds / unitSeconds), unit)
    }
  }
  return formatter.format(-Math.round(seconds), 'second')
}

export function titleCase(value?: string | null): string {
  if (!value) return ''
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/** Very small markdown subset: **bold**, *italic*, `code`, and `- ` bullets. */
export function renderMarkdown(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const lines = escaped.split('\n')
  const out: string[] = []
  let inList = false

  for (const line of lines) {
    const bullet = line.match(/^\s*[-*]\s+(.*)$/)
    if (bullet) {
      if (!inList) {
        out.push('<ul class="my-1.5 space-y-1 pl-4 list-disc marker:text-ink-400">')
        inList = true
      }
      out.push(`<li>${bullet[1]}</li>`)
      continue
    }
    if (inList) {
      out.push('</ul>')
      inList = false
    }
    out.push(line.trim() ? `<p>${line}</p>` : '')
  }
  if (inList) out.push('</ul>')

  return out
    .join('')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(
      /`([^`]+)`/g,
      '<code class="rounded bg-ink-100 px-1 py-0.5 text-[0.85em] font-mono">$1</code>',
    )
}

export const SENTIMENT_STYLES: Record<string, { label: string; className: string }> = {
  very_negative: { label: 'Very negative', className: 'bg-red-100 text-red-700 ring-red-600/20' },
  negative: { label: 'Negative', className: 'bg-orange-100 text-orange-700 ring-orange-600/20' },
  neutral: { label: 'Neutral', className: 'bg-ink-100 text-ink-600 ring-ink-500/20' },
  positive: { label: 'Positive', className: 'bg-emerald-100 text-emerald-700 ring-emerald-600/20' },
  very_positive: { label: 'Very positive', className: 'bg-emerald-100 text-emerald-800 ring-emerald-600/30' },
}

export const PRIORITY_STYLES: Record<string, string> = {
  urgent: 'bg-red-100 text-red-700 ring-red-600/20',
  high: 'bg-orange-100 text-orange-700 ring-orange-600/20',
  medium: 'bg-amber-100 text-amber-700 ring-amber-600/20',
  low: 'bg-ink-100 text-ink-600 ring-ink-500/20',
}

export const STATUS_STYLES: Record<string, string> = {
  open: 'bg-blue-100 text-blue-700 ring-blue-600/20',
  in_progress: 'bg-violet-100 text-violet-700 ring-violet-600/20',
  waiting_customer: 'bg-amber-100 text-amber-700 ring-amber-600/20',
  resolved: 'bg-emerald-100 text-emerald-700 ring-emerald-600/20',
  closed: 'bg-ink-100 text-ink-600 ring-ink-500/20',
  active: 'bg-blue-100 text-blue-700 ring-blue-600/20',
  escalated: 'bg-red-100 text-red-700 ring-red-600/20',
  abandoned: 'bg-ink-100 text-ink-500 ring-ink-500/20',
  delivered: 'bg-emerald-100 text-emerald-700 ring-emerald-600/20',
  shipped: 'bg-blue-100 text-blue-700 ring-blue-600/20',
  out_for_delivery: 'bg-violet-100 text-violet-700 ring-violet-600/20',
  packed: 'bg-amber-100 text-amber-700 ring-amber-600/20',
  confirmed: 'bg-sky-100 text-sky-700 ring-sky-600/20',
  pending: 'bg-ink-100 text-ink-600 ring-ink-500/20',
  cancelled: 'bg-red-100 text-red-700 ring-red-600/20',
  returned: 'bg-orange-100 text-orange-700 ring-orange-600/20',
}

export const CHART_COLORS = [
  '#6366f1', '#0ea5e9', '#10b981', '#f59e0b',
  '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6',
]

export function anonymousKey(): string {
  const KEY = 'rv.anonymous_key'
  let value = localStorage.getItem(KEY)
  if (!value) {
    value = `guest-${Math.random().toString(36).slice(2, 12)}`
    localStorage.setItem(KEY, value)
  }
  return value
}
