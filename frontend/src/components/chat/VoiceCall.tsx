import {
  AlertTriangle, Bot, Mic, MicOff, PhoneOff, Send, Shield, Volume2, Wrench,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Button, Input, Modal } from '@/components/ui'
import { api, voiceSocketUrl } from '@/lib/api'
import {
  SpeechRecognizer, isRecognitionSupported, playBase64Audio, speak, stopSpeaking,
} from '@/lib/speech'
import type { VoiceConfig } from '@/lib/types'
import { cn, titleCase } from '@/lib/utils'
import { useChat } from '@/store/chat'

type CallState = 'connecting' | 'listening' | 'thinking' | 'speaking' | 'ended' | 'error'

/** Voice sentiment level — determines urgency HUD, no colour icons on UI */
type SentimentLevel = 'calm' | 'neutral' | 'frustrated'

interface Line {
  id: number
  who: 'you' | 'aura'
  text: string
}

const STATE_COPY: Record<CallState, string> = {
  connecting: 'Connecting…',
  listening: 'Listening — go ahead',
  thinking: 'Working on it…',
  speaking: 'Aura is speaking',
  ended: 'Call ended',
  error: 'Something went wrong',
}

const SENTIMENT_LABELS: Record<SentimentLevel, string> = {
  calm: 'Customer: Calm',
  neutral: 'Customer: Neutral',
  frustrated: 'Customer: Frustrated — adjusting response',
}

const SENTIMENT_BAR_COLORS: Record<SentimentLevel, string> = {
  calm: 'bg-emerald-400',
  neutral: 'bg-amber-400',
  frustrated: 'bg-rose-500',
}

/**
 * Heuristic: analyse the last user utterance for frustration signals.
 * Returns a sentiment level without relying on any external service.
 */
function detectSentiment(text: string): SentimentLevel {
  const lower = text.toLowerCase()
  const frustratedKeywords = [
    'angry', 'upset', 'frustrated', 'terrible', 'worst', 'useless', 'stupid',
    'this is ridiculous', 'not acceptable', 'give me a refund', 'I want a refund',
    'speak to manager', 'speak to human', 'you are not helping',
    'hate', 'unacceptable', 'disgusting', 'disappointed', 'never again',
  ]
  const neutralKeywords = ['when', 'how', 'what', 'where', 'can you', 'could you', 'help me', 'want']

  if (frustratedKeywords.some((k) => lower.includes(k))) return 'frustrated'
  if (neutralKeywords.some((k) => lower.includes(k))) return 'neutral'
  return 'calm'
}

/**
 * A live voice session over `/ws/voice`.
 *
 * Two capture paths, chosen by what the backend reports:
 *  - `stt_client_side` (default): the browser recognises speech and sends the
 *    transcript as a `text` frame. No audio leaves the device.
 *  - server-side STT: MediaRecorder chunks are base64-encoded and streamed as
 *    `audio_chunk` frames, terminated by `audio_end`.
 */
export function VoiceCall({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { conversationId, setConversationId, pushUser, pushAssistant } = useChat()

  const [state, setState] = useState<CallState>('connecting')
  const [config, setConfig] = useState<VoiceConfig | null>(null)
  const [lines, setLines] = useState<Line[]>([])
  const [partial, setPartial] = useState('')
  const [streamingReply, setStreamingReply] = useState('')
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [escalated, setEscalated] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [muted, setMuted] = useState(false)
  const [seconds, setSeconds] = useState(0)

  /* ---- Feature: Acoustic Sentiment Meter ---- */
  const [sentiment, setSentiment] = useState<SentimentLevel>('calm')
  const [sentimentVisible, setSentimentVisible] = useState(false)

  /* ---- Feature: Barge-In Visualizer ---- */
  const [bargeInFlash, setBargeInFlash] = useState(false)

  /* ---- Feature: OTP Verification ---- */
  const [otpPrompt, setOtpPrompt] = useState<string | null>(null)
  const [otpInput, setOtpInput] = useState('')
  const [otpSent, setOtpSent] = useState(false)

  const socketRef = useRef<WebSocket | null>(null)
  const recognizerRef = useRef<SpeechRecognizer | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const lineId = useRef(0)
  const mutedRef = useRef(false)
  const transcriptRef = useRef<HTMLDivElement>(null)
  const isSpeakingRef = useRef(false)
  const lastSpokenRef = useRef('')
  const noSpeechStreakRef = useRef(0)
  const callStartRef = useRef<number>(Date.now())
  const issueRef = useRef<string>('')
  const convIdRef = useRef<string | null>(conversationId)

  // Keep convId ref in sync so the endCall closure can read it
  useEffect(() => {
    convIdRef.current = conversationId
  }, [conversationId])

  const addLine = useCallback((who: Line['who'], text: string) => {
    lineId.current += 1
    setLines((current) => [...current.slice(-40), { id: lineId.current, who, text }])
  }, [])

  const [manualText, setManualText] = useState('')

  const sendManualText = (textToSend: string) => {
    const text = textToSend.trim()
    if (!text || socketRef.current?.readyState !== WebSocket.OPEN) return
    setError(null)
    setManualText('')
    setPartial('')
    setStreamingReply('')
    recognizerRef.current?.abort()
    addLine('you', text)
    pushUser(text, true)
    socketRef.current.send(JSON.stringify({ type: 'text', data: text }))
    setState('thinking')
    // Update sentiment on every human utterance
    const lvl = detectSentiment(text)
    setSentiment(lvl)
    setSentimentVisible(true)
    if (!issueRef.current) issueRef.current = text
  }

  /* ----------------------------------------------------------- capture --- */
  const startBrowserListening = useCallback(() => {
    if (mutedRef.current || !isRecognitionSupported() || isSpeakingRef.current) return
    recognizerRef.current?.abort()
    setError(null)

    const userLang =
      typeof navigator !== 'undefined' && navigator.language ? navigator.language : 'en-US'
    const recognizer = new SpeechRecognizer(userLang)
    recognizerRef.current = recognizer
    const started = recognizer.start({
      onPartial: (text) => {
        if (isSpeakingRef.current) return
        noSpeechStreakRef.current = 0
        setError(null)
        setPartial(text)
      },
      onFinal: (text, confidence) => {
        noSpeechStreakRef.current = 0
        if (isSpeakingRef.current) {
          setPartial('')
          return
        }
        setError(null)
        setPartial('')
        const trimmed = text.trim()
        if (!trimmed) return

        // Update sentiment on every human utterance
        const lvl = detectSentiment(trimmed)
        setSentiment(lvl)
        setSentimentVisible(true)
        if (!issueRef.current) issueRef.current = trimmed

        // Immediately show in transcript so the user sees live feedback
        addLine('you', trimmed)
        pushUser(trimmed, true)
        socketRef.current?.send(JSON.stringify({ type: 'text', data: trimmed, confidence }))
        setState('thinking')
      },
      onNoSpeech: () => {
        if (isSpeakingRef.current) return
        noSpeechStreakRef.current += 1
        if (noSpeechStreakRef.current >= 3) {
          setError(
            "Didn't catch that. Check that Chrome has microphone access (Windows: Settings → " +
              'Privacy & security → Microphone) and that the right input device is selected.',
          )
        }
      },
      onEnd: () => {
        if (socketRef.current?.readyState === WebSocket.OPEN && !mutedRef.current && !isSpeakingRef.current) {
          setTimeout(() => {
            if (socketRef.current?.readyState === WebSocket.OPEN && !isSpeakingRef.current) {
              startBrowserListening()
            }
          }, 200)
        }
      },
      onError: (message) => {
        if (message) setError(message)
      },
    })
    if (started) {
      setState('listening')
    }
  }, [addLine, pushUser])

  const startServerCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      recorderRef.current = recorder

      recorder.ondataavailable = async (event) => {
        if (!event.data.size || mutedRef.current) return
        const buffer = await event.data.arrayBuffer()
        const base64 = btoa(String.fromCharCode(...new Uint8Array(buffer)))
        socketRef.current?.send(JSON.stringify({ type: 'audio_chunk', data: base64 }))
      }
      recorder.onstop = () => socketRef.current?.send(JSON.stringify({ type: 'audio_end' }))

      socketRef.current?.send(JSON.stringify({ type: 'start' }))
      recorder.start(500)
      setState('listening')
    } catch {
      setError('Microphone access was denied.')
      setState('error')
    }
  }, [])

  const stopCapture = useCallback(() => {
    recognizerRef.current?.abort()
    recognizerRef.current = null
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    recorderRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }, [])

  /** Barge-in: let the customer cut Aura off mid-reply and start talking. */
  const interruptSpeaking = useCallback(() => {
    if (!isSpeakingRef.current || mutedRef.current) return
    stopSpeaking()
    isSpeakingRef.current = false
    setPartial('')

    // Trigger Barge-In Visualizer flash
    setBargeInFlash(true)
    setTimeout(() => setBargeInFlash(false), 900)

    try {
      socketRef.current?.send(JSON.stringify({ type: 'barge_in' }))
    } catch {
      /* socket already gone */
    }
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      if (config && !config.stt_client_side) {
        void startServerCapture()
      } else {
        startBrowserListening()
      }
    }
  }, [config, startServerCapture, startBrowserListening])

  /** Send OTP entered by the customer back over the WebSocket */
  const submitOtp = () => {
    const otp = otpInput.trim()
    if (!otp) return
    setOtpSent(true)
    const text = `My OTP is ${otp}`
    addLine('you', text)
    pushUser(text, true)
    socketRef.current?.send(JSON.stringify({ type: 'text', data: text }))
    setState('thinking')
    setOtpPrompt(null)
    setOtpInput('')
    setTimeout(() => setOtpSent(false), 3000)
  }

  /** Fire post-call summary to backend (silent, no user-visible output) */
  const saveExecutiveSummary = useCallback(async (cid: string) => {
    try {
      const voiceSeconds = Math.round((Date.now() - callStartRef.current) / 1000)
      const issue = issueRef.current || 'Voice Customer Support Session'
      await api.saveEndCallSummary(cid, {
        issue,
        resolution: 'Session ended. Agent handled via voice.',
        summary: `Voice session of ${voiceSeconds}s. Customer issue: ${issue}`,
        voice_seconds: voiceSeconds,
      })
    } catch {
      /* silent — supervisor-only data, user doesn't need to see errors */
    }
  }, [])

  /* --------------------------------------------------------- lifecycle --- */
  useEffect(() => {
    if (!open) return

    let closed = false
    callStartRef.current = Date.now()
    issueRef.current = ''
    setState('connecting')
    setLines([])
    setPartial('')
    setStreamingReply('')
    setError(null)
    setEscalated(false)
    setSeconds(0)
    setSentiment('calm')
    setSentimentVisible(false)
    setBargeInFlash(false)
    setOtpPrompt(null)
    setOtpInput('')
    noSpeechStreakRef.current = 0

    const timer = setInterval(() => setSeconds((s) => s + 1), 1000)

    ;(async () => {
      let voiceConfig: VoiceConfig | null = null
      try {
        voiceConfig = await api.voiceConfig()
        setConfig(voiceConfig)
      } catch {
        /* fall back to the client-side path */
      }
      if (closed) return

      const socket = new WebSocket(voiceSocketUrl(conversationId, 'en'))
      socketRef.current = socket

      socket.onopen = () => setState('connecting')

      socket.onmessage = async (event) => {
        const frame = JSON.parse(event.data as string) as {
          type: string
          data: Record<string, unknown>
          conversation_id?: string
        }
        const data = frame.data ?? {}

        switch (frame.type) {
          case 'ready': {
            if (frame.conversation_id) {
              setConversationId(frame.conversation_id)
              convIdRef.current = frame.conversation_id
            }
            const greeting = data.greeting as string | undefined
            if (greeting && !lines.length) {
              lastSpokenRef.current = greeting
              isSpeakingRef.current = true
              addLine('aura', greeting)
              setState('speaking')
              try {
                await speak(greeting)
              } catch {
                /* ignore */
              } finally {
                await new Promise((resolve) => setTimeout(resolve, 300))
                isSpeakingRef.current = false
              }
            }
            if (voiceConfig && !voiceConfig.stt_client_side) {
              await startServerCapture()
            } else {
              startBrowserListening()
            }
            break
          }

          case 'final_transcript': {
            const text = (data.text as string) ?? ''
            if (text) {
              setLines((current) => {
                const last = current[current.length - 1]
                if (last && last.who === 'you' && last.text.toLowerCase() === text.toLowerCase()) {
                  return current
                }
                return [...current, { id: lineId.current + 1, who: 'you', text }]
              })
            }
            setPartial('')
            setState('thinking')
            break
          }

          case 'reply_delta': {
            const chunk = (data.text as string) ?? ''
            if (data.interrupted) {
              setStreamingReply('')
            } else if (chunk) {
              setStreamingReply((current) => current + chunk)
            }
            break
          }

          case 'tool_call':
            setActiveTool(data.tool as string)
            // Detect OTP request from the agent tool call
            if ((data.tool as string) === 'send_security_otp' || (data.tool as string) === 'verify_security_otp') {
              setOtpPrompt('Live 4-digit code dispatched to registered mobile. Enter or speak code:')
            }
            break

          case 'tool_result':
            setActiveTool(null)
            if ((data.tool as string) === 'verify_security_otp') {
              setOtpPrompt(null)
            } else if ((data.tool as string) === 'send_security_otp') {
              const res = data.result as Record<string, unknown> | undefined
              const phone = (res?.masked_phone as string) || 'registered mobile'
              setOtpPrompt(`4-digit code dispatched to ${phone}. Enter or speak code:`)
            }
            break

          case 'escalated':
            setEscalated(true)
            break

          case 'reply': {
            const text = (data.text as string) ?? ''
            lastSpokenRef.current = text
            setStreamingReply('')
            addLine('aura', text)
            // Auto-trigger OTP panel in voice call if Aura requests OTP or verification code
            if (/\b(otp|verification code|security code|4-digit|one-time password)\b/i.test(text)) {
              setOtpPrompt('Please enter or speak the 4-digit verification code sent to your registered mobile.')
            }
            pushAssistant({
              content: text,
              escalated: Boolean(data.escalated),
              ticketNumber: (data.handoff_ticket_number as string) ?? null,
              intent: data.intent as string,
              latencyMs: data.latency_ms as number,
              viaVoice: true,
            })
            setActiveTool(null)
            break
          }

          case 'audio': {
            setState('speaking')
            recognizerRef.current?.abort()   // immediately stop microphone
            setPartial('')
            isSpeakingRef.current = true
            const useClient = Boolean(data.use_client_tts)
            try {
              if (useClient) {
                await speak((data.text as string) ?? '')
              } else {
                await playBase64Audio(
                  (data.audio_base64 as string) ?? '',
                  (data.mime_type as string) ?? 'audio/wav',
                )
              }
            } catch {
              /* ignore */
            } finally {
              // Grace period: Wait 350ms after Aura finishes speaking
              await new Promise((resolve) => setTimeout(resolve, 350))
              isSpeakingRef.current = false
              if (socketRef.current?.readyState === WebSocket.OPEN && !mutedRef.current) {
                if (voiceConfig && !voiceConfig.stt_client_side) setState('listening')
                else startBrowserListening()
              }
            }
            break
          }

          case 'clarify': {
            const message = (data.message as string) ?? ''
            setState('speaking')
            recognizerRef.current?.abort()
            setPartial('')
            isSpeakingRef.current = true
            if (message) addLine('aura', message)
            try {
              await speak(message)
            } catch {
              /* ignore */
            } finally {
              await new Promise((resolve) => setTimeout(resolve, 300))
              isSpeakingRef.current = false
              if (socketRef.current?.readyState === WebSocket.OPEN && !mutedRef.current) {
                if (voiceConfig && !voiceConfig.stt_client_side) setState('listening')
                else startBrowserListening()
              }
            }
            break
          }

          case 'error':
            setError((data.message as string) ?? 'Voice error.')
            break

          case 'closed':
            setState('ended')
            break
        }
      }

      socket.onerror = () => {
        setError('The voice connection dropped.')
        setState('error')
      }
      socket.onclose = () => {
        if (!closed) setState('ended')
      }
    })()

    return () => {
      closed = true
      clearInterval(timer)
      stopCapture()
      stopSpeaking()
      try {
        socketRef.current?.send(JSON.stringify({ type: 'stop' }))
      } catch {
        /* socket already gone */
      }
      socketRef.current?.close()
      socketRef.current = null
    }
    // `lines` is intentionally excluded: the socket is set up once per call.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [lines, partial, streamingReply])

  function toggleMute() {
    const next = !muted
    setMuted(next)
    mutedRef.current = next
    if (next) {
      recognizerRef.current?.abort()
      setPartial('')
    } else if (config?.stt_client_side !== false) {
      startBrowserListening()
    }
  }

  function endCall() {
    stopCapture()
    stopSpeaking()
    try {
      socketRef.current?.send(JSON.stringify({ type: 'stop' }))
    } catch {
      /* already closed */
    }
    setState('ended')
    // Silently save executive summary to DB (supervisor-only)
    if (convIdRef.current) {
      void saveExecutiveSummary(convIdRef.current)
    }
    onClose()
  }

  const active = state === 'listening'
  const mmss = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  /* ---------- Sentiment HUD meter ----------
   * 3 bars: calm=1 lit, neutral=2 lit, frustrated=3 lit.
   * No colour icons shown to the customer — just text label + subtle bars. */
  const sentimentBars = sentiment === 'calm' ? 1 : sentiment === 'neutral' ? 2 : 3
  const barColor = SENTIMENT_BAR_COLORS[sentiment]

  return (
    <Modal open={open} onClose={endCall} title="Voice call with Aura">
      <div className="flex flex-col items-center gap-5 py-2">

        {/* ── Barge-In Ripple Flash ── */}
        {bargeInFlash && (
          <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center">
            <span className="block h-40 w-40 animate-ping rounded-full bg-violet-400/30" />
            <span className="absolute block h-20 w-20 animate-ping rounded-full bg-violet-500/40" style={{ animationDelay: '0.15s' }} />
          </div>
        )}

        {/* ── OTP Verification Panel ── */}
        {otpPrompt && (
          <div className="w-full animate-fade-up rounded-2xl border border-violet-400/60 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-4 shadow-[0_0_30px_rgba(139,92,246,0.35)]">
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-600">
                <Shield className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="text-xs font-semibold text-violet-200">Secure Identity Verification</span>
            </div>
            <p className="text-[11px] text-slate-300 mb-3 leading-relaxed">{otpPrompt}</p>
            {!otpSent ? (
              <div className="flex gap-2">
                <input
                  value={otpInput}
                  onChange={(e) => setOtpInput(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  onKeyDown={(e) => { if (e.key === 'Enter') submitOtp() }}
                  placeholder="Enter 6-digit code"
                  maxLength={6}
                  className="flex-1 rounded-xl border border-violet-500/40 bg-white/10 px-3 py-2 text-sm font-mono text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500"
                />
                <button
                  onClick={submitOtp}
                  disabled={otpInput.length < 4}
                  className="rounded-xl bg-violet-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-violet-500 disabled:opacity-40"
                >
                  Verify
                </button>
              </div>
            ) : (
              <p className="text-center text-xs font-semibold text-emerald-400">
                ✓ Verification code submitted
              </p>
            )}
          </div>
        )}

        {/* Orb */}
        <div className="relative flex h-28 w-28 items-center justify-center">
          {active && (
            <>
              <span className="absolute inset-0 animate-pulse-ring rounded-full bg-brand-400/40" />
              <span
                className="absolute inset-0 animate-pulse-ring rounded-full bg-brand-400/30"
                style={{ animationDelay: '0.5s' }}
              />
            </>
          )}
          <div
            role={state === 'speaking' ? 'button' : undefined}
            tabIndex={state === 'speaking' ? 0 : undefined}
            onClick={state === 'speaking' ? interruptSpeaking : undefined}
            onKeyDown={
              state === 'speaking'
                ? (e) => {
                    if (e.key === 'Enter' || e.key === ' ') interruptSpeaking()
                  }
                : undefined
            }
            title={state === 'speaking' ? 'Tap to interrupt' : undefined}
            className={cn(
              'relative flex h-24 w-24 items-center justify-center rounded-full text-white transition-colors',
              state === 'speaking' ? 'cursor-pointer bg-emerald-600 hover:bg-emerald-700'
                : state === 'thinking' ? 'bg-amber-500'
                : state === 'error' ? 'bg-red-600'
                : 'bg-brand-600',
            )}
          >
            {state === 'speaking' ? (
              <Volume2 className="h-9 w-9" />
            ) : state === 'thinking' ? (
              <Bot className="h-9 w-9 animate-pulse" />
            ) : (
              <Mic className="h-9 w-9" />
            )}
          </div>
        </div>

        {/* Animated Audio Frequency Spectrum */}
        <div className="flex items-center justify-center gap-1.5 h-10 px-4 py-1 rounded-2xl bg-slate-950/80 border border-violet-500/30 shadow-[0_0_20px_rgba(139,92,246,0.2)]">
          {[0.2, 0.45, 0.8, 0.35, 0.95, 0.6, 0.4, 0.75, 1.0, 0.85, 0.5, 0.9, 0.65, 0.35, 0.8, 0.55, 0.3, 0.7, 0.9, 0.5, 0.25].map((factor, i) => (
            <span
              key={i}
              className={cn(
                'w-1 rounded-full transition-all duration-150',
                state === 'speaking'
                  ? 'bg-gradient-to-t from-emerald-500 to-teal-300 animate-soundwave shadow-[0_0_8px_rgba(16,185,129,0.5)]'
                  : state === 'listening'
                    ? 'bg-gradient-to-t from-violet-600 to-indigo-300 animate-soundwave shadow-[0_0_8px_rgba(139,92,246,0.5)]'
                    : 'bg-slate-700 h-1.5',
              )}
              style={{
                animationDelay: `${(i * 0.06).toFixed(2)}s`,
                animationDuration: `${(0.55 + factor * 0.45).toFixed(2)}s`,
                height: state === 'speaking' || state === 'listening' ? undefined : '4px',
              }}
            />
          ))}
        </div>

        <div className="text-center">
          <p className="text-sm font-semibold text-ink-900">
            {STATE_COPY[state]}
            {state === 'speaking' && <span className="ml-1 font-normal text-ink-400">(tap to interrupt)</span>}
          </p>
          <p className="mt-0.5 text-xs text-ink-500 font-mono">
            {mmss} · Hands-Free Autonomous Voice Session
          </p>
        </div>

        {/* ── Live Acoustic Sentiment & Urgency HUD ── (no colour icons, text + bars only) */}
        {sentimentVisible && (
          <div className="w-full rounded-xl border border-slate-200/60 bg-slate-50 px-3 py-2">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-semibold text-slate-600">Voice Tone Analysis</span>
              <span className="text-[10px] text-slate-400 font-mono">Live</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-end gap-0.5">
                {[1, 2, 3].map((level) => (
                  <span
                    key={level}
                    className={cn(
                      'w-2 rounded-sm transition-all duration-500',
                      level <= sentimentBars ? barColor : 'bg-slate-200',
                    )}
                    style={{ height: `${level * 6}px` }}
                  />
                ))}
              </div>
              <span className="text-[11px] text-slate-700 font-medium">{SENTIMENT_LABELS[sentiment]}</span>
            </div>
          </div>
        )}

        {activeTool && (
          <div className="inline-flex items-center gap-2 rounded-full border border-violet-400/60 bg-gradient-to-r from-violet-950/90 via-slate-900 to-indigo-950/90 px-3.5 py-1 text-xs font-semibold text-violet-200 shadow-[0_0_15px_rgba(139,92,246,0.3)] animate-fade-up">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <Wrench className="h-3.5 w-3.5 text-violet-400" />
            <span>Autonomous Step: {titleCase(activeTool)}</span>
          </div>
        )}

        {escalated && (
          <p className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800">
            <AlertTriangle className="h-3.5 w-3.5" />
            Handing you to a human agent
          </p>
        )}

        {error && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-center text-xs text-red-700">
            {error}
          </p>
        )}

        {/* Live transcript */}
        <div
          ref={transcriptRef}
          className="h-44 w-full space-y-2 overflow-y-auto scroll-thin rounded-lg border border-ink-200 bg-ink-50 p-3"
        >
          {lines.length === 0 && !partial && !streamingReply && (
            <p className="pt-12 text-center text-xs text-ink-400">
              Say something like "where is my order?"
            </p>
          )}
          {lines.map((line) => (
            <p key={line.id} className="text-xs leading-relaxed">
              <span
                className={cn(
                  'font-semibold',
                  line.who === 'you' ? 'text-ink-700' : 'text-brand-700',
                )}
              >
                {line.who === 'you' ? 'You' : 'Aura'}:{' '}
              </span>
              <span className="text-ink-600">{line.text}</span>
            </p>
          ))}
          {partial && (
            <p className="text-xs italic text-ink-400">
              <span className="font-semibold">You: </span>
              {partial}
            </p>
          )}
          {streamingReply && (
            <p className="text-xs leading-relaxed">
              <span className="font-semibold text-brand-700">Aura: </span>
              <span className="text-ink-600">{streamingReply}</span>
            </p>
          )}
        </div>

        {/* Quick prompt chips & text input backup */}
        <div className="w-full space-y-2">
          <div className="flex flex-wrap items-center justify-center gap-1.5">
            <button
              type="button"
              disabled={state === 'thinking'}
              onClick={() => sendManualText('Where is my order?')}
              className="rounded-full border border-ink-200 bg-white px-2.5 py-1 text-[11px] font-medium text-ink-600 transition hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"
            >
              "Where is my order?"
            </button>
            <button
              type="button"
              disabled={state === 'thinking'}
              onClick={() => sendManualText('What is your refund policy?')}
              className="rounded-full border border-ink-200 bg-white px-2.5 py-1 text-[11px] font-medium text-ink-600 transition hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"
            >
              "What is your refund policy?"
            </button>
            <button
              type="button"
              disabled={state === 'thinking'}
              onClick={() => sendManualText('Can I speak to a human agent?')}
              className="rounded-full border border-ink-200 bg-white px-2.5 py-1 text-[11px] font-medium text-ink-600 transition hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"
            >
              "Speak to a human"
            </button>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              sendManualText(manualText)
            }}
            className="flex items-center gap-2"
          >
            <Input
              value={manualText}
              onChange={(e) => setManualText(e.target.value)}
              placeholder="Or type here to talk with Aura…"
              className="h-8 text-xs flex-1"
            />
            <Button
              size="sm"
              type="submit"
              disabled={!manualText.trim() || state === 'thinking'}
            >
              <Send className="h-3.5 w-3.5" />
            </Button>
          </form>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant={muted ? 'danger' : 'outline'}
            size="icon"
            onClick={toggleMute}
            title={muted ? 'Unmute' : 'Mute'}
          >
            {muted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          </Button>
          <Button variant="danger" onClick={endCall}>
            <PhoneOff className="h-4 w-4" />
            End call
          </Button>
        </div>

        {!isRecognitionSupported() && (
          <p className="text-center text-xs text-ink-500">
            Speech recognition is not supported in this browser. Please open in Chrome, Edge, or Safari for voice calls.
          </p>
        )}
      </div>
    </Modal>
  )
}
