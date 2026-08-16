import { AlertTriangle, Bot, Clock, RefreshCw, Ticket as TicketIcon } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { PageHeader } from '@/components/layout/AppShell'
import {
  Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, Modal, Select,
  Skeleton, Stat, Textarea,
} from '@/components/ui'
import { api } from '@/lib/api'
import type { Ticket, TicketStats } from '@/lib/types'
import { PRIORITY_STYLES, STATUS_STYLES, cn, formatDate, timeAgo, titleCase } from '@/lib/utils'

export function Tickets() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [stats, setStats] = useState<TicketStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Ticket | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      api.tickets({
        page_size: 60,
        status: status || undefined,
        priority: priority || undefined,
        q: search || undefined,
      }),
      api.ticketStats().catch(() => null),
    ])
      .then(([page, statistics]) => {
        setTickets(page.items)
        setStats(statistics)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load tickets.'))
      .finally(() => setLoading(false))
  }, [status, priority, search])

  useEffect(load, [load])

  async function update(ticket: Ticket, payload: Record<string, unknown>) {
    setBusy(true)
    try {
      const updated = await api.updateTicket(ticket.ticket_number, payload)
      setSelected(updated)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed.')
    } finally {
      setBusy(false)
    }
  }

  function slaState(ticket: Ticket): 'ok' | 'due' | 'breached' {
    if (!ticket.sla_due_at || ['resolved', 'closed'].includes(ticket.status)) return 'ok'
    const remaining = new Date(ticket.sla_due_at).getTime() - Date.now()
    if (remaining < 0) return 'breached'
    if (remaining < 2 * 60 * 60 * 1000) return 'due'
    return 'ok'
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <PageHeader
        title="Tickets"
        description="Everything the AI escalated or logged, prioritised by urgency and SLA."
        action={
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      {error && <ErrorBanner message={error} onRetry={load} />}

      {stats && (
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Stat label="Open" value={stats.open} icon={<TicketIcon className="h-4 w-4" />} />
          <Stat label="In progress" value={stats.in_progress} />
          <Stat
            label="Urgent"
            value={stats.urgent}
            tone={stats.urgent > 0 ? 'bad' : 'default'}
            icon={<AlertTriangle className="h-4 w-4" />}
          />
          <Stat
            label="SLA breaching"
            value={stats.sla_breaching}
            tone={stats.sla_breaching > 0 ? 'bad' : 'good'}
            icon={<Clock className="h-4 w-4" />}
          />
          <Stat
            label="AI created"
            value={stats.ai_created}
            hint="Opened by the agent"
            icon={<Bot className="h-4 w-4" />}
          />
          <Stat label="Resolved" value={stats.resolved} tone="good" />
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search subject or ticket number…"
          className="max-w-xs"
        />
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-auto">
          <option value="">Any status</option>
          {['open', 'in_progress', 'waiting_customer', 'resolved', 'closed'].map((value) => (
            <option key={value} value={value}>
              {titleCase(value)}
            </option>
          ))}
        </Select>
        <Select value={priority} onChange={(e) => setPriority(e.target.value)} className="w-auto">
          <option value="">Any priority</option>
          {['urgent', 'high', 'medium', 'low'].map((value) => (
            <option key={value} value={value}>
              {titleCase(value)}
            </option>
          ))}
        </Select>
      </div>

      <Card className="overflow-hidden">
        {loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : tickets.length === 0 ? (
          <EmptyState
            icon={<TicketIcon className="h-10 w-10" />}
            title="No tickets match"
            description="Adjust the filters, or enjoy the quiet queue."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="border-b border-ink-200 bg-ink-50 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Ticket</th>
                  <th className="px-4 py-2.5 font-semibold">Subject</th>
                  <th className="px-4 py-2.5 font-semibold">Priority</th>
                  <th className="px-4 py-2.5 font-semibold">Status</th>
                  <th className="px-4 py-2.5 font-semibold">SLA</th>
                  <th className="px-4 py-2.5 font-semibold">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {tickets.map((ticket) => {
                  const sla = slaState(ticket)
                  return (
                    <tr
                      key={ticket.id}
                      onClick={() => {
                        setSelected(ticket)
                        setNote(ticket.resolution_note ?? '')
                      }}
                      className="cursor-pointer transition hover:bg-ink-50"
                    >
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="font-mono text-xs font-semibold text-ink-800">
                          {ticket.ticket_number}
                        </span>
                        {ticket.created_by_agent && (
                          <Bot className="ml-1.5 inline h-3 w-3 text-brand-500" />
                        )}
                      </td>
                      <td className="max-w-[280px] px-4 py-3">
                        <p className="truncate text-ink-800">{ticket.subject}</p>
                        <p className="truncate text-[11px] text-ink-400">
                          {titleCase(ticket.category)}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={PRIORITY_STYLES[ticket.priority]} dot>
                          {titleCase(ticket.priority)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={STATUS_STYLES[ticket.status]}>
                          {titleCase(ticket.status)}
                        </Badge>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span
                          className={cn(
                            'text-xs font-medium',
                            sla === 'breached'
                              ? 'text-red-600'
                              : sla === 'due'
                                ? 'text-amber-600'
                                : 'text-ink-500',
                          )}
                        >
                          {sla === 'breached' ? 'Breached' : timeAgo(ticket.sla_due_at)}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-ink-500">
                        {formatDate(ticket.created_at)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected?.ticket_number ?? 'Ticket'}
        wide
        footer={
          selected && (
            <>
              <Button
                variant="outline"
                loading={busy}
                onClick={() => api.claimTicket(selected.ticket_number).then(load)}
              >
                Assign to me
              </Button>
              <Button
                variant="outline"
                loading={busy}
                onClick={() => update(selected, { status: 'in_progress' })}
              >
                Mark in progress
              </Button>
              <Button
                loading={busy}
                onClick={() => update(selected, { status: 'resolved', resolution_note: note })}
              >
                Resolve
              </Button>
            </>
          )
        }
      >
        {selected && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge className={PRIORITY_STYLES[selected.priority]} dot>
                {titleCase(selected.priority)}
              </Badge>
              <Badge className={STATUS_STYLES[selected.status]}>
                {titleCase(selected.status)}
              </Badge>
              <Badge>{titleCase(selected.category)}</Badge>
              {selected.created_by_agent && (
                <Badge className="bg-brand-50 text-brand-700 ring-brand-600/20">
                  <Bot className="h-3 w-3" />
                  Opened by Aura
                </Badge>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold text-ink-900">{selected.subject}</h3>
              <p className="mt-1 text-xs text-ink-500">
                Created {formatDate(selected.created_at, true)}
                {selected.sla_due_at && ` · SLA due ${formatDate(selected.sla_due_at, true)}`}
              </p>
            </div>

            <div className="max-h-72 overflow-y-auto scroll-thin rounded-lg border border-ink-200 bg-ink-50 p-3">
              <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-ink-700">
                {selected.description}
              </pre>
            </div>

            <Field label="Resolution note" hint="Shown on the customer's ticket history.">
              <Textarea
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What was done to resolve this?"
              />
            </Field>
          </div>
        )}
      </Modal>
    </div>
  )
}
