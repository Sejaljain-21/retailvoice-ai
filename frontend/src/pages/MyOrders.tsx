import { MapPin, Package, RotateCcw, Truck, XCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '@/components/layout/AppShell'
import {
  Badge, Button, Card, EmptyState, ErrorBanner, Field, Modal, Skeleton, Textarea,
} from '@/components/ui'
import { api } from '@/lib/api'
import type { Order } from '@/lib/types'
import { STATUS_STYLES, cn, formatDate, formatMoney, titleCase } from '@/lib/utils'
import { useChat } from '@/store/chat'

function TrackingTimeline({ order }: { order: Order }) {
  const shipment = order.shipment
  if (!shipment) {
    return (
      <p className="text-xs text-ink-500">
        Not handed to the courier yet — tracking appears once it ships.
      </p>
    )
  }
  const events = [...(shipment.events ?? [])].reverse()

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <span className="text-ink-500">
          Carrier <span className="font-medium text-ink-800">{shipment.carrier}</span>
        </span>
        <span className="text-ink-500">
          AWB <span className="font-mono font-medium text-ink-800">{shipment.tracking_number}</span>
        </span>
        {shipment.estimated_delivery && (
          <span className="text-ink-500">
            ETA{' '}
            <span className="font-medium text-ink-800">
              {formatDate(shipment.estimated_delivery)}
            </span>
          </span>
        )}
      </div>

      <ol className="space-y-2.5">
        {events.map((event, index) => (
          <li key={`${event.at}-${index}`} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  'mt-1 h-2 w-2 shrink-0 rounded-full',
                  index === 0 ? 'bg-brand-600 ring-4 ring-brand-100' : 'bg-ink-300',
                )}
              />
              {index < events.length - 1 && <span className="h-full w-px flex-1 bg-ink-200" />}
            </div>
            <div className="pb-1">
              <p className={cn('text-xs font-medium', index === 0 ? 'text-ink-900' : 'text-ink-600')}>
                {event.status}
              </p>
              <p className="text-[11px] text-ink-400">
                {event.location} · {formatDate(event.at, true)}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

export function MyOrders() {
  const navigate = useNavigate()
  const { send, reset } = useChat()

  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [action, setAction] = useState<{ order: Order; kind: 'cancel' | 'return' } | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .orders({ page_size: 50 })
      .then((page) => setOrders(page.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load orders.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  async function confirmAction() {
    if (!action || !reason.trim()) return
    setBusy(true)
    setActionError(null)
    try {
      if (action.kind === 'cancel') {
        await api.cancelOrder(action.order.order_number, reason.trim())
      } else {
        await api.createReturn(action.order.order_number, { reason: reason.trim() })
      }
      setAction(null)
      setReason('')
      load()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'That did not work.')
    } finally {
      setBusy(false)
    }
  }

  function askAura(order: Order, prompt: string) {
    reset()
    navigate('/support')
    setTimeout(() => void send(`${prompt} (order ${order.order_number})`), 120)
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 lg:px-8">
      <PageHeader
        title="My orders"
        description="Track, cancel or return — or ask Aura to do it for you."
      />

      {error && <ErrorBanner message={error} onRetry={load} />}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="mt-3 h-3 w-full" />
              <Skeleton className="mt-2 h-3 w-2/3" />
            </Card>
          ))}
        </div>
      ) : orders.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Package className="h-10 w-10" />}
            title="No orders yet"
            description="Once you place an order it will appear here with live tracking."
            action={<Button onClick={() => navigate('/')}>Browse the storefront</Button>}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => {
            const isOpen = expanded === order.id
            const cancellable = ['pending', 'confirmed', 'packed'].includes(order.status)
            const returnable = order.status === 'delivered' && order.returns.length === 0

            return (
              <Card key={order.id} className="overflow-hidden">
                <button
                  onClick={() => setExpanded(isOpen ? null : order.id)}
                  className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3.5 text-left transition hover:bg-ink-50"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-semibold text-ink-900">
                        {order.order_number}
                      </span>
                      <Badge className={STATUS_STYLES[order.status]} dot>
                        {titleCase(order.status)}
                      </Badge>
                      {order.returns.length > 0 && (
                        <Badge className="bg-orange-100 text-orange-700 ring-orange-600/20">
                          Return {titleCase(order.returns[0].status)}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-1 truncate text-xs text-ink-500">
                      {order.items.map((i) => `${i.quantity}× ${i.product_name}`).join(', ')}
                    </p>
                  </div>

                  <div className="text-right">
                    <p className="text-sm font-bold text-ink-900">
                      {formatMoney(order.total_amount, order.currency)}
                    </p>
                    <p className="text-[11px] text-ink-500">
                      Placed {formatDate(order.placed_at)}
                    </p>
                  </div>
                </button>

                {isOpen && (
                  <div className="animate-fade-up space-y-4 border-t border-ink-200 bg-ink-50/60 px-4 py-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-500">
                          <Truck className="h-3.5 w-3.5" />
                          Tracking
                        </h4>
                        <TrackingTimeline order={order} />
                      </div>

                      <div>
                        <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-500">
                          <MapPin className="h-3.5 w-3.5" />
                          Delivery &amp; payment
                        </h4>
                        <p className="text-xs leading-relaxed text-ink-600">
                          {order.shipping_address}
                        </p>
                        <dl className="mt-3 space-y-1 text-xs">
                          {[
                            ['Subtotal', formatMoney(order.subtotal, order.currency)],
                            ['Shipping', order.shipping_fee
                              ? formatMoney(order.shipping_fee, order.currency) : 'Free'],
                            ...(order.discount
                              ? [['Discount', `− ${formatMoney(order.discount, order.currency)}`]]
                              : []),
                            ['Tax', formatMoney(order.tax, order.currency)],
                            ['Payment', `${titleCase(order.payment_method)} · ${titleCase(order.payment_status)}`],
                          ].map(([label, value]) => (
                            <div key={label} className="flex justify-between gap-3">
                              <dt className="text-ink-500">{label}</dt>
                              <dd className="font-medium text-ink-800">{value}</dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 border-t border-ink-200 pt-3">
                      {cancellable && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setAction({ order, kind: 'cancel' })
                            setReason('')
                          }}
                        >
                          <XCircle className="h-3.5 w-3.5" />
                          Cancel order
                        </Button>
                      )}
                      {returnable && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setAction({ order, kind: 'return' })
                            setReason('')
                          }}
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          Return item
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => askAura(order, 'Where is my order?')}
                      >
                        Ask Aura about this order
                      </Button>
                    </div>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}

      <Modal
        open={action !== null}
        onClose={() => setAction(null)}
        title={action?.kind === 'cancel' ? 'Cancel this order' : 'Return an item'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAction(null)}>
              Keep it
            </Button>
            <Button
              variant={action?.kind === 'cancel' ? 'danger' : 'primary'}
              loading={busy}
              disabled={!reason.trim()}
              onClick={confirmAction}
            >
              {action?.kind === 'cancel' ? 'Cancel order' : 'Start return'}
            </Button>
          </>
        }
      >
        <p className="mb-4 text-sm text-ink-600">
          {action?.kind === 'cancel'
            ? `Order ${action.order.order_number} will be cancelled and any amount paid refunded to the original payment method in 3–5 business days.`
            : `We'll book a free pickup for order ${action?.order.order_number}. The refund is processed within 48 hours of collection.`}
        </p>
        <Field label="Reason" hint="This helps us fix what went wrong.">
          <Textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={
              action?.kind === 'cancel'
                ? 'Ordered the wrong variant'
                : 'Item arrived damaged'
            }
          />
        </Field>
        {actionError && <p className="mt-3 text-sm text-red-600">{actionError}</p>}
      </Modal>
    </div>
  )
}
