import {
  AlertTriangle, BookOpen, Bot, CheckCircle2, ChevronDown, Clock,
  MapPin, Mic, Package, ShieldCheck, Sparkles, Truck, User as UserIcon, Wrench, Zap,
} from 'lucide-react'
import { useState } from 'react'

import { useChat, type ChatMessage } from '@/store/chat'
import { Badge } from '@/components/ui'
import { cn, formatTime, renderMarkdown, SENTIMENT_STYLES, titleCase } from '@/lib/utils'

/** Human-readable names for the agent's tools, shown in the trace. */
const TOOL_LABELS: Record<string, string> = {
  lookup_order: 'Looked up the order',
  track_shipment: 'Checked courier tracking',
  cancel_order: 'Cancelled the order',
  initiate_return: 'Started a return',
  get_order_history: 'Read the order history',
  check_product_availability: 'Checked stock',
  recommend_products: 'Searched the catalogue',
  check_delivery_estimate: 'Checked delivery to the pincode',
  find_nearby_store: 'Found nearby stores',
  search_knowledge_base: 'Searched the help centre',
  get_customer_profile: 'Read the customer profile',
  create_support_ticket: 'Created a support ticket',
  escalate_to_human: 'Escalated to a human agent',
  apply_goodwill_coupon: 'Issued a goodwill voucher',
  send_security_otp: 'Dispatched security verification SMS',
  verify_security_otp: 'Identity verification completed',
  place_order: 'Booked and placed order in database',
  end_voice_call: 'Disconnected voice call',
  record_csat_feedback: 'Satisfaction score recorded',
}

/* ──────────────────────────────────────────────────────────────
   Interactive Parcel Delivery Stepper
   Parses track_shipment tool result and renders a visual courier
   tracker directly in the chat bubble.
────────────────────────────────────────────────────────────── */
interface ShipmentResult {
  order_id?: string
  status?: string
  courier?: string
  tracking_number?: string
  estimated_delivery?: string
  current_location?: string
  events?: Array<{ timestamp: string; description: string; location?: string }>
}

const COURIER_STEPS = [
  { key: 'ordered', label: 'Ordered' },
  { key: 'dispatched', label: 'Dispatched' },
  { key: 'in_transit', label: 'In Transit' },
  { key: 'out_for_delivery', label: 'Out for Delivery' },
  { key: 'delivered', label: 'Delivered' },
] as const

type CourierStepKey = (typeof COURIER_STEPS)[number]['key']

function statusToStep(status: string | undefined): number {
  const s = (status ?? '').toLowerCase().replace(/\s+/g, '_')
  if (s.includes('delivered') && !s.includes('out_for')) return 4
  if (s.includes('out_for_delivery')) return 3
  if (s.includes('in_transit') || s.includes('transit') || s.includes('shipped')) return 2
  if (s.includes('dispatch') || s.includes('packed') || s.includes('confirmed')) return 1
  return 0
}

function ParcelStepper({ result }: { result: ShipmentResult }) {
  const currentStep = statusToStep(result.status)

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-violet-200/60 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-4 shadow-[0_0_24px_rgba(139,92,246,0.2)]">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-600/80">
            <Truck className="h-3.5 w-3.5 text-white" />
          </div>
          <span className="text-xs font-bold text-violet-200">Live Shipment Tracker</span>
        </div>
        {result.order_id && (
          <span className="rounded-full bg-white/10 px-2 py-0.5 font-mono text-[10px] text-slate-300">
            {result.order_id}
          </span>
        )}
      </div>

      {/* Step indicators */}
      <div className="relative mb-4">
        {/* Connecting line */}
        <div className="absolute left-3 top-3 h-0.5 right-3 bg-white/10" />
        <div
          className="absolute left-3 top-3 h-0.5 bg-gradient-to-r from-violet-500 to-emerald-400 transition-all duration-700"
          style={{ width: currentStep === 0 ? '0%' : `${Math.min((currentStep / 4) * 100, 100)}%` }}
        />

        <div className="relative flex justify-between">
          {COURIER_STEPS.map((step, index) => {
            const done = index <= currentStep
            const active = index === currentStep
            return (
              <div key={step.key} className="flex flex-col items-center gap-1.5" style={{ width: '20%' }}>
                <div
                  className={cn(
                    'relative z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 transition-all duration-500',
                    done
                      ? 'border-emerald-400 bg-emerald-500 shadow-[0_0_12px_rgba(52,211,153,0.5)]'
                      : 'border-white/20 bg-slate-800',
                    active && 'scale-110 shadow-[0_0_16px_rgba(52,211,153,0.7)]',
                  )}
                >
                  {done ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-white" />
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-white/20" />
                  )}
                </div>
                <span
                  className={cn(
                    'text-center text-[9px] font-medium leading-tight',
                    done ? 'text-emerald-300' : 'text-slate-500',
                    active && 'text-emerald-200 font-bold',
                  )}
                >
                  {step.label}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Details row */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[10px]">
        {result.courier && (
          <span className="flex items-center gap-1 text-slate-400">
            <Package className="h-3 w-3 text-violet-400" />
            <span className="text-violet-200 font-medium">{result.courier}</span>
          </span>
        )}
        {result.current_location && (
          <span className="flex items-center gap-1 text-slate-400">
            <MapPin className="h-3 w-3 text-rose-400" />
            <span className="text-slate-300">{result.current_location}</span>
          </span>
        )}
        {result.estimated_delivery && (
          <span className="flex items-center gap-1 text-slate-400">
            <Clock className="h-3 w-3 text-amber-400" />
            <span className="text-amber-200">ETA: {result.estimated_delivery}</span>
          </span>
        )}
      </div>

      {/* Recent events */}
      {result.events && result.events.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t border-white/10 pt-2.5">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-500">
            Recent Updates
          </span>
          {result.events.slice(0, 3).map((ev, i) => (
            <div key={i} className="flex items-start gap-2 text-[10px]">
              <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
              <div>
                <span className="text-slate-300">{ev.description}</span>
                {ev.location && (
                  <span className="ml-1 text-slate-500">· {ev.location}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ──────────────────────────────────────────────────────────────
   Autonomous OTP Verification Card (Chat & Voice authorization)
────────────────────────────────────────────────────────────── */
function OtpVerificationCard({
  verified,
  destination,
  liveCode,
  onSendCode,
}: {
  verified: boolean
  destination?: string
  liveCode?: string
  onSendCode?: (code: string) => void
}) {
  const [code, setCode] = useState('')

  if (verified) {
    return (
      <div className="mt-3 overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/80 via-slate-950 to-slate-900 p-3.5 shadow-[0_0_20px_rgba(16,185,129,0.15)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-emerald-200">Security Verification Granted</div>
              <div className="text-[10px] text-emerald-400/80">Autonomous voice & transaction identity confirmed via SMS</div>
            </div>
          </div>
          <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-300 border border-emerald-500/20">
            ✓ AUTHORIZED
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-violet-500/40 bg-gradient-to-br from-violet-950/90 via-slate-950 to-indigo-950 p-3.5 shadow-[0_0_24px_rgba(139,92,246,0.25)]">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600/30 text-violet-300 border border-violet-500/30">
            <ShieldCheck className="h-4 w-4 text-violet-400" />
          </div>
          <div>
            <div className="text-xs font-bold text-violet-200">Autonomous Security Verification</div>
            <div className="text-[10px] text-slate-400">
              4-digit code dispatched to <span className="font-semibold text-violet-300 font-mono">{destination || 'registered mobile'}</span>
            </div>
          </div>
        </div>
        <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-semibold text-violet-300 border border-violet-500/30">
          REQUIRED
        </span>
      </div>

      {/* Live incoming SMS notification simulator */}
      {liveCode && (
        <div className="mb-2.5 flex items-center justify-between rounded-lg bg-emerald-950/60 border border-emerald-500/30 px-3 py-2 text-[11px] text-emerald-300">
          <span className="flex items-center gap-1.5 font-medium">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Live SMS received on {destination}:
          </span>
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold tracking-widest bg-emerald-500/20 px-2 py-0.5 rounded text-emerald-200">
              {liveCode}
            </span>
            <button
              type="button"
              onClick={() => setCode(liveCode)}
              className="text-[10px] underline text-emerald-400 hover:text-emerald-200"
            >
              Auto-fill
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 pt-1">
        <input
          type="text"
          maxLength={4}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 4))}
          className="w-24 rounded-lg border border-violet-500/40 bg-slate-900/90 px-3 py-1.5 text-center font-mono text-xs tracking-widest text-violet-200 placeholder:text-slate-500 focus:border-violet-400 focus:outline-none"
          placeholder="Enter OTP"
        />
        <button
          type="button"
          disabled={code.length < 4}
          onClick={() => onSendCode?.(code)}
          className="flex-1 rounded-lg bg-violet-600 disabled:opacity-40 px-3 py-1.5 text-xs font-semibold text-white shadow-md hover:bg-violet-500 active:scale-[0.98] transition flex items-center justify-center gap-1.5"
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          <span>Confirm Security OTP {code ? `(${code})` : ''}</span>
        </button>
      </div>
    </div>
  )
}

/* ──────────────────────────────────────────────────────────────
   Extract parcel shipment data from tool trace results
────────────────────────────────────────────────────────────── */
function extractShipmentData(
  toolTrace: import('@/lib/types').ToolTrace[],
): ShipmentResult | null {
  const trackTool = toolTrace.find((t) => t.tool === 'track_shipment' && t.success)
  if (!trackTool) return null
  const r = trackTool.result as Record<string, unknown>
  if (!r || typeof r !== 'object') return null
  return r as unknown as ShipmentResult
}

/* ──────────────────────────────────────────────────────────────
   Main MessageBubble Component
────────────────────────────────────────────────────────────── */
export function MessageBubble({ message }: { message: ChatMessage }) {
  const [showTrace, setShowTrace] = useState(false)
  const [showSources, setShowSources] = useState(false)
  const { send } = useChat()
  const isUser = message.role === 'user'

  const tools = message.toolTrace ?? []
  const citations = message.citations ?? []
  const sentiment = message.sentiment ? SENTIMENT_STYLES[message.sentiment] : null
  const shipment = !isUser ? extractShipmentData(tools) : null

  const isOtpVerified = tools.some((t) => t.tool === 'verify_security_otp' && t.success)
  // Show OTP card if send_security_otp was called or requires_otp is true
  const isOtpPrompted =
    !isUser &&
    !isOtpVerified &&
    (tools.some((t) => t.tool === 'send_security_otp') ||
      tools.some((t) => Boolean((t.result as Record<string, unknown> | undefined)?.requires_otp)))

  const otpTool = tools.find(
    (t) =>
      t.tool === 'send_security_otp' ||
      t.tool === 'verify_security_otp' ||
      Boolean((t.result as Record<string, unknown> | undefined)?.requires_otp),
  )
  const otpRes = (otpTool?.result as Record<string, unknown>) || {}
  const liveCode = (otpRes.live_code as string) || (otpRes.code as string) || undefined
  const maskedPhone =
    (otpRes.masked_phone as string) ||
    (otpRes.destination as string) ||
    message.content.match(/\(\+91[^\)]+\)/)?.[0]?.replace(/[()]/g, '') ||
    'your registered mobile'

  return (
    <div
      className={cn('flex animate-fade-up gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      <div
        className={cn(
          'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-ink-200 text-ink-600' : 'bg-brand-600 text-white',
        )}
        aria-hidden
      >
        {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className={cn('min-w-0 max-w-[85%]', isUser && 'flex flex-col items-end')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
            isUser
              ? 'rounded-tr-sm bg-brand-600 text-white'
              : message.failed
                ? 'rounded-tl-sm border border-amber-200 bg-amber-50 text-amber-900'
                : 'rounded-tl-sm border border-ink-200 bg-white text-ink-800',
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div
              className="prose-chat"
              // The agent's own output only; sanitised by renderMarkdown, which
              // escapes all HTML before applying its small markdown subset.
              dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
            />
          )}
        </div>

        {/* ── Interactive Parcel Delivery Stepper ── */}
        {shipment && <ParcelStepper result={shipment} />}

        {/* ── Security OTP Verification Card ── */}
        {(isOtpVerified || isOtpPrompted) && (
          <OtpVerificationCard
            verified={isOtpVerified}
            destination={maskedPhone}
            liveCode={liveCode}
            onSendCode={(otpCode) => {
              void send(`My security verification code is ${otpCode}`)
            }}
          />
        )}

        {/* Escalation banner */}
        {message.escalated && (
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            <span>
              Handed to a human agent
              {message.ticketNumber && (
                <>
                  {' '}· ref <span className="font-semibold">{message.ticketNumber}</span>
                </>
              )}
            </span>
          </div>
        )}

        {/* Grounding + telemetry */}
        {!isUser && (tools.length > 0 || citations.length > 0 || message.latencyMs) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-500">
            {tools.length > 0 && (
              <button
                onClick={() => setShowTrace((v) => !v)}
                className="inline-flex items-center gap-1 rounded-full border border-violet-200/80 bg-violet-50/80 px-2.5 py-0.5 font-medium text-violet-700 transition hover:bg-violet-100/90 shadow-2xs"
              >
                <Zap className="h-3 w-3 text-violet-600" />
                {tools.length} autonomous step{tools.length > 1 ? 's' : ''}
                <ChevronDown className={cn('h-3 w-3 transition', showTrace && 'rotate-180')} />
              </button>
            )}
            {citations.length > 0 && (
              <button
                onClick={() => setShowSources((v) => !v)}
                className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700 transition hover:bg-emerald-100"
              >
                <BookOpen className="h-3 w-3" />
                {citations.length} source{citations.length > 1 ? 's' : ''}
                <ChevronDown className={cn('h-3 w-3 transition', showSources && 'rotate-180')} />
              </button>
            )}
            {message.latencyMs != null && (
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {(message.latencyMs / 1000).toFixed(1)}s
              </span>
            )}
            {message.intent && message.intent !== 'unknown' && (
              <span className="text-ink-400">{titleCase(message.intent)}</span>
            )}
          </div>
        )}

        {/* Autonomous Reasoning & Execution Flow */}
        {showTrace && tools.length > 0 && (
          <div className="mt-2.5 w-full space-y-2 rounded-2xl border border-violet-400/40 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-3.5 text-white shadow-[0_0_25px_rgba(139,92,246,0.25)]">
            <div className="flex items-center justify-between border-b border-white/10 pb-2 text-[11px] font-semibold text-violet-200">
              <span className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-violet-400" />
                Autonomous Step-by-Step Reasoning
              </span>
              <span className="text-[10px] font-medium text-emerald-400 font-mono bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                Verified against store records
              </span>
            </div>

            <ul className="space-y-2 pt-1">
              {tools.map((tool, index) => (
                <li key={`${tool.tool}-${index}`} className="flex items-start gap-2.5 rounded-xl bg-white/5 border border-white/10 p-2.5 text-xs transition hover:border-violet-400/40">
                  <div className="flex flex-col items-center">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-violet-600/80 text-[10px] font-bold text-white shadow-2xs">
                      {index + 1}
                    </span>
                    {index < tools.length - 1 && (
                      <span className="w-0.5 h-3 bg-violet-500/30 my-0.5" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-bold text-white flex items-center gap-1.5">
                        {TOOL_LABELS[tool.tool] ?? titleCase(tool.tool)}
                        {tool.success ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                        )}
                      </p>
                      <span className="text-[10px] font-mono font-medium text-emerald-300 bg-emerald-500/20 px-1.5 py-0.5 rounded border border-emerald-400/30 shrink-0">
                        {tool.duration_ms}ms
                      </span>
                    </div>

                    {Object.keys(tool.arguments ?? {}).length > 0 && (
                      <p className="mt-1 text-[11px] text-slate-300 font-medium truncate">
                        Context:{' '}
                        <span className="text-violet-200 font-mono bg-white/5 px-1 py-0.5 rounded">
                          {Object.entries(tool.arguments ?? {})
                            .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
                            .join(', ')}
                        </span>
                      </p>
                    )}
                    {tool.error && <p className="mt-1 text-[11px] text-red-400">{tool.error}</p>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Citations */}
        {showSources && citations.length > 0 && (
          <ul className="mt-2 w-full space-y-2 rounded-lg border border-emerald-200 bg-emerald-50/60 p-2.5">
            {citations.map((citation) => (
              <li key={citation.document_id + citation.snippet.slice(0, 16)} className="text-xs">
                <p className="font-semibold text-emerald-900">
                  {citation.title}
                  <span className="ml-1.5 font-normal text-emerald-600">
                    {(citation.score * 100).toFixed(0)}% match
                  </span>
                </p>
                <p className="mt-0.5 line-clamp-3 text-emerald-800/80">{citation.snippet}</p>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-1 flex items-center gap-2 px-1 text-[11px] text-ink-400">
          {message.viaVoice && <Mic className="h-3 w-3" aria-label="Spoken" />}
          <span>{formatTime(message.createdAt)}</span>
          {isUser && sentiment && (
            <Badge className={cn('!py-0 !text-[10px]', sentiment.className)}>
              {sentiment.label}
            </Badge>
          )}
        </div>
      </div>
    </div>
  )
}
