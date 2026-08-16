import {
  AlertTriangle, Bot, MessagesSquare, Phone, RefreshCw, Send, User as UserIcon,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { PageHeader } from '@/components/layout/AppShell'
import {
  Badge, Button, Card, EmptyState, ErrorBanner, Input, Select, Skeleton,
} from '@/components/ui'
import { api } from '@/lib/api'
import type { Conversation, ConversationDetail } from '@/lib/types'
import {
  SENTIMENT_STYLES, STATUS_STYLES, cn, formatDate, renderMarkdown, timeAgo, titleCase,
} from '@/lib/utils'

const CHANNEL_ICONS: Record<string, typeof MessagesSquare> = {
  web_chat: MessagesSquare,
  voice: Phone,
  phone: Phone,
  whatsapp: MessagesSquare,
  email: MessagesSquare,
}

export function AgentConsole() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selected, setSelected] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'escalated' | 'active'>('escalated')
  const [channel, setChannel] = useState('')
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .conversations({
        page_size: 50,
        escalated_only: filter === 'escalated',
        status: filter === 'active' ? 'active' : undefined,
        channel: channel || undefined,
      })
      .then((page) => setConversations(page.items))
      .catch((err) =>
        setError(err instanceof Error ? err.message : 'Could not load conversations.'),
      )
      .finally(() => setLoading(false))
  }, [filter, channel])

  useEffect(load, [load])

  async function openConversation(id: string) {
    setLoadingDetail(true)
    try {
      setSelected(await api.conversation(id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open that conversation.')
    } finally {
      setLoadingDetail(false)
    }
  }

  async function sendReply() {
    if (!selected || !reply.trim()) return
    setSending(true)
    try {
      await api.agentReply(selected.id, reply.trim())
      setReply('')
      await openConversation(selected.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The reply was not delivered.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <PageHeader
        title="Conversations"
        description="Every AI-handled thread, with the escalated ones first."
        action={
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      {error && <ErrorBanner message={error} onRetry={load} />}

      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        {/* Queue */}
        <div className="space-y-3">
          <div className="flex gap-2">
            <Select
              value={filter}
              onChange={(e) => setFilter(e.target.value as typeof filter)}
              className="flex-1"
            >
              <option value="escalated">Escalated only</option>
              <option value="active">Active</option>
              <option value="all">All conversations</option>
            </Select>
            <Select value={channel} onChange={(e) => setChannel(e.target.value)} className="flex-1">
              <option value="">All channels</option>
              <option value="web_chat">Web chat</option>
              <option value="voice">Voice</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="phone">Phone</option>
            </Select>
          </div>

          <div className="max-h-[calc(100vh-14rem)] space-y-2 overflow-y-auto scroll-thin pr-1">
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <Card key={i} className="p-3">
                  <Skeleton className="h-3 w-2/3" />
                  <Skeleton className="mt-2 h-3 w-1/3" />
                </Card>
              ))
            ) : conversations.length === 0 ? (
              <Card>
                <EmptyState
                  icon={<MessagesSquare className="h-8 w-8" />}
                  title="Nothing in this queue"
                  description="Try a different filter."
                />
              </Card>
            ) : (
              conversations.map((conversation) => {
                const Icon = CHANNEL_ICONS[conversation.channel] ?? MessagesSquare
                const sentiment = SENTIMENT_STYLES[conversation.last_sentiment]
                return (
                  <button
                    key={conversation.id}
                    onClick={() => openConversation(conversation.id)}
                    className={cn(
                      'w-full rounded-lg border bg-white p-3 text-left transition hover:border-brand-300 hover:shadow-sm',
                      selected?.id === conversation.id
                        ? 'border-brand-500 ring-1 ring-brand-500'
                        : 'border-ink-200',
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink-900">
                          {conversation.title}
                        </p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <Badge className={STATUS_STYLES[conversation.status]} dot>
                            {titleCase(conversation.status)}
                          </Badge>
                          {sentiment && (
                            <Badge className={sentiment.className}>{sentiment.label}</Badge>
                          )}
                          {conversation.primary_intent !== 'unknown' && (
                            <span className="text-[11px] text-ink-400">
                              {titleCase(conversation.primary_intent)}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-[11px] text-ink-400">
                          {conversation.message_count} messages ·{' '}
                          {timeAgo(conversation.updated_at)}
                        </p>
                      </div>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Detail */}
        <Card className="flex min-h-[520px] flex-col overflow-hidden">
          {loadingDetail ? (
            <div className="space-y-3 p-5">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-2/3" />
            </div>
          ) : !selected ? (
            <EmptyState
              icon={<MessagesSquare className="h-10 w-10" />}
              title="Select a conversation"
              description="Pick a thread on the left to read the full transcript, the tools the agent used, and to reply as a human agent."
            />
          ) : (
            <>
              <div className="border-b border-ink-200 px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold text-ink-900">
                      {selected.title}
                    </h2>
                    <p className="mt-0.5 text-xs text-ink-500">
                      {titleCase(selected.channel)} · opened {formatDate(selected.created_at, true)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge className={STATUS_STYLES[selected.status]} dot>
                      {titleCase(selected.status)}
                    </Badge>
                    {selected.is_escalated && (
                      <Badge className="bg-red-100 text-red-700 ring-red-600/20">
                        <AlertTriangle className="h-3 w-3" />
                        {titleCase(selected.escalation_reason ?? 'escalated')}
                      </Badge>
                    )}
                  </div>
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] sm:grid-cols-4">
                  {[
                    ['Intent', titleCase(selected.primary_intent)],
                    ['Sentiment', `${selected.sentiment_score >= 0 ? '+' : ''}${selected.sentiment_score.toFixed(2)}`],
                    ['Tokens', selected.total_tokens.toLocaleString('en-IN')],
                    ['Voice', `${Math.round(selected.voice_seconds)}s`],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-ink-400">{label}</dt>
                      <dd className="font-medium text-ink-800">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              <div className="flex-1 space-y-4 overflow-y-auto scroll-thin px-5 py-4">
                {selected.messages.map((message) => {
                  const isCustomer = message.role === 'user'
                  const isHuman = message.role === 'human_agent'
                  return (
                    <div
                      key={message.id}
                      className={cn('flex gap-3', isCustomer ? 'flex-row' : 'flex-row-reverse')}
                    >
                      <div
                        className={cn(
                          'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white',
                          isCustomer ? 'bg-ink-400' : isHuman ? 'bg-emerald-600' : 'bg-brand-600',
                        )}
                      >
                        {isCustomer ? (
                          <UserIcon className="h-3.5 w-3.5" />
                        ) : (
                          <Bot className="h-3.5 w-3.5" />
                        )}
                      </div>
                      <div className={cn('max-w-[80%]', !isCustomer && 'text-right')}>
                        <div
                          className={cn(
                            'rounded-xl px-3.5 py-2 text-left text-sm',
                            isCustomer
                              ? 'bg-ink-100 text-ink-800'
                              : isHuman
                                ? 'bg-emerald-50 text-emerald-900 ring-1 ring-emerald-200'
                                : 'bg-brand-50 text-ink-800 ring-1 ring-brand-100',
                          )}
                        >
                          {isCustomer ? (
                            <p className="whitespace-pre-wrap">{message.content}</p>
                          ) : (
                            <div
                              className="prose-chat"
                              dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
                            />
                          )}
                        </div>
                        <p className="mt-1 px-1 text-[11px] text-ink-400">
                          {isHuman ? 'Human agent' : isCustomer ? 'Customer' : 'Aura'} ·{' '}
                          {formatDate(message.created_at, true)}
                          {message.tool_calls?.length > 0 &&
                            ` · ${message.tool_calls.length} tool call(s)`}
                          {message.latency_ms != null &&
                            ` · ${(message.latency_ms / 1000).toFixed(1)}s`}
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="border-t border-ink-200 bg-ink-50 px-5 py-3">
                <div className="flex gap-2">
                  <Input
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendReply()}
                    placeholder="Reply to the customer as a human agent…"
                  />
                  <Button onClick={sendReply} loading={sending} disabled={!reply.trim()}>
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
                <p className="mt-1.5 text-[11px] text-ink-400">
                  Your reply is stored as <code className="font-mono">human_agent</code> and shown
                  to the customer as a person, not the AI.
                </p>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
