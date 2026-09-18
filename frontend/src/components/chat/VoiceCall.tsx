import {
  AlertTriangle, Bot, Mic, MicOff, PhoneOff, Send, Volume2, Wrench,
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
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [escalated, setEscalated] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [muted, setMuted] = useState(false)
  const [seconds, setSeconds] = useState(0)

  const socketRef = useRef<WebSocket | null>(null)
  const recognizerRef = useRef<SpeechRecognizer | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const lineId = useRef(0)
  const mutedRef = useRef(false)
  const transcriptRef = useRef<HTMLDivElement>(null)
  const isSpeakingRef = useRef(false)
  const lastSpokenRef = useRef('')

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
    recognizerRef.current?.abort()
    addLine('you', text)
    pushUser(text, true)
    socketRef.current.send(JSON.stringify({ type: 'text', data: text }))
    setState('thinking')
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
        setError(null)
        setPartial(text)
      },
      onFinal: (text) => {
        if (isSpeakingRef.current) {
          setPartial('')
          return
        }
        setError(null)
        setPartial('')
        const trimmed = text.trim()
        if (!trimmed) return

        // Immediately show in transcript so the user sees live feedback
        addLine('you', trimmed)
        pushUser(trimmed, true)
        socketRef.current?.send(JSON.stringify({ type: 'text', data: trimmed }))
        setState('thinking')
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

  /* --------------------------------------------------------- lifecycle --- */
  useEffect(() => {
    if (!open) return

    let closed = false
    setState('connecting')
    setLines([])
    setPartial('')
    setError(null)
    setEscalated(false)
    setSeconds(0)

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
            if (frame.conversation_id) setConversationId(frame.conversation_id)
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

          case 'tool_call':
            setActiveTool(data.tool as string)
            break

          case 'tool_result':
            setActiveTool(null)
            break

          case 'escalated':
            setEscalated(true)
            break

          case 'reply': {
            const text = (data.text as string) ?? ''
            lastSpokenRef.current = text
            addLine('aura', text)
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
  }, [lines, partial])

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
    onClose()
  }

  const active = state === 'listening'
  const mmss = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <Modal open={open} onClose={endCall} title="Voice call with Aura">
      <div className="flex flex-col items-center gap-5 py-2">
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
            className={cn(
              'relative flex h-24 w-24 items-center justify-center rounded-full text-white transition-colors',
              state === 'speaking' ? 'bg-emerald-600'
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

        <div className="text-center">
          <p className="text-sm font-semibold text-ink-900">{STATE_COPY[state]}</p>
          <p className="mt-0.5 text-xs text-ink-500">
            {mmss}
            {config && (
              <>
                {' · '}
                {config.stt_client_side ? 'on-device speech' : `${config.stt_provider} STT`}
              </>
            )}
          </p>
        </div>

        {activeTool && (
          <p className="inline-flex items-center gap-1.5 rounded-full bg-ink-100 px-3 py-1 text-xs text-ink-600">
            <Wrench className="h-3 w-3" />
            {titleCase(activeTool)}
          </p>
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
          {lines.length === 0 && !partial && (
            <p className="pt-12 text-center text-xs text-ink-400">
              Say something like “where is my order?”
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

        {!isRecognitionSupported() && config?.stt_client_side && (
          <p className="text-center text-xs text-ink-500">
            This browser has no speech recognition. Chrome, Edge or Safari support it —
            or set <code className="font-mono">STT_PROVIDER=whisper</code> on the server
            to transcribe audio server-side.
          </p>
        )}
      </div>
    </Modal>
  )
}
