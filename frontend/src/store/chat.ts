import { create } from 'zustand'

import { api } from '@/lib/api'
import type { AgentReply, Citation, ToolTrace } from '@/lib/types'
import { anonymousKey } from '@/lib/utils'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  pending?: boolean
  failed?: boolean
  citations?: Citation[]
  toolTrace?: ToolTrace[]
  intent?: string
  sentiment?: string
  sentimentScore?: number
  latencyMs?: number
  model?: string
  escalated?: boolean
  ticketNumber?: string | null
  viaVoice?: boolean
}

/** Live status of the current turn, surfaced in the composer. */
export type AgentStage = 'idle' | 'thinking' | 'using_tool' | 'writing'

interface ChatState {
  conversationId: string | null
  messages: ChatMessage[]
  suggestions: string[]
  stage: AgentStage
  activeTool: string | null
  escalated: boolean
  ticketNumber: string | null
  error: string | null

  greet: (text: string) => void
  send: (text: string, options?: { voiceMode?: boolean }) => Promise<AgentReply | null>
  requestHuman: () => Promise<void>
  pushUser: (text: string, viaVoice?: boolean) => string
  pushAssistant: (message: Omit<ChatMessage, 'id' | 'role' | 'createdAt'>) => void
  setStage: (stage: AgentStage, tool?: string | null) => void
  setConversationId: (id: string | null) => void
  voiceCallOpen: boolean
  setVoiceCallOpen: (open: boolean) => void
  reset: () => void
}

const uid = () => `m_${Math.random().toString(36).slice(2, 11)}`

export const useChat = create<ChatState>((set, get) => ({
  conversationId: null,
  messages: [],
  suggestions: ['Track my order', 'Start a return', 'What is your refund policy?'],
  stage: 'idle',
  activeTool: null,
  escalated: false,
  ticketNumber: null,
  error: null,
  voiceCallOpen: false,
  setVoiceCallOpen: (open) => set({ voiceCallOpen: open }),

  greet(text) {
    if (get().messages.length) return
    set({
      messages: [
        { id: uid(), role: 'assistant', content: text, createdAt: new Date().toISOString() },
      ],
    })
  },

  pushUser(text, viaVoice = false) {
    const id = uid()
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id, role: 'user', content: text,
          createdAt: new Date().toISOString(), viaVoice,
        },
      ],
      error: null,
    }))
    return id
  },

  pushAssistant(message) {
    set((state) => ({
      messages: [
        ...state.messages,
        { id: uid(), role: 'assistant', createdAt: new Date().toISOString(), ...message },
      ],
      stage: 'idle',
      activeTool: null,
    }))
  },

  setStage(stage, tool = null) {
    set({ stage, activeTool: tool })
  },

  setConversationId(id) {
    set({ conversationId: id })
  },

  async send(text, options = {}) {
    const trimmed = text.trim()
    if (!trimmed || get().stage !== 'idle') return null

    get().pushUser(trimmed, options.voiceMode)
    set({ stage: 'thinking', activeTool: null })

    try {
      const reply = await api.sendMessage({
        message: trimmed,
        conversation_id: get().conversationId,
        channel: options.voiceMode ? 'voice' : 'web_chat',
        anonymous_key: anonymousKey(),
        voice_mode: options.voiceMode ?? false,
      })

      set({ conversationId: reply.conversation_id })
      get().pushAssistant({
        content: reply.reply,
        citations: reply.citations,
        toolTrace: reply.tool_trace,
        intent: reply.intent,
        sentiment: reply.sentiment,
        sentimentScore: reply.sentiment_score,
        latencyMs: reply.latency_ms,
        model: reply.model,
        escalated: reply.escalated,
        ticketNumber: reply.handoff_ticket_number,
      })
      set({
        suggestions: reply.suggested_replies?.length
          ? reply.suggested_replies
          : get().suggestions,
        escalated: reply.escalated || get().escalated,
        ticketNumber: reply.handoff_ticket_number ?? get().ticketNumber,
      })
      return reply
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'The assistant could not be reached.'
      set({ stage: 'idle', activeTool: null, error: message })
      get().pushAssistant({
        content:
          "I couldn't reach the support service just then. Please check your connection " +
          'and try again — your conversation has been kept.',
        failed: true,
      })
      return null
    }
  },

  async requestHuman() {
    const id = get().conversationId
    if (!id) return
    try {
      const result = await api.handoff(id, 'Customer used the "talk to a human" control.')
      set({ escalated: true, ticketNumber: result.ticket_number })
      get().pushAssistant({
        content:
          `I'm connecting you with a human colleague now. Your reference is ` +
          `**${result.ticket_number}** and you're number ${result.queue_position} in the queue.`,
        escalated: true,
        ticketNumber: result.ticket_number,
      })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Handoff failed.' })
    }
  },

  reset() {
    set({
      conversationId: null,
      messages: [],
      stage: 'idle',
      activeTool: null,
      escalated: false,
      ticketNumber: null,
      error: null,
      suggestions: ['Track my order', 'Start a return', 'What is your refund policy?'],
    })
  },
}))
