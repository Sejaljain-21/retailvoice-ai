import {
  Bot, Clock, DollarSign, Gauge, Mic, Smile, TicketCheck, TrendingUp,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import { PageHeader } from '@/components/layout/AppShell'
import { Card, CardHeader, ErrorBanner, Select, Skeleton, Stat } from '@/components/ui'
import { api } from '@/lib/api'
import type { Dashboard } from '@/lib/types'
import { CHART_COLORS, formatDate, titleCase } from '@/lib/utils'

const AXIS = { stroke: '#94a3b8', fontSize: 11 }
const TOOLTIP_STYLE = {
  contentStyle: {
    borderRadius: 8,
    border: '1px solid #e2e8f0',
    fontSize: 12,
    boxShadow: '0 4px 12px rgb(15 23 42 / 0.08)',
  },
}

export function Analytics() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .dashboard(days)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load analytics.'))
      .finally(() => setLoading(false))
  }, [days])

  useEffect(load, [load])

  if (loading && !data) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 px-4 py-6 lg:px-8">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <ErrorBanner message={error} onRetry={load} />
      </div>
    )
  }

  if (!data) return null

  const { kpis, intents, channels, timeseries, tools, sentiment, top_articles } = data

  const sentimentData = sentiment
    .filter((s) => s.count > 0)
    .map((s) => ({ name: titleCase(s.sentiment), value: s.count }))

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <PageHeader
        title="Support analytics"
        description={`Generated ${formatDate(data.generated_at, true)} · the numbers this project is measured on.`}
        action={
          <Select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="w-auto"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </Select>
        }
      />

      {/* KPI row */}
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Containment rate"
          value={`${kpis.containment_rate}%`}
          hint="Closed without a human"
          tone={kpis.containment_rate >= 70 ? 'good' : kpis.containment_rate >= 50 ? 'warn' : 'bad'}
          icon={<Gauge className="h-4 w-4" />}
        />
        <Stat
          label="Deflection rate"
          value={`${kpis.deflection_rate}%`}
          hint="No ticket created"
          tone={kpis.deflection_rate >= 60 ? 'good' : 'warn'}
          icon={<TicketCheck className="h-4 w-4" />}
        />
        <Stat
          label="Average CSAT"
          value={kpis.avg_csat ? `${kpis.avg_csat.toFixed(2)} / 5` : '—'}
          hint={`${kpis.csat_responses} responses`}
          tone={kpis.avg_csat >= 4 ? 'good' : kpis.avg_csat >= 3 ? 'warn' : 'bad'}
          icon={<Smile className="h-4 w-4" />}
        />
        <Stat
          label="Avg first response"
          value={`${(kpis.avg_first_response_ms / 1000).toFixed(1)}s`}
          hint="Agent reply latency"
          tone={kpis.avg_first_response_ms < 3000 ? 'good' : 'warn'}
          icon={<Clock className="h-4 w-4" />}
        />
        <Stat
          label="Conversations"
          value={kpis.total_conversations.toLocaleString('en-IN')}
          hint={`${kpis.conversations_today} today · ${kpis.active_conversations} active`}
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <Stat
          label="Escalated"
          value={kpis.escalated}
          hint={`${kpis.open_tickets} tickets open`}
          tone={kpis.escalated > kpis.ai_resolved ? 'bad' : 'default'}
          icon={<Bot className="h-4 w-4" />}
        />
        <Stat
          label="Voice minutes"
          value={kpis.total_voice_minutes.toFixed(1)}
          hint="Spoken conversations"
          icon={<Mic className="h-4 w-4" />}
        />
        <Stat
          label="Estimated operational cost"
          value={`$${kpis.estimated_cost_usd.toFixed(2)}`}
          hint={`${(kpis.total_tokens / 1000).toFixed(1)}k usage units`}
          icon={<DollarSign className="h-4 w-4" />}
        />
      </div>

      {/* Volume over time */}
      <Card className="mb-4">
        <CardHeader
          title="Conversation volume"
          subtitle="AI-resolved versus escalated, per day"
        />
        <div className="h-72 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timeseries} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="resolved" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="escalated" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                dataKey="date"
                tick={AXIS}
                tickFormatter={(value: string) => value.slice(5)}
                axisLine={false}
                tickLine={false}
              />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area
                type="monotone" dataKey="ai_resolved" name="AI resolved"
                stroke="#10b981" fill="url(#resolved)" strokeWidth={2}
              />
              <Area
                type="monotone" dataKey="escalations" name="Escalated"
                stroke="#ef4444" fill="url(#escalated)" strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        {/* Intents */}
        <Card>
          <CardHeader
            title="Why customers get in touch"
            subtitle="Top intents, with the share escalated to a human"
          />
          <div className="h-80 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={intents.slice(0, 8).map((i) => ({ ...i, label: titleCase(i.intent) }))}
                layout="vertical"
                margin={{ top: 4, right: 16, left: 8, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis
                  type="category" dataKey="label" tick={{ ...AXIS, fontSize: 10 }}
                  width={130} axisLine={false} tickLine={false}
                />
                <Tooltip
                  {...TOOLTIP_STYLE}
                  formatter={(value: number, name: string) => [
                    name === 'Escalation rate' ? `${value}%` : value, name,
                  ]}
                />
                <Bar dataKey="count" name="Conversations" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Sentiment */}
        <Card>
          <CardHeader
            title="Sentiment mix"
            subtitle="Last recorded sentiment per conversation"
          />
          <div className="h-80 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={sentimentData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={62}
                  outerRadius={104}
                  paddingAngle={2}
                >
                  {sentimentData.map((entry, index) => (
                    <Cell
                      key={entry.name}
                      fill={
                        ['#ef4444', '#f97316', '#94a3b8', '#22c55e', '#10b981'][index] ??
                        CHART_COLORS[index % CHART_COLORS.length]
                      }
                    />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Tools */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Tool usage"
            subtitle="What the agent actually does — the audit trail behind every answer"
          />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead className="border-b border-ink-200 bg-ink-50 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2 font-semibold">Tool</th>
                  <th className="px-4 py-2 text-right font-semibold">Calls</th>
                  <th className="px-4 py-2 text-right font-semibold">Success</th>
                  <th className="px-4 py-2 text-right font-semibold">Avg latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {tools.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-xs text-ink-400">
                      No tool calls recorded yet.
                    </td>
                  </tr>
                ) : (
                  tools.map((tool) => (
                    <tr key={tool.tool}>
                      <td className="px-4 py-2.5 font-mono text-xs text-ink-800">{tool.tool}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{tool.calls}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        <span
                          className={
                            tool.success_rate >= 98
                              ? 'text-emerald-600'
                              : tool.success_rate >= 90
                                ? 'text-amber-600'
                                : 'text-red-600'
                          }
                        >
                          {tool.success_rate}%
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-ink-600">
                        {tool.avg_duration_ms.toFixed(0)} ms
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          {/* Channels */}
          <Card>
            <CardHeader title="Channels" subtitle="Volume and containment" />
            <ul className="divide-y divide-ink-100">
              {channels.map((item) => (
                <li key={item.channel} className="px-4 py-2.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-ink-800">{titleCase(item.channel)}</span>
                    <span className="tabular-nums text-ink-600">{item.count}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-100">
                    <div
                      className="h-full rounded-full bg-brand-500"
                      style={{ width: `${item.percentage}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-ink-500">
                    {item.percentage}% of volume · {item.containment_rate}% contained
                  </p>
                </li>
              ))}
            </ul>
          </Card>

          {/* Top articles */}
          <Card>
            <CardHeader title="Most-read articles" subtitle="Help-centre demand" />
            <ul className="divide-y divide-ink-100">
              {top_articles.map((article) => (
                <li key={article.slug} className="px-4 py-2.5">
                  <p className="truncate text-xs font-medium text-ink-800">{article.title}</p>
                  <p className="text-[11px] text-ink-500">
                    {article.views.toLocaleString('en-IN')} views · {article.helpful} helpful
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
