import { BookOpen, ChevronLeft, Search, Sparkles, ThumbsUp } from 'lucide-react'
import { useEffect, useState } from 'react'

import { PageHeader } from '@/components/layout/AppShell'
import { Badge, Button, Card, EmptyState, Input, Skeleton } from '@/components/ui'
import { api } from '@/lib/api'
import type { KBDocument, KBSearchHit, KBSummary } from '@/lib/types'
import { cn, titleCase } from '@/lib/utils'

export function HelpCentre() {
  const [articles, setArticles] = useState<KBSummary[]>([])
  const [categories, setCategories] = useState<Array<{ category: string; count: number }>>([])
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<KBSearchHit[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [tookMs, setTookMs] = useState(0)
  const [open, setOpen] = useState<KBDocument | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.kbCategories().then(setCategories).catch(() => setCategories([]))
  }, [])

  useEffect(() => {
    setLoading(true)
    api
      .kbList({ category, page_size: 50 })
      .then((page) => setArticles(page.items))
      .catch(() => setArticles([]))
      .finally(() => setLoading(false))
  }, [category])

  async function runSearch(event: React.FormEvent) {
    event.preventDefault()
    if (!query.trim()) {
      setHits(null)
      return
    }
    setSearching(true)
    try {
      const result = await api.kbSearch(query.trim(), 6)
      setHits(result.hits)
      setTookMs(result.took_ms)
    } catch {
      setHits([])
    } finally {
      setSearching(false)
    }
  }

  async function openArticle(idOrSlug: string) {
    try {
      setOpen(await api.kbDocument(idOrSlug))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch {
      /* ignore */
    }
  }

  if (open) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-6 lg:px-8">
        <Button variant="ghost" size="sm" onClick={() => setOpen(null)} className="mb-4">
          <ChevronLeft className="h-4 w-4" />
          Back to help centre
        </Button>

        <Card className="p-6">
          <Badge className="bg-brand-50 text-brand-700 ring-brand-600/20">
            {titleCase(open.category)}
          </Badge>
          <h1 className="mt-3 text-2xl font-bold text-ink-900">{open.title}</h1>
          <p className="mt-1 text-xs text-ink-500">
            Version {open.version} · {open.view_count.toLocaleString('en-IN')} views ·{' '}
            {open.helpful_count} found this helpful
          </p>

          <div className="mt-5 space-y-3 text-sm leading-relaxed text-ink-700">
            {open.content.split(/\n\s*\n/).map((paragraph, index) => (
              <p key={index} className="whitespace-pre-line">
                {paragraph}
              </p>
            ))}
          </div>

          <div className="mt-6 flex items-center gap-3 border-t border-ink-200 pt-4">
            <span className="text-sm text-ink-600">Was this helpful?</span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void fetch(`/api/v1/knowledge/${open.id}/helpful`, { method: 'POST' })
                setOpen({ ...open, helpful_count: open.helpful_count + 1 })
              }}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
              Yes
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 lg:px-8">
      <PageHeader
        title="Help centre"
        description="The same articles the AI agent cites when it answers a policy question."
      />

      <form onSubmit={runSearch} className="mb-5 flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              if (!e.target.value) setHits(null)
            }}
            placeholder="Ask a question — “how long does a UPI refund take?”"
            className="pl-9"
          />
        </div>
        <Button type="submit" loading={searching}>
          Search
        </Button>
      </form>

      {hits !== null ? (
        <div>
          <p className="mb-3 text-xs text-ink-500">
            {hits.length} passage{hits.length === 1 ? '' : 's'} ranked by hybrid semantic +
            keyword search in {tookMs} ms
          </p>
          {hits.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Sparkles className="h-10 w-10" />}
                title="Nothing matched"
                description="Try different words, or ask Aura directly — she can create a ticket for you."
              />
            </Card>
          ) : (
            <div className="space-y-3">
              {hits.map((hit) => (
                <Card
                  key={hit.chunk_id}
                  className="cursor-pointer p-4 transition hover:border-brand-300 hover:shadow-sm"
                  onClick={() => openArticle(hit.slug)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-ink-900">{hit.title}</h3>
                    <Badge className="shrink-0 bg-emerald-100 text-emerald-700 ring-emerald-600/20">
                      {(hit.score * 100).toFixed(0)}% match
                    </Badge>
                  </div>
                  <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-ink-600">
                    {hit.snippet}
                  </p>
                </Card>
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-1.5">
            <button
              onClick={() => setCategory('')}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition',
                !category
                  ? 'bg-brand-600 text-white'
                  : 'bg-white text-ink-600 ring-1 ring-inset ring-ink-200 hover:bg-ink-50',
              )}
            >
              All
            </button>
            {categories.map(({ category: name, count }) => (
              <button
                key={name}
                onClick={() => setCategory(name)}
                className={cn(
                  'rounded-full px-3 py-1 text-xs font-medium transition',
                  category === name
                    ? 'bg-brand-600 text-white'
                    : 'bg-white text-ink-600 ring-1 ring-inset ring-ink-200 hover:bg-ink-50',
                )}
              >
                {titleCase(name)} ({count})
              </button>
            ))}
          </div>

          {loading ? (
            <div className="grid gap-3 md:grid-cols-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="p-4">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="mt-2 h-3 w-1/2" />
                </Card>
              ))}
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {articles.map((article) => (
                <Card
                  key={article.id}
                  className="cursor-pointer p-4 transition hover:border-brand-300 hover:shadow-sm"
                  onClick={() => openArticle(article.slug)}
                >
                  <div className="flex items-start gap-3">
                    <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-ink-900">{article.title}</h3>
                      <p className="mt-1 text-[11px] text-ink-500">
                        {titleCase(article.category)} ·{' '}
                        {article.view_count.toLocaleString('en-IN')} views
                      </p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
