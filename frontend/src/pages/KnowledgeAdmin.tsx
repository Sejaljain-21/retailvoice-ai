import { BookOpen, Database, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { PageHeader } from '@/components/layout/AppShell'
import {
  Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, Modal, Select,
  Skeleton, Stat, Textarea,
} from '@/components/ui'
import { api } from '@/lib/api'
import type { KBDocument, KBSummary } from '@/lib/types'
import { formatDate, titleCase } from '@/lib/utils'

const CATEGORIES = [
  'returns', 'refunds', 'orders', 'shipping', 'payments',
  'warranty', 'offers', 'account', 'stores', 'general',
]

export function KnowledgeAdmin() {
  const [articles, setArticles] = useState<KBSummary[]>([])
  const [stats, setStats] = useState<{
    documents: number; chunks: number; embedding_model: string; dim: number
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editing, setEditing] = useState<KBDocument | 'new' | null>(null)
  const [form, setForm] = useState({ title: '', category: 'general', content: '', tags: '' })
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      api.kbList({ page_size: 100, published_only: false }),
      api.kbStats().catch(() => null),
    ])
      .then(([page, indexStats]) => {
        setArticles(page.items)
        setStats(indexStats)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load articles.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  function startNew() {
    setForm({ title: '', category: 'general', content: '', tags: '' })
    setEditing('new')
  }

  async function startEdit(id: string) {
    try {
      const doc = await api.kbDocument(id)
      setForm({
        title: doc.title,
        category: doc.category,
        content: doc.content,
        tags: doc.tags.join(', '),
      })
      setEditing(doc)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open that article.')
    }
  }

  async function save() {
    setBusy(true)
    setError(null)
    const payload = {
      title: form.title.trim(),
      category: form.category,
      content: form.content.trim(),
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
    }
    try {
      if (editing === 'new') {
        await api.kbCreate(payload)
        setNotice('Article created and embedded into the retrieval index.')
      } else if (editing) {
        await api.kbUpdate(editing.id, payload)
        setNotice('Article updated and re-embedded.')
      }
      setEditing(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed.')
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: string, title: string) {
    if (!confirm(`Delete “${title}”? The agent will no longer be able to cite it.`)) return
    try {
      await api.kbDelete(id)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.')
    }
  }

  async function reindex() {
    setBusy(true)
    try {
      const result = await api.kbReindex()
      setNotice(
        `Reindexed ${result.documents} articles into ${result.chunks} chunks in ${result.took_ms} ms.`,
      )
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reindex failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 lg:px-8">
      <PageHeader
        title="Knowledge base"
        description="The agent's only source of truth for policy answers. Edits are re-embedded immediately."
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" loading={busy} onClick={reindex}>
              <RefreshCw className="h-3.5 w-3.5" />
              Rebuild index
            </Button>
            <Button size="sm" onClick={startNew}>
              <Plus className="h-3.5 w-3.5" />
              New article
            </Button>
          </div>
        }
      />

      {error && <ErrorBanner message={error} />}
      {notice && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
          {notice}
        </div>
      )}

      {stats && (
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Articles" value={stats.documents} icon={<BookOpen className="h-4 w-4" />} />
          <Stat label="Indexed chunks" value={stats.chunks} icon={<Database className="h-4 w-4" />} />
          <Stat label="Embedding model" value={<span className="text-sm">{stats.embedding_model}</span>} />
          <Stat label="Vector size" value={stats.dim} hint="dimensions per chunk" />
        </div>
      )}

      <Card className="overflow-hidden">
        {loading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : articles.length === 0 ? (
          <EmptyState
            icon={<BookOpen className="h-10 w-10" />}
            title="No articles yet"
            description="Add the first policy article so the agent has something to cite."
            action={<Button onClick={startNew}>New article</Button>}
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {articles.map((article) => (
              <li
                key={article.id}
                className="flex items-center justify-between gap-3 px-4 py-3 transition hover:bg-ink-50"
              >
                <button
                  onClick={() => startEdit(article.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <p className="truncate text-sm font-medium text-ink-900">{article.title}</p>
                  <p className="mt-0.5 text-[11px] text-ink-500">
                    {titleCase(article.category)} · {article.view_count.toLocaleString('en-IN')}{' '}
                    views · updated {formatDate(article.updated_at)}
                  </p>
                </button>
                <div className="flex shrink-0 items-center gap-2">
                  {article.tags.slice(0, 2).map((tag) => (
                    <Badge key={tag}>{tag}</Badge>
                  ))}
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => remove(article.id, article.title)}
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4 text-ink-400" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'New help article' : 'Edit article'}
        wide
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button
              loading={busy}
              disabled={form.title.trim().length < 3 || form.content.trim().length < 20}
              onClick={save}
            >
              Save &amp; re-embed
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Title">
            <Input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Gift wrapping and personalised messages"
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Category">
              <Select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {CATEGORIES.map((value) => (
                  <option key={value} value={value}>
                    {titleCase(value)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Tags" hint="Comma separated.">
              <Input
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                placeholder="gift, wrapping, checkout"
              />
            </Field>
          </div>

          <Field
            label="Content"
            hint="Write it the way you'd want the agent to say it. Concrete numbers and named exceptions retrieve far better than vague prose."
          >
            <Textarea
              rows={14}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              className="font-mono text-xs"
              placeholder={
                'Gift wrapping costs Rs 49 per item and can be added at checkout.\n\n' +
                'You may include a personalised message of up to 200 characters.'
              }
            />
          </Field>
        </div>
      </Modal>
    </div>
  )
}
