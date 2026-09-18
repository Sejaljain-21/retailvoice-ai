/**
 * Browser speech helpers.
 *
 * The default backend configuration (`STT_PROVIDER=browser`, `TTS_PROVIDER=browser`)
 * puts recognition and synthesis in the client. That removes the audio
 * round-trip entirely, needs no API keys, and works offline - at the cost of
 * being Chrome/Edge/Safari only for recognition. If the backend reports a
 * server-side provider instead, these helpers are simply not used.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

export interface RecognitionHandlers {
  onPartial?: (text: string) => void
  onFinal?: (text: string, confidence: number) => void
  onError?: (message: string) => void
  onEnd?: () => void
}

function getRecognitionCtor(): any | null {
  const w = window as any
  return w.SpeechRecognition || w.webkitSpeechRecognition || null
}

export function isRecognitionSupported(): boolean {
  return getRecognitionCtor() !== null
}

export function isSynthesisSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

/** Continuous dictation with interim results. Returns a stop function. */
export class SpeechRecognizer {
  private recognition: any = null
  private stopped = false

  constructor(
    private language = typeof navigator !== 'undefined' && navigator.language
      ? navigator.language
      : 'en-US',
  ) {}

  start(handlers: RecognitionHandlers): boolean {
    const Ctor = getRecognitionCtor()
    if (!Ctor) {
      handlers.onError?.(
        'Speech recognition is not available in this browser. Chrome, Edge or Safari support it.',
      )
      return false
    }

    this.stopped = false
    const recognition = new Ctor()
    recognition.lang = this.language
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onresult = (event: any) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        const transcript = result[0].transcript as string
        if (result.isFinal) {
          handlers.onFinal?.(transcript.trim(), result[0].confidence ?? 0.9)
        } else {
          interim += transcript
        }
      }
      if (interim) handlers.onPartial?.(interim.trim())
    }

    recognition.onerror = (event: any) => {
      // Natural silence ('no-speech') or aborts are not errors
      if (event.error === 'no-speech' || event.error === 'aborted') {
        return
      }
      const map: Record<string, string> = {
        'audio-capture': 'No microphone was found. Please check your audio settings.',
        'not-allowed': 'Microphone permission was denied. Please allow microphone access in your browser address bar.',
        network: 'Speech recognition service temporarily unavailable.',
      }
      handlers.onError?.(map[event.error] ?? `Speech recognition notice: ${event.error}`)
    }

    recognition.onend = () => {
      if (!this.stopped) handlers.onEnd?.()
    }

    this.recognition = recognition
    try {
      recognition.start()
      return true
    } catch {
      handlers.onError?.('Could not start the microphone.')
      return false
    }
  }

  stop(): void {
    this.stopped = true
    try {
      this.recognition?.stop()
    } catch {
      /* already stopped */
    }
  }

  abort(): void {
    this.stopped = true
    try {
      this.recognition?.abort()
    } catch {
      /* already stopped */
    }
  }
}

/* -------------------------------------------------------------------------- */
let cachedVoices: SpeechSynthesisVoice[] = []

function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    const voices = window.speechSynthesis.getVoices()
    if (voices.length) {
      cachedVoices = voices
      resolve(voices)
      return
    }
    // Chrome populates the list asynchronously.
    const timeout = setTimeout(() => resolve(cachedVoices), 700)
    window.speechSynthesis.onvoiceschanged = () => {
      clearTimeout(timeout)
      cachedVoices = window.speechSynthesis.getVoices()
      resolve(cachedVoices)
    }
  })
}

function pickVoice(voices: SpeechSynthesisVoice[], language: string): SpeechSynthesisVoice | null {
  if (!voices.length) return null
  const prefix = language.split('-')[0]
  return (
    voices.find((v) => v.lang.toLowerCase().startsWith('en-in')) ??
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ??
    voices.find((v) => v.lang.toLowerCase().startsWith('en')) ??
    voices[0]
  )
}

/** Speak text with the browser's synthesiser. Resolves when playback finishes. */
export async function speak(
  text: string,
  options: { language?: string; rate?: number; onStart?: () => void } = {},
): Promise<void> {
  if (!isSynthesisSupported() || !text.trim()) return

  const { language = 'en-IN', rate = 1.02, onStart } = options
  try {
    window.speechSynthesis.cancel()
  } catch {
    /* ignore */
  }

  let voices: SpeechSynthesisVoice[] = []
  try {
    voices = await loadVoices()
  } catch {
    /* ignore */
  }
  const voice = pickVoice(voices, language)

  return new Promise((resolve) => {
    let resolved = false
    const done = () => {
      if (!resolved) {
        resolved = true
        clearInterval(resumeInterval)
        clearTimeout(maxTimeout)
        resolve()
      }
    }

    // Safety timeout based on words to prevent Chrome from hanging if onend never fires
    const wordCount = text.trim().split(/\s+/).length
    const expectedDurationMs = Math.min(15000, Math.max(2500, wordCount * 500))
    const maxTimeout = setTimeout(done, expectedDurationMs)

    // Chrome bug workaround: keep synthesis active and detect completion
    const resumeInterval = setInterval(() => {
      try {
        if (!window.speechSynthesis.speaking) {
          done()
        } else {
          window.speechSynthesis.resume()
        }
      } catch {
        done()
      }
    }, 400)

    try {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = language
      utterance.rate = rate
      utterance.pitch = 1
      if (voice) utterance.voice = voice
      utterance.onstart = () => onStart?.()
      utterance.onend = done
      utterance.onerror = done
      window.speechSynthesis.speak(utterance)
    } catch {
      done()
    }
  })
}

export function stopSpeaking(): void {
  if (isSynthesisSupported()) window.speechSynthesis.cancel()
}

/** Play base64 audio returned by a server-side TTS provider. */
export function playBase64Audio(base64: string, mimeType = 'audio/wav'): Promise<void> {
  return new Promise((resolve) => {
    if (!base64) {
      resolve()
      return
    }
    const audio = new Audio(`data:${mimeType};base64,${base64}`)
    audio.onended = () => resolve()
    audio.onerror = () => resolve()
    void audio.play().catch(() => resolve())
  })
}

/** Strip markdown so the synthesiser doesn't read punctuation aloud. */
export function toSpeakable(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '')
    .replace(/₹/g, ' rupees ')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, '. ')
    .trim()
}
