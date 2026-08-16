import {
  AlertTriangle, BookOpen, Bot, CheckCircle2, ChevronDown, Clock,
  Mic, User as UserIcon, Wrench,
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
                className="inline-flex items-center gap-1 rounded-full bg-ink-100 px-2 py-0.5 font-medium text-ink-600 transition hover:bg-ink-200"
              >
                <Wrench className="h-3 w-3" />
                {tools.length} action{tools.length > 1 ? 's' : ''}
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

        {/* Tool trace */}
        {showTrace && tools.length > 0 && (
          <ul className="mt-2 w-full space-y-1.5 rounded-lg border border-ink-200 bg-ink-50 p-2.5">
            {tools.map((tool, index) => (
              <li key={`${tool.tool}-${index}`} className="flex items-start gap-2 text-xs">
                {tool.success ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" />
                )}
                <div className="min-w-0">
                  <p className="font-medium text-ink-700">
                    {TOOL_LABELS[tool.tool] ?? titleCase(tool.tool)}
                    <span className="ml-1.5 font-normal text-ink-400">{tool.duration_ms}ms</span>
                  </p>
                  {Object.keys(tool.arguments ?? {}).length > 0 && (
                    <p className="truncate font-mono text-[11px] text-ink-500">
                      {JSON.stringify(tool.arguments)}
                    </p>
                  )}
                  {tool.error && <p className="text-[11px] text-red-600">{tool.error}</p>}
                </div>
              </li>
            ))}
          </ul>
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
