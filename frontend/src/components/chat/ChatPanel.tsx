import {
  Bot, Headphones, Mic, MicOff, RotateCcw, Send, Sparkles, Star, UserCog,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { MessageBubble } from './MessageBubble'
import { Button } from '@/components/ui'
import { api } from '@/lib/api'
import {
  SpeechRecognizer, isRecognitionSupported, isSynthesisSupported, speak, stopSpeaking, toSpeakable,
} from '@/lib/speech'
import { cn, titleCase } from '@/lib/utils'
import { useChat } from '@/store/chat'

const GREETING =
  "Hi! I'm **Aura**, your NovaMart assistant. I can track an order, start a return, " +
  'check stock or answer a policy question. What can I help you with?'

interface ChatPanelProps {
  /** `page` fills its container; `widget` is the floating storefront bubble. */
  variant?: 'page' | 'widget'
  className?: string
}

export function ChatPanel({ variant = 'page', className }: ChatPanelProps) {
  const {
    messages, suggestions, stage, activeTool, escalated,
    send, greet, requestHuman, reset, error, setVoiceCallOpen,
  } = useChat()

  const [draft, setDraft] = useState('')
  const [dictating, setDictating] = useState(false)
  const [interim, setInterim] = useState('')
  const [speakReplies, setSpeakReplies] = useState(false)

  /* ── CSAT Voice Survey ── */
  const [csatVisible, setCsatVisible] = useState(false)
  const [csatRating, setCsatRating] = useState(0)
  const [csatHover, setCsatHover] = useState(0)
  const [csatComment, setCsatComment] = useState('')
  const [csatSubmitted, setCsatSubmitted] = useState(false)
  const prevVoiceOpen = useRef(false)

  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const recognizerRef = useRef<SpeechRecognizer | null>(null)
  const spokenRef = useRef<string | null>(null)

  useEffect(() => greet(GREETING), [greet])

  // Detect voice call close → show CSAT survey
  const { voiceCallOpen, conversationId } = useChat()
  useEffect(() => {
    if (prevVoiceOpen.current && !voiceCallOpen) {
      setCsatVisible(true)
      setCsatRating(0)
      setCsatHover(0)
      setCsatComment('')
      setCsatSubmitted(false)
    }
    prevVoiceOpen.current = voiceCallOpen
  }, [voiceCallOpen])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, stage])

  // Read the newest assistant reply aloud when "speak replies" is on.
  useEffect(() => {
    if (!speakReplies || !isSynthesisSupported()) return
    const last = messages[messages.length - 1]
    if (!last || last.role !== 'assistant' || last.id === spokenRef.current) return
    spokenRef.current = last.id
    void speak(toSpeakable(last.content))
  }, [messages, speakReplies])

  useEffect(() => () => {
    recognizerRef.current?.abort()
    stopSpeaking()
  }, [])

  const busy = stage !== 'idle'

  async function submit(text: string) {
    const value = text.trim()
    if (!value || busy) return
    setDraft('')
    setInterim('')
    await send(value)
    inputRef.current?.focus()
  }

  function toggleDictation() {
    if (dictating) {
      recognizerRef.current?.stop()
      setDictating(false)
      return
    }
    const recognizer = new SpeechRecognizer()
    recognizerRef.current = recognizer
    const started = recognizer.start({
      onPartial: setInterim,
      onFinal: (text) => {
        setInterim('')
        setDraft((current) => (current ? `${current} ${text}` : text))
      },
      onEnd: () => setDictating(false),
      onError: () => setDictating(false),
    })
    setDictating(started)
  }

  const stageLabel =
    stage === 'using_tool' && activeTool
      ? `Checking ${titleCase(activeTool).toLowerCase()}…`
      : stage === 'writing'
        ? 'Writing a reply…'
        : 'Thinking…'

  return (
    <div
      className={cn(
        'flex min-h-0 flex-col overflow-hidden bg-ink-50',
        variant === 'page' ? 'h-full rounded-xl border border-ink-200' : 'h-full',
        className,
      )}
    >
      {/* Header */}
      <header className="flex items-center justify-between gap-3 border-b border-ink-200 bg-white px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="relative">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-white">
              <Bot className="h-5 w-5" />
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-900">Aura · NovaMart Support</p>
            <p className="text-xs text-ink-500">
              {escalated ? 'Human agent joining…' : 'Online · replies in seconds'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {isSynthesisSupported() && (
            <Button
              size="icon"
              variant="ghost"
              title={speakReplies ? 'Turn off spoken replies' : 'Read replies aloud'}
              onClick={() => {
                stopSpeaking()
                setSpeakReplies((v) => !v)
              }}
              className={cn(speakReplies && 'bg-brand-50 text-brand-700')}
            >
              <Headphones className="h-4 w-4" />
            </Button>
          )}
          <Button
            size="icon"
            variant="ghost"
            title="Start a voice call"
            onClick={() => setVoiceCallOpen(true)}
          >
            <Mic className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" title="New conversation" onClick={reset}>
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* Transcript */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto scroll-thin px-4 py-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {/* ── Automated CSAT Voice Survey ── */}
        {csatVisible && !csatSubmitted && (
          <div className="animate-fade-up rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-4 shadow-sm">
            <p className="text-sm font-semibold text-violet-900 mb-1">
              How was your experience with Aura today?
            </p>
            <p className="text-xs text-violet-600 mb-3">
              Your feedback helps us improve our service.
            </p>
            <div className="flex items-center gap-1 mb-3">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onMouseEnter={() => setCsatHover(star)}
                  onMouseLeave={() => setCsatHover(0)}
                  onClick={() => setCsatRating(star)}
                  className="transition-transform hover:scale-110"
                  aria-label={`Rate ${star} out of 5`}
                >
                  <Star
                    className={cn(
                      'h-7 w-7 transition-colors',
                      (csatHover || csatRating) >= star
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-slate-300',
                    )}
                  />
                </button>
              ))}
              {csatRating > 0 && (
                <span className="ml-2 text-xs font-medium text-violet-700">
                  {csatRating === 5 ? 'Excellent!' : csatRating >= 4 ? 'Good' : csatRating >= 3 ? 'Average' : csatRating >= 2 ? 'Poor' : 'Very Poor'}
                </span>
              )}
            </div>
            <textarea
              value={csatComment}
              onChange={(e) => setCsatComment(e.target.value)}
              placeholder="Any additional comments? (optional)"
              rows={2}
              className="input mb-3 w-full resize-none text-xs"
            />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                disabled={csatRating === 0}
                onClick={async () => {
                  if (conversationId && csatRating > 0) {
                    try {
                      await api.submitFeedback(conversationId, {
                        rating: csatRating,
                        resolved: true,
                        comment: csatComment || undefined,
                      })
                    } catch { /* silent */ }
                  }
                  setCsatSubmitted(true)
                }}
              >
                Submit feedback
              </Button>
              <button
                onClick={() => setCsatVisible(false)}
                className="text-xs text-slate-400 hover:text-slate-600 transition"
              >
                Skip
              </button>
            </div>
          </div>
        )}
        {csatSubmitted && csatVisible && (
          <div className="animate-fade-up rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
            Thank you for your feedback! Your rating has been recorded.
          </div>
        )}

        {busy && (
          <div className="flex flex-col gap-2 rounded-2xl border border-violet-400/40 bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 p-3.5 text-white shadow-[0_0_25px_rgba(139,92,246,0.25)] animate-fade-up">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <div className="flex items-center gap-2">
                <div className="relative flex h-6 w-6 items-center justify-center rounded-lg bg-violet-600 text-white shadow-xs">
                  <Bot className="h-3.5 w-3.5" />
                  <span className="absolute inset-0 rounded-lg bg-violet-400/40 animate-pulse-ring" />
                </div>
                <div>
                  <span className="text-xs font-bold text-white flex items-center gap-1.5">
                    Live Autonomous Tool Execution
                    <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-mono text-violet-300 bg-violet-500/20 px-2 py-0.5 rounded-full border border-violet-400/30">
                {stage === 'using_tool' ? 'Step 2/3: Executing' : stage === 'writing' ? 'Step 3/3: Synthesizing' : 'Step 1/3: Reasoning'}
              </span>
            </div>

            {/* Step-by-Step Agent Reasoning Badges */}
            <div className="grid grid-cols-3 gap-2 pt-1">
              <div className={cn(
                'flex items-center gap-1.5 rounded-lg p-1.5 text-[10px] font-medium border transition',
                stage === 'thinking'
                  ? 'border-violet-400/60 bg-violet-500/20 text-white'
                  : 'border-white/10 bg-white/5 text-slate-300'
              )}>
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <span className="truncate">1. Ingest Intent</span>
              </div>

              <div className={cn(
                'flex items-center gap-1.5 rounded-lg p-1.5 text-[10px] font-medium border transition',
                stage === 'using_tool'
                  ? 'border-violet-400/80 bg-violet-600/30 text-violet-200 shadow-[0_0_15px_rgba(139,92,246,0.3)]'
                  : stage === 'writing'
                    ? 'border-white/10 bg-white/5 text-slate-300'
                    : 'border-white/5 bg-white/5 text-slate-400'
              )}>
                <span className={cn('h-1.5 w-1.5 rounded-full', stage === 'using_tool' ? 'bg-violet-400 animate-pulse' : 'bg-slate-400')} />
                <span className="truncate">{activeTool ? titleCase(activeTool) : '2. System Verify'}</span>
              </div>

              <div className={cn(
                'flex items-center gap-1.5 rounded-lg p-1.5 text-[10px] font-medium border transition',
                stage === 'writing'
                  ? 'border-emerald-400/60 bg-emerald-500/20 text-emerald-200'
                  : 'border-white/5 bg-white/5 text-slate-400'
              )}>
                <span className={cn('h-1.5 w-1.5 rounded-full', stage === 'writing' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400')} />
                <span className="truncate">3. Final Reply</span>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-0.5 text-xs text-slate-300">
              <span className="flex gap-1" aria-hidden>
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-1.5 w-1.5 animate-blink rounded-full bg-violet-400"
                    style={{ animationDelay: `${i * 0.18}s` }}
                  />
                ))}
              </span>
              <span className="text-[11px] text-slate-200 font-medium">
                {stageLabel}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-ink-200 bg-white px-4 py-3">
        {error && <p className="mb-2 text-xs text-red-600">{error}</p>}

        {suggestions.length > 0 && !busy && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {suggestions.slice(0, 3).map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => submit(suggestion)}
                className="inline-flex items-center gap-1 rounded-full border border-ink-200 bg-white px-3 py-1 text-xs font-medium text-ink-600 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
              >
                <Sparkles className="h-3 w-3" />
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2">
          <div className="relative flex-1">
            <textarea
              ref={inputRef}
              rows={1}
              value={dictating && interim ? `${draft} ${interim}`.trim() : draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void submit(draft)
                }
              }}
              placeholder={dictating ? 'Listening…' : 'Ask about an order, return or product…'}
              disabled={busy}
              className="input max-h-32 min-h-[42px] resize-none py-2.5 pr-10"
            />
            {isRecognitionSupported() && (
              <button
                onClick={toggleDictation}
                title={dictating ? 'Stop dictation' : 'Dictate a message'}
                className={cn(
                  'absolute bottom-2 right-2 rounded-md p-1.5 transition',
                  dictating
                    ? 'bg-red-100 text-red-600'
                    : 'text-ink-400 hover:bg-ink-100 hover:text-ink-700',
                )}
              >
                {dictating ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </button>
            )}
          </div>

          <Button
            size="icon"
            onClick={() => submit(draft)}
            disabled={busy || !draft.trim()}
            title="Send"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>

        {!escalated && (
          <button
            onClick={() => void requestHuman()}
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-ink-500 transition hover:text-brand-700"
          >
            <UserCog className="h-3.5 w-3.5" />
            Talk to a human agent
          </button>
        )}
      </div>
    </div>
  )
}
