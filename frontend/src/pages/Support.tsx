import { BookOpen, Package, RotateCcw, Truck, Wallet } from 'lucide-react'

import { ChatPanel } from '@/components/chat/ChatPanel'
import { Card } from '@/components/ui'
import { useChat } from '@/store/chat'

const QUICK_TOPICS = [
  { icon: Truck, label: 'Track my order', prompt: 'Where is my order?' },
  { icon: RotateCcw, label: 'Return an item', prompt: 'I want to return an item I received.' },
  { icon: Package, label: 'Cancel an order', prompt: 'I want to cancel my order.' },
  { icon: Wallet, label: 'Refund status', prompt: 'How long does a refund take on UPI?' },
  { icon: BookOpen, label: 'Delivery charges', prompt: 'What are your delivery charges?' },
]

export function Support() {
  const { send, stage } = useChat()

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-5 px-4 py-6 lg:flex-row lg:px-8">
      <div className="min-h-[540px] flex-1 lg:min-h-0">
        <ChatPanel />
      </div>

      <aside className="w-full shrink-0 space-y-4 lg:w-72">
        <Card className="p-4">
          <h2 className="text-sm font-semibold text-ink-900">Common requests</h2>
          <p className="mt-0.5 text-xs text-ink-500">One tap to get started.</p>
          <div className="mt-3 space-y-1.5">
            {QUICK_TOPICS.map(({ icon: Icon, label, prompt }) => (
              <button
                key={label}
                disabled={stage !== 'idle'}
                onClick={() => void send(prompt)}
                className="flex w-full items-center gap-2.5 rounded-lg border border-ink-200 px-3 py-2 text-left text-sm text-ink-700 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-800 disabled:opacity-50"
              >
                <Icon className="h-4 w-4 shrink-0 text-ink-400" />
                {label}
              </button>
            ))}
          </div>
        </Card>

        <Card className="p-4">
          <h2 className="text-sm font-semibold text-ink-900">How Aura answers</h2>
          <ul className="mt-3 space-y-2.5 text-xs leading-relaxed text-ink-600">
            <li>
              <span className="font-semibold text-ink-800">Grounded.</span> Order status,
              stock and prices come from a live lookup, never from memory.
            </li>
            <li>
              <span className="font-semibold text-ink-800">Cited.</span> Policy answers link
              back to the help-centre article they came from.
            </li>
            <li>
              <span className="font-semibold text-ink-800">Private.</span> Emails, phone
              numbers and card numbers are masked before anything is stored.
            </li>
            <li>
              <span className="font-semibold text-ink-800">Escalating.</span> Ask for a
              person at any time — a human gets the full transcript.
            </li>
          </ul>
        </Card>

        <Card className="bg-ink-900 p-4">
          <h2 className="text-sm font-semibold text-white">Prefer to talk?</h2>
          <p className="mt-1 text-xs leading-relaxed text-ink-300">
            Use the microphone in the chat header to start a live voice call. Aura listens,
            answers out loud, and you can interrupt at any point.
          </p>
        </Card>
      </aside>
    </div>
  )
}
