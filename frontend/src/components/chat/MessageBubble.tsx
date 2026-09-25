import {
  AlertTriangle, BookOpen, Bot, CheckCircle2, ChevronDown, Clock,
  Mic, Sparkles, User as UserIcon, Wrench, Zap,
} from 'lucide-react'
import { useState } from 'react'

import type { ChatMessage } from '@/store/chat'
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
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const [showTrace, setShowTrace] = useState(false)
  const [showSources, setShowSources] = useState(false)
  const isUser = message.role === 'user'

  const tools = message.toolTrace ?? []
  const citations = message.citations ?? []
  const sentiment = message.sentiment ? SENTIMENT_STYLES[message.sentiment] : null

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
