/**
 * Typed API client.
 *
 * One place owns the base URL, the bearer token, error shape translation and
 * automatic refresh-on-401, so no component ever touches `fetch` directly.
 */

import type {
  AgentReply, AuthResponse, Capabilities, Category, Conversation, ConversationDetail,
  Dashboard, KBDocument, KBSearchHit, KBSummary, Order, Page, Product,
  StoreLocation, Ticket, TicketStats, User, VoiceConfig,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const ACCESS_KEY = 'rv.access_token'
const REFRESH_KEY = 'rv.refresh_token'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export const tokenStore = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

type Query = Record<string, string | number | boolean | undefined | null>

function buildUrl(path: string, query?: Query): string {
  const url = `${BASE}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params.append(key, String(value))
    }
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

let refreshing: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  const token = tokenStore.refresh()
  if (!token) return false
  // Collapse concurrent 401s into a single refresh round-trip.
  refreshing ??= (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: token }),
      })
      if (!response.ok) return false
      const data = await response.json()
      tokenStore.set(data.access_token, data.refresh_token)
      return true
    } catch {
      return false
    } finally {
      setTimeout(() => (refreshing = null), 0)
    }
  })()
  return refreshing
}

interface RequestOptions {
  method?: string
  body?: unknown
  query?: Query
  formData?: FormData
  auth?: boolean
  retryOn401?: boolean
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, formData, auth = true, retryOn401 = true } = options

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = tokenStore.access()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  })

  if (response.status === 401 && retryOn401 && (await tryRefresh())) {
    return request<T>(path, { ...options, retryOn401: false })
  }

  if (!response.ok) {
    let code = 'http_error'
    let message = `Request failed with status ${response.status}`
    let details: Record<string, unknown> = {}
    try {
      const payload = await response.json()
      if (payload?.error) {
        code = payload.error.code ?? code
        message = payload.error.message ?? message
        details = payload.error.details ?? {}
      } else if (payload?.detail) {
        message = typeof payload.detail === 'string'
          ? payload.detail
          : JSON.stringify(payload.detail)
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, code, message, details)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/* ------------------------------------------------------------------------- */
export const api = {
  /* system */
  capabilities: () => request<Capabilities>('/capabilities', { auth: false }),
  health: () => request<{ status: string; version: string }>('/health', { auth: false }),

  /* auth */
  login: (email: string, password: string) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST', body: { email, password }, auth: false,
    }),
  register: (payload: { email: string; password: string; full_name: string; phone?: string }) =>
    request<AuthResponse>('/auth/register', { method: 'POST', body: payload, auth: false }),
  me: () => request<User>('/auth/me'),
  updateMe: (payload: Record<string, unknown>) =>
    request<User>('/auth/me', { method: 'PATCH', body: payload }),

  /* catalogue */
  categories: () => request<Category[]>('/catalog/categories', { auth: false }),
  products: (query?: Query) =>
    request<Page<Product>>('/catalog/products', { query, auth: false }),
  product: (id: string) => request<Product>(`/catalog/products/${id}`, { auth: false }),
  stores: (query?: Query) =>
    request<StoreLocation[]>('/catalog/stores', { query, auth: false }),

  /* orders */
  orders: (query?: Query) => request<Page<Order>>('/orders', { query }),
  order: (reference: string) => request<Order>(`/orders/${reference}`),
  createOrder: (payload: Record<string, unknown>) =>
    request<Order>('/orders', { method: 'POST', body: payload }),
  cancelOrder: (reference: string, reason: string) =>
    request<Order>(`/orders/${reference}/cancel`, { method: 'POST', body: { reason } }),
  createReturn: (reference: string, payload: Record<string, unknown>) =>
    request(`/orders/${reference}/returns`, { method: 'POST', body: payload }),
  tracking: (reference: string) =>
    request<Record<string, unknown>>(`/orders/${reference}/tracking`),

  /* chat */
  sendMessage: (payload: {
    message: string
    conversation_id?: string | null
    channel?: string
    language?: string
    anonymous_key?: string
    voice_mode?: boolean
  }) => request<AgentReply>('/chat/message', { method: 'POST', body: payload }),
  createConversation: (payload: Record<string, unknown> = {}) =>
    request<Conversation>('/chat/conversations', { method: 'POST', body: payload }),
  conversations: (query?: Query) =>
    request<Page<Conversation>>('/chat/conversations', { query }),
  conversation: (id: string) => request<ConversationDetail>(`/chat/conversations/${id}`),
  closeConversation: (id: string) =>
    request(`/chat/conversations/${id}/close`, { method: 'POST' }),
  handoff: (id: string, note?: string) =>
    request<{ escalated: boolean; ticket_number: string; queue_position: number }>(
      `/chat/conversations/${id}/handoff`,
      { method: 'POST', body: { reason: 'customer_request', note } },
    ),
  agentReply: (id: string, content: string) =>
    request(`/chat/conversations/${id}/reply`, { method: 'POST', body: { content } }),
  submitFeedback: (id: string, payload: { rating: number; resolved: boolean; comment?: string }) =>
    request(`/chat/conversations/${id}/feedback`, { method: 'POST', body: payload }),
  saveEndCallSummary: (
    id: string,
    payload: {
      issue?: string
      resolution?: string
      summary?: string
      rma_or_refund_id?: string
      next_steps?: string
      voice_seconds?: number
    },
  ) => request(`/chat/conversations/${id}/end_call_summary`, { method: 'POST', body: payload }),

  /* voice */
  voiceConfig: () => request<VoiceConfig>('/voice/config', { auth: false }),
  voiceTurn: (form: FormData) =>
    request<{
      transcript: { text: string; confidence: number }
      reply: AgentReply
      audio: { audio_base64: string; mime_type: string; use_client_tts: boolean; text: string } | null
    }>('/voice/turn', { method: 'POST', formData: form }),
  synthesize: (text: string) =>
    request<{ audio_base64: string; mime_type: string; use_client_tts: boolean; text: string }>(
      '/voice/synthesize', { method: 'POST', body: { text } },
    ),

  /* tickets */
  tickets: (query?: Query) => request<Page<Ticket>>('/tickets', { query }),
  ticket: (id: string) => request<Ticket>(`/tickets/${id}`),
  ticketStats: () => request<TicketStats>('/tickets/stats'),
  updateTicket: (id: string, payload: Record<string, unknown>) =>
    request<Ticket>(`/tickets/${id}`, { method: 'PATCH', body: payload }),
  claimTicket: (id: string) => request<Ticket>(`/tickets/${id}/claim`, { method: 'POST' }),
  createTicket: (payload: Record<string, unknown>) =>
    request<Ticket>('/tickets', { method: 'POST', body: payload }),

  /* knowledge */
  kbSearch: (q: string, topK = 5) =>
    request<{ query: string; hits: KBSearchHit[]; took_ms: number }>(
      '/knowledge/search', { query: { q, top_k: topK }, auth: false },
    ),
  kbList: (query?: Query) => request<Page<KBSummary>>('/knowledge', { query, auth: false }),
  kbCategories: () =>
    request<Array<{ category: string; count: number }>>('/knowledge/categories', { auth: false }),
  kbDocument: (idOrSlug: string) =>
    request<KBDocument>(`/knowledge/${idOrSlug}`, { auth: false }),
  kbCreate: (payload: Record<string, unknown>) =>
    request<KBDocument>('/knowledge', { method: 'POST', body: payload }),
  kbUpdate: (id: string, payload: Record<string, unknown>) =>
    request<KBDocument>(`/knowledge/${id}`, { method: 'PATCH', body: payload }),
  kbDelete: (id: string) => request(`/knowledge/${id}`, { method: 'DELETE' }),
  kbReindex: () =>
    request<{ documents: number; chunks: number; took_ms: number }>(
      '/knowledge/reindex', { method: 'POST' },
    ),
  kbStats: () =>
    request<{ documents: number; chunks: number; embedding_model: string; dim: number }>(
      '/knowledge/stats', { auth: false },
    ),

  /* analytics */
  dashboard: (days = 30) => request<Dashboard>('/analytics/dashboard', { query: { days } }),
}

/** WebSocket URL for the voice session, carrying the JWT as a query param
 *  (browsers cannot set headers on a WebSocket handshake). */
export function voiceSocketUrl(conversationId?: string | null, language = 'en'): string {
  let protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  let host = location.host

  if (import.meta.env.VITE_WS_HOST) {
    host = import.meta.env.VITE_WS_HOST
  } else if (import.meta.env.VITE_API_BASE_URL) {
    try {
      const url = new URL(import.meta.env.VITE_API_BASE_URL, window.location.origin)
      host = url.host
      protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    } catch {
      /* fallback to location.host */
    }
  }

  const params = new URLSearchParams({ language })
  const token = tokenStore.access()
  if (token) params.set('token', token)
  if (conversationId) params.set('conversation_id', conversationId)
  return `${protocol}//${host}/ws/voice?${params.toString()}`
}
