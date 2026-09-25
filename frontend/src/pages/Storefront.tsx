import {
  CheckCircle2, Copy, MessageSquare, Mic, Package, Search,
  ShieldCheck, ShoppingBag, Sparkles, Star, Store, Truck, X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '@/components/layout/AppShell'
import {
  Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, Modal, Select, Skeleton, Textarea,
} from '@/components/ui'
import { api } from '@/lib/api'
import type { Category, Order, Product } from '@/lib/types'
import { cn, formatDate, formatMoney } from '@/lib/utils'
import { useAuth } from '@/store/auth'
import { useChat } from '@/store/chat'

function ProductCard({
  product,
  onSelect,
}: {
  product: Product
  onSelect: (p: Product) => void
}) {
  const inStock = product.is_active && product.stock_quantity > 0
  const discount =
    product.mrp > product.price ? Math.round((1 - product.price / product.mrp) * 100) : 0

  return (
    <Card
      onClick={() => onSelect(product)}
      className="group flex flex-col overflow-hidden transition duration-200 hover:shadow-lg hover:border-brand-300 cursor-pointer"
    >
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
          <span className="absolute left-2 top-2 rounded-md bg-emerald-600 px-1.5 py-0.5 text-[11px] font-bold text-white shadow-sm">
            {discount}% off
          </span>
        )}
        {!inStock && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 backdrop-blur-[2px]">
            <span className="rounded-md bg-ink-900 px-2.5 py-1 text-xs font-semibold text-white">
              Out of stock
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col p-3.5">
        <p className="text-[11px] font-medium uppercase tracking-wide text-ink-400">
          {product.brand}
        </p>
        <h3 className="mt-0.5 line-clamp-2 text-sm font-semibold text-ink-900 group-hover:text-brand-600 transition">
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

          <Button
            size="sm"
            className="mt-3 w-full"
            variant={inStock ? 'primary' : 'outline'}
            disabled={!inStock}
            onClick={(e) => {
              e.stopPropagation()
              onSelect(product)
            }}
          >
            {inStock ? 'Book / Buy Now' : 'Out of stock'}
          </Button>
        </div>
      </div>
    </Card>
  )
}

export function Storefront() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const chat = useChat()

  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState('rating')
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // Booking & product detail modal state
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [pincode, setPincode] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('upi')
  const [coupon, setCoupon] = useState('')
  const [bookingBusy, setBookingBusy] = useState(false)
  const [bookingError, setBookingError] = useState<string | null>(null)
  const [orderPlaced, setOrderPlaced] = useState<Order | null>(null)
  const [copied, setCopied] = useState(false)

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

  const openProduct = (prod: Product) => {
    setSelectedProduct(prod)
    setQuantity(1)
    setAddress(
      user?.profile?.default_address ||
        '402, Lakeview Apartments, 5th Cross, Koramangala',
    )
    setCity(user?.profile?.city || 'Bengaluru')
    setPincode(user?.profile?.pincode || '560095')
    setPaymentMethod('upi')
    setCoupon('')
    setBookingBusy(false)
    setBookingError(null)
    setOrderPlaced(null)
    setCopied(false)
  }

  async function handlePlaceOrder() {
    if (!selectedProduct || !user) return
    if (!address.trim()) {
      setBookingError('Please enter a delivery address.')
      return
    }
    setBookingBusy(true)
    setBookingError(null)
    try {
      const order = await api.createOrder({
        items: [{ product_id: selectedProduct.id, quantity }],
        shipping_address: address.trim(),
        shipping_city: city.trim() || undefined,
        shipping_pincode: pincode.trim() || undefined,
        payment_method: paymentMethod,
        coupon_code: coupon.trim() ? coupon.trim().toUpperCase() : undefined,
      })
      setOrderPlaced(order)
      // update local stock
      setProducts((prev) =>
        prev.map((p) =>
          p.id === selectedProduct.id
            ? { ...p, stock_quantity: Math.max(0, p.stock_quantity - quantity) }
            : p,
        ),
      )
    } catch (err) {
      setBookingError(err instanceof Error ? err.message : 'Could not place order.')
    } finally {
      setBookingBusy(false)
    }
  }

  return (
    <>
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        {/* Retail Sandbox Context Banner */}
        <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4 rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-violet-50 p-5 shadow-xs">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-700">
              <Store className="h-3.5 w-3.5" />
              <span>Interactive Retail Sandbox</span>
            </div>
            <h1 className="text-xl font-bold text-ink-900">Retail Product Catalog & Sandbox</h1>
            <p className="text-xs text-ink-600 max-w-2xl">
              Simulate customer purchases or browse catalog inventory. Any order created here is stored in the live database and can be tracked, inquired upon, or returned autonomously by <strong>Aura</strong>.
            </p>
          </div>

          <Button
            onClick={() => navigate('/')}
            className="shrink-0 gap-2 bg-gradient-to-r from-brand-600 to-violet-600 hover:from-brand-700 hover:to-violet-700 text-xs font-semibold"
          >
            <Mic className="h-4 w-4" />
            <span>Open Voice & Support Studio</span>
          </Button>
        </div>

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
                <Button onClick={() => navigate('/support')}>
                  <MessageSquare className="h-4 w-4" />
                  Ask the assistant
                </Button>
              }
            />
          </Card>
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onSelect={openProduct}
              />
            ))}
          </div>
        )}
      </div>

      {/* Product Detail & Booking Modal */}
      <Modal
        open={!!selectedProduct}
        onClose={() => {
          setSelectedProduct(null)
          setOrderPlaced(null)
          setBookingError(null)
        }}
        title={orderPlaced ? 'Booking Confirmation' : selectedProduct?.name ?? 'Product Details'}
        wide
      >
        {orderPlaced ? (
          <div className="p-6 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <h3 className="mt-3 text-lg font-bold text-ink-900">Order Placed Successfully!</h3>
            <p className="mt-1 text-sm text-ink-500">
              Your order has been confirmed in the live system and is ready to test.
            </p>

            <div className="mx-auto mt-5 max-w-md rounded-xl border border-ink-200 bg-ink-50 p-4 text-left">
              <div className="flex items-center justify-between border-b border-ink-200 pb-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-ink-500">
                  Order Number
                </span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-bold text-brand-600">
                    {orderPlaced.order_number}
                  </span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(orderPlaced.order_number)
                      setCopied(true)
                      setTimeout(() => setCopied(false), 2000)
                    }}
                    className="rounded p-1 text-ink-500 hover:bg-ink-200 transition"
                    title="Copy order number"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  {copied && <span className="text-[11px] text-emerald-600 font-medium">Copied!</span>}
                </div>
              </div>

              <div className="mt-3 space-y-2 text-xs text-ink-600">
                <div className="flex justify-between">
                  <span>Product:</span>
                  <span className="font-medium text-ink-900 truncate max-w-[220px]">
                    {selectedProduct?.name} (x{quantity})
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Total Amount:</span>
                  <span className="font-bold text-ink-900">
                    {formatMoney(orderPlaced.total_amount, orderPlaced.currency)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Payment Method:</span>
                  <span className="font-medium uppercase text-ink-800">
                    {orderPlaced.payment_method}
                  </span>
                </div>
                {orderPlaced.expected_delivery && (
                  <div className="flex justify-between">
                    <span>Expected Delivery:</span>
                    <span className="font-medium text-ink-800">
                      {formatDate(orderPlaced.expected_delivery)}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Shipping Address:</span>
                  <span className="max-w-[220px] truncate text-right font-medium text-ink-800">
                    {orderPlaced.shipping_address}, {orderPlaced.shipping_city} {orderPlaced.shipping_pincode}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Button
                variant="primary"
                onClick={() => {
                  setSelectedProduct(null)
                  setOrderPlaced(null)
                  navigate('/orders')
                }}
              >
                <Package className="h-4 w-4" />
                View in My Orders
              </Button>

              <Button
                variant="outline"
                onClick={() => {
                  const num = orderPlaced.order_number
                  setSelectedProduct(null)
                  setOrderPlaced(null)
                  chat.reset()
                  chat.send(`Where is my order ${num}?`)
                  navigate('/')
                }}
              >
                <MessageSquare className="h-4 w-4" />
                Ask Aura to track it
              </Button>

              <Button
                variant="ghost"
                onClick={() => {
                  setSelectedProduct(null)
                  setOrderPlaced(null)
                }}
              >
                Continue Shopping
              </Button>
            </div>
          </div>
        ) : selectedProduct ? (
          <div className="grid grid-cols-1 gap-6 p-6 md:grid-cols-2">
            {/* Left: Product Media & Specs */}
            <div className="flex flex-col">
              <div className="relative aspect-square w-full overflow-hidden rounded-xl border border-ink-200 bg-ink-100">
                {selectedProduct.image_url ? (
                  <img
                    src={selectedProduct.image_url}
                    alt={selectedProduct.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-ink-300">
                    <ShoppingBag className="h-16 w-16" />
                  </div>
                )}
                {selectedProduct.mrp > selectedProduct.price && (
                  <span className="absolute left-3 top-3 rounded-md bg-emerald-600 px-2 py-1 text-xs font-bold text-white shadow-sm">
                    {Math.round((1 - selectedProduct.price / selectedProduct.mrp) * 100)}% off
                  </span>
                )}
              </div>

              <div className="mt-4 space-y-2">
                <p className="text-xs leading-relaxed text-ink-600">
                  {selectedProduct.description}
                </p>

                <div className="mt-3 flex flex-wrap gap-2 pt-2">
                  <Badge className="bg-ink-100 text-ink-700">
                    <Truck className="mr-1 h-3.5 w-3.5" />
                    {selectedProduct.stock_quantity > 0 ? 'Ready to ship' : 'Out of stock'}
                  </Badge>
                  <Badge className="bg-ink-100 text-ink-700">
                    <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                    {selectedProduct.is_returnable
                      ? `${selectedProduct.return_window_days}-day return policy`
                      : 'Non-returnable'}
                  </Badge>
                </div>

                {selectedProduct.attributes && Object.keys(selectedProduct.attributes).length > 0 && (
                  <div className="mt-4 rounded-lg border border-ink-200 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-500">
                      Specifications
                    </p>
                    <dl className="mt-2 grid grid-cols-2 gap-2 text-xs">
                      {Object.entries(selectedProduct.attributes).map(([key, val]) => (
                        <div key={key}>
                          <dt className="text-ink-400 capitalize">{key.replace('_', ' ')}</dt>
                          <dd className="font-medium text-ink-800">{String(val)}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Pricing & Booking Form */}
            <div className="flex flex-col">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-ink-400">
                  {selectedProduct.brand}
                </p>
                <h2 className="mt-1 text-lg font-bold text-ink-900">
                  {selectedProduct.name}
                </h2>

                <div className="mt-2 flex items-center gap-2 text-xs text-ink-500">
                  <div className="flex items-center gap-1">
                    <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                    <span className="font-semibold text-ink-800">{selectedProduct.rating.toFixed(1)}</span>
                  </div>
                  <span>·</span>
                  <span>{selectedProduct.review_count.toLocaleString('en-IN')} ratings</span>
                </div>

                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-ink-950">
                    {formatMoney(selectedProduct.price, selectedProduct.currency)}
                  </span>
                  {selectedProduct.mrp > selectedProduct.price && (
                    <span className="text-sm text-ink-400 line-through">
                      {formatMoney(selectedProduct.mrp, selectedProduct.currency)}
                    </span>
                  )}
                  <span className="text-xs font-medium text-emerald-600">
                    Inclusive of all taxes
                  </span>
                </div>

                <p className="mt-1 text-xs text-ink-500">
                  {selectedProduct.stock_quantity > 0 ? (
                    <span className="text-emerald-700 font-medium">
                      In Stock ({selectedProduct.stock_quantity} available)
                    </span>
                  ) : (
                    <span className="text-red-600 font-medium">Out of stock</span>
                  )}
                </p>

                {/* Ask Aura about this product button */}
                <div className="mt-3">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const name = selectedProduct.name
                      setSelectedProduct(null)
                      chat.reset()
                      chat.send(`Tell me about the stock, warranty and return policy for ${name}.`)
                      navigate('/')
                    }}
                    className="w-full gap-2 text-xs font-semibold text-brand-700 border-brand-200 hover:bg-brand-50"
                  >
                    <Mic className="h-3.5 w-3.5 text-brand-600" />
                    Ask Aura about this product
                  </Button>
                </div>
              </div>

              <div className="my-4 border-t border-ink-200" />

              {/* Order Form */}
              {!user ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-center">
                  <p className="text-sm font-semibold text-amber-900">
                    Sign in to book this product
                  </p>
                  <p className="mt-1 text-xs text-amber-700">
                    Sign in with the demo customer account to test live order booking, tracking, and cancellation.
                  </p>
                  <Button
                    className="mt-3 w-full"
                    onClick={() => {
                      setSelectedProduct(null)
                      navigate('/login')
                    }}
                  >
                    Sign In to Book
                  </Button>
                </div>
              ) : selectedProduct.stock_quantity <= 0 ? (
                <div className="rounded-xl border border-ink-200 bg-ink-50 p-4 text-center">
                  <p className="text-sm font-semibold text-ink-700">
                    This item is currently out of stock
                  </p>
                  <p className="mt-1 text-xs text-ink-500">
                    Please select another item to test booking.
                  </p>
                </div>
              ) : (
                <div className="space-y-3.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-ink-700">Quantity</label>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-ink-300 bg-white text-sm font-bold text-ink-700 hover:bg-ink-100 disabled:opacity-50"
                        disabled={quantity <= 1}
                      >
                        -
                      </button>
                      <span className="w-8 text-center text-sm font-bold text-ink-900">
                        {quantity}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setQuantity((q) => Math.min(Math.min(10, selectedProduct.stock_quantity), q + 1))
                        }
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-ink-300 bg-white text-sm font-bold text-ink-700 hover:bg-ink-100 disabled:opacity-50"
                        disabled={quantity >= Math.min(10, selectedProduct.stock_quantity)}
                      >
                        +
                      </button>
                    </div>
                  </div>

                  <Field label="Delivery Address">
                    <Textarea
                      rows={2}
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      placeholder="House number, street, landmark"
                    />
                  </Field>

                  <div className="grid grid-cols-2 gap-2">
                    <Field label="City">
                      <Input
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        placeholder="City"
                      />
                    </Field>
                    <Field label="Pincode">
                      <Input
                        value={pincode}
                        onChange={(e) => setPincode(e.target.value)}
                        placeholder="560095"
                      />
                    </Field>
                  </div>

                  <Field label="Payment Method">
                    <Select
                      value={paymentMethod}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                    >
                      <option value="upi">UPI (Instant confirmation)</option>
                      <option value="card">Credit / Debit Card</option>
                      <option value="netbanking">Net Banking</option>
                      <option value="cod">Cash on Delivery</option>
                    </Select>
                  </Field>

                  <Field label="Coupon Code (Optional)" hint="Try: WELCOME10 or FREESHIP">
                    <Input
                      value={coupon}
                      onChange={(e) => setCoupon(e.target.value)}
                      placeholder="e.g. WELCOME10"
                    />
                  </Field>

                  {/* Pricing summary */}
                  <div className="rounded-lg border border-ink-200 bg-ink-50 p-3 text-xs">
                    <div className="flex justify-between text-ink-600">
                      <span>Item Subtotal ({quantity} item{quantity > 1 ? 's' : ''}):</span>
                      <span>{formatMoney(selectedProduct.price * quantity, selectedProduct.currency)}</span>
                    </div>
                    <div className="mt-1 flex justify-between text-ink-600">
                      <span>Delivery Fee:</span>
                      <span>{selectedProduct.price * quantity >= 999 ? 'FREE' : '₹49.00'}</span>
                    </div>
                    <div className="mt-1 flex justify-between text-ink-600">
                      <span>GST (18% included):</span>
                      <span>{formatMoney(selectedProduct.price * quantity * 0.18, selectedProduct.currency)}</span>
                    </div>
                    <div className="mt-2 flex justify-between border-t border-ink-200 pt-2 font-bold text-ink-900">
                      <span>Total Amount:</span>
                      <span>
                        {formatMoney(
                          selectedProduct.price * quantity +
                            (selectedProduct.price * quantity >= 999 ? 0 : 49) +
                            selectedProduct.price * quantity * 0.18,
                          selectedProduct.currency,
                        )}
                      </span>
                    </div>
                  </div>

                  {bookingError && <ErrorBanner message={bookingError} />}

                  <Button
                    className="w-full"
                    loading={bookingBusy}
                    onClick={handlePlaceOrder}
                  >
                    Confirm & Book Now
                  </Button>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Modal>
    </>
  )
}
