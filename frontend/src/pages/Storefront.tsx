import { MessageSquare, Search, ShoppingBag, Star, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { ChatPanel } from '@/components/chat/ChatPanel'
import { PageHeader } from '@/components/layout/AppShell'
import { Badge, Button, Card, EmptyState, Input, Select, Skeleton } from '@/components/ui'
import { api } from '@/lib/api'
import type { Category, Product } from '@/lib/types'
import { cn, formatMoney } from '@/lib/utils'

function ProductCard({ product }: { product: Product }) {
  const inStock = product.is_active && product.stock_quantity > 0
  const discount =
    product.mrp > product.price ? Math.round((1 - product.price / product.mrp) * 100) : 0

  return (
    <Card className="group flex flex-col overflow-hidden transition hover:shadow-md">
      <div className="relative aspect-square overflow-hidden bg-ink-100">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-ink-300">
            <ShoppingBag className="h-10 w-10" />
          </div>
        )}
        {discount > 0 && (
          <span className="absolute left-2 top-2 rounded-md bg-emerald-600 px-1.5 py-0.5 text-[11px] font-bold text-white">
            {discount}% off
          </span>
        )}
        {!inStock && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70">
            <span className="rounded-md bg-ink-900 px-2.5 py-1 text-xs font-semibold text-white">
              Out of stock
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col p-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-ink-400">
          {product.brand}
        </p>
        <h3 className="mt-0.5 line-clamp-2 text-sm font-semibold text-ink-900">
          {product.name}
        </h3>

        <div className="mt-1.5 flex items-center gap-1 text-xs text-ink-500">
          <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
          <span className="font-medium text-ink-700">{product.rating.toFixed(1)}</span>
          <span>({product.review_count.toLocaleString('en-IN')})</span>
        </div>

        <div className="mt-auto pt-3">
          <div className="flex items-baseline gap-2">
            <span className="text-base font-bold text-ink-900">
              {formatMoney(product.price, product.currency)}
            </span>
            {discount > 0 && (
              <span className="text-xs text-ink-400 line-through">
                {formatMoney(product.mrp, product.currency)}
              </span>
            )}
          </div>
          <p className="mt-1 text-[11px] text-ink-500">
            {inStock ? `${product.stock_quantity} in stock` : 'Notify me when available'}
            {product.is_returnable
              ? ` · ${product.return_window_days}-day returns`
              : ' · non-returnable'}
          </p>
        </div>
      </div>
    </Card>
  )
}

export function Storefront() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState('rating')
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    api.categories().then(setCategories).catch(() => setCategories([]))
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .products({ q: debounced, category, sort, page_size: 24 })
      .then((page) => {
        if (cancelled) return
        setProducts(page.items)
        setTotal(page.total)
      })
      .catch(() => !cancelled && setProducts([]))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [debounced, category, sort])

  const heading = useMemo(() => {
    if (debounced) return `Results for “${debounced}”`
    const match = categories.find((c) => c.slug === category)
    return match ? match.name : 'All products'
  }, [debounced, category, categories])

  return (
    <>
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <PageHeader
          title="NovaMart"
          description="Electronics, fashion, home and more — with an AI assistant that can see your orders."
        />

        {/* Filters */}
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search headphones, shoes, air purifier…"
              className="pl-9"
            />
          </div>

          <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-auto">
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>
                {c.name}
              </option>
            ))}
          </Select>

          <Select value={sort} onChange={(e) => setSort(e.target.value)} className="w-auto">
            <option value="rating">Top rated</option>
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
            <option value="newest">Newest</option>
          </Select>
        </div>

        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-ink-800">{heading}</h2>
          <span className="text-xs text-ink-500">{total} products</span>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Card key={i} className="overflow-hidden">
                <Skeleton className="aspect-square rounded-none" />
                <div className="space-y-2 p-3">
                  <Skeleton className="h-3 w-1/3" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              </Card>
            ))}
          </div>
        ) : products.length === 0 ? (
          <Card>
            <EmptyState
              icon={<ShoppingBag className="h-10 w-10" />}
              title="No products matched"
              description="Try a different search term, or ask Aura to find something for you."
              action={
                <Button onClick={() => setChatOpen(true)}>
                  <MessageSquare className="h-4 w-4" />
                  Ask the assistant
                </Button>
              }
            />
          </Card>
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        )}
      </div>

      {/* Floating support widget - the storefront entry point to the agent */}
      <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-3">
        {chatOpen && (
          <div className="h-[560px] w-[380px] max-w-[calc(100vw-2.5rem)] animate-fade-up overflow-hidden rounded-xl border border-ink-200 bg-white shadow-2xl">
            <ChatPanel variant="widget" />
          </div>
        )}

        <button
          onClick={() => setChatOpen((v) => !v)}
          className={cn(
            'flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg transition',
            chatOpen ? 'bg-ink-800 hover:bg-ink-900' : 'bg-brand-600 hover:bg-brand-700',
          )}
          aria-label={chatOpen ? 'Close support chat' : 'Open support chat'}
        >
          {chatOpen ? <X className="h-6 w-6" /> : <MessageSquare className="h-6 w-6" />}
        </button>

        {!chatOpen && (
          <Badge className="absolute -left-2 -top-1 bg-emerald-100 text-emerald-700 ring-emerald-600/20">
            Aura
          </Badge>
        )}
      </div>
    </>
  )
}
