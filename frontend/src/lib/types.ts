/** Mirrors the Pydantic schemas exposed by the FastAPI backend. */

export type UserRole = 'customer' | 'agent' | 'supervisor' | 'admin'
export type CustomerTier = 'standard' | 'silver' | 'gold' | 'platinum'
export type Channel = 'web_chat' | 'voice' | 'email' | 'whatsapp' | 'phone'
export type ConversationStatus = 'active' | 'resolved' | 'escalated' | 'abandoned'
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool' | 'human_agent'
export type TicketStatus =
  | 'open' | 'in_progress' | 'waiting_customer' | 'resolved' | 'closed'
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent'
export type Sentiment =
  | 'very_negative' | 'negative' | 'neutral' | 'positive' | 'very_positive'
export type OrderStatus =
  | 'pending' | 'confirmed' | 'packed' | 'shipped'
  | 'out_for_delivery' | 'delivered' | 'cancelled' | 'returned'

export interface CustomerProfile {
  tier: CustomerTier
  loyalty_points: number
  lifetime_value: number
  total_orders: number
  preferred_language: string
  default_address: string | null
  city: string | null
  pincode: string | null
}

export interface User {
  id: string
  email: string
  full_name: string
  phone: string | null
  role: UserRole
  is_active: boolean
  avatar_url: string | null
  locale: string
  created_at: string
  profile: CustomerProfile | null
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface AuthResponse {
  user: User
  tokens: TokenPair
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/* ------------------------------------------------------------------ catalog */
export interface Category {
  id: string
  name: string
  slug: string
  description: string | null
  icon: string | null
}

export interface Product {
  id: string
  sku: string
  name: string
  brand: string
  description: string
  price: number
  mrp: number
  currency: string
  stock_quantity: number
  is_active: boolean
  rating: number
  review_count: number
  image_url: string | null
  attributes: Record<string, unknown>
  tags: string[]
  return_window_days: number
  is_returnable: boolean
  category: Category | null
}

export interface StoreLocation {
  id: string
  name: string
  address: string
  city: string
  pincode: string
  phone: string | null
  opening_hours: string
  supports_pickup: boolean
}

/* ------------------------------------------------------------------- orders */
export interface OrderItem {
  id: string
  product_id: string
  product_name: string
  sku: string
  quantity: number
  unit_price: number
  line_total: number
}

export interface TrackingEvent {
  at: string
  status: string
  location: string
}

export interface Shipment {
  id: string
  tracking_number: string
  carrier: string
  status: string
  current_location: string | null
  estimated_delivery: string | null
  delivered_at: string | null
  events: TrackingEvent[]
}

export interface ReturnRequest {
  id: string
  rma_number: string
  order_id: string
  reason: string
  status: string
  refund_amount: number
  pickup_scheduled_at: string | null
  created_at: string
}

export interface Order {
  id: string
  order_number: string
  customer_id: string
  status: OrderStatus
  payment_status: string
  payment_method: string
  subtotal: number
  shipping_fee: number
  discount: number
  tax: number
  total_amount: number
  currency: string
  shipping_address: string
  shipping_city: string | null
  placed_at: string | null
  expected_delivery: string | null
  delivered_at: string | null
  items: OrderItem[]
  shipment: Shipment | null
  returns: ReturnRequest[]
}

/* -------------------------------------------------------------------- chat */
export interface Citation {
  document_id: string
  title: string
  snippet: string
  score: number
  slug: string | null
}

export interface ToolTrace {
  tool: string
  arguments: Record<string, unknown>
  result: Record<string, unknown>
  success: boolean
  duration_ms: number
  error: string | null
}

export interface AgentReply {
  conversation_id: string
  message_id: string
  reply: string
  intent: string
  intent_confidence: number
  sentiment: Sentiment
  sentiment_score: number
  citations: Citation[]
  tool_trace: ToolTrace[]
  escalated: boolean
  escalation_reason: string | null
  suggested_replies: string[]
  handoff_ticket_number: string | null
  latency_ms: number
  model: string
  tokens_in: number
  tokens_out: number
}

export interface Message {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  created_at: string
  intent: string | null
  sentiment: Sentiment | null
  sentiment_score: number | null
  tool_calls: Array<Record<string, unknown>>
  citations: Citation[]
  latency_ms: number | null
  model: string | null
}

export interface Conversation {
  id: string
  customer_id: string | null
  channel: Channel
  status: ConversationStatus
  title: string
  language: string
  primary_intent: string
  last_sentiment: Sentiment
  sentiment_score: number
  is_escalated: boolean
  escalation_reason: string | null
  assigned_agent_id: string | null
  resolved_by_ai: boolean
  message_count: number
  total_tokens: number
  voice_seconds: number
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

/* ----------------------------------------------------------------- tickets */
export interface Ticket {
  id: string
  ticket_number: string
  conversation_id: string | null
  customer_id: string | null
  assigned_agent_id: string | null
  subject: string
  description: string
  category: string
  status: TicketStatus
  priority: TicketPriority
  order_id: string | null
  created_by_agent: boolean
  sla_due_at: string | null
  resolved_at: string | null
  resolution_note: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface TicketStats {
  open: number
  in_progress: number
  waiting_customer: number
  resolved: number
  urgent: number
  ai_created: number
  sla_breaching: number
  queue_depth: number
}

/* --------------------------------------------------------------- knowledge */
export interface KBSummary {
  id: string
  title: string
  slug: string
  category: string
  tags: string[]
  view_count: number
  updated_at: string
}

export interface KBDocument extends KBSummary {
  content: string
  language: string
  is_published: boolean
  version: number
  helpful_count: number
  created_at: string
}

export interface KBSearchHit {
  chunk_id: string
  document_id: string
  title: string
  slug: string
  category: string
  snippet: string
  score: number
}

/* --------------------------------------------------------------- analytics */
export interface Kpis {
  total_conversations: number
  conversations_today: number
  active_conversations: number
  ai_resolved: number
  escalated: number
  containment_rate: number
  deflection_rate: number
  avg_csat: number
  csat_responses: number
  avg_handle_time_s: number
  avg_first_response_ms: number
  open_tickets: number
  total_voice_minutes: number
  total_tokens: number
  estimated_cost_usd: number
}

export interface Dashboard {
  kpis: Kpis
  intents: Array<{
    intent: string; count: number; percentage: number
    avg_sentiment: number; escalation_rate: number
  }>
  channels: Array<{
    channel: string; count: number; percentage: number; containment_rate: number
  }>
  timeseries: Array<{
    date: string; conversations: number; escalations: number
    ai_resolved: number; avg_sentiment: number
  }>
  tools: Array<{ tool: string; calls: number; success_rate: number; avg_duration_ms: number }>
  sentiment: Array<{ sentiment: string; count: number; percentage: number }>
  top_articles: Array<{ title: string; slug: string; views: number; helpful: number }>
  generated_at: string
}

/* ------------------------------------------------------------------- voice */
export interface VoiceConfig {
  stt_provider: string
  stt_client_side: boolean
  tts_provider: string
  tts_client_side: boolean
  max_session_seconds: number
  silence_timeout_ms: number
  websocket_path: string
  supported_languages: string[]
}

export interface Capabilities {
  app: string
  version: string
  environment: string
  llm: { provider: string; model: string; max_tool_iterations: number }
  speech: {
    stt_provider: string; stt_client_side: boolean
    tts_provider: string; tts_client_side: boolean
  }
  retrieval: { embedding_provider: string; dim: number; top_k: number }
  tools: string[]
  channels: string[]
  features: Record<string, unknown>
}
