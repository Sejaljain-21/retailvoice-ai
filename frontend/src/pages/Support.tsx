import { BookOpen, Headphones, Mic, Package, RotateCcw, Truck, Wallet } from 'lucide-react'

import { ChatPanel } from '@/components/chat/ChatPanel'
import { Button, Card } from '@/components/ui'
import { useChat } from '@/store/chat'

const QUICK_TOPICS = [
  { icon: Truck, label: 'Track my order', prompt: 'Where is my order?' },
  { icon: RotateCcw, label: 'Return an item', prompt: 'I want to return an item I received.' },
  { icon: Package, label: 'Cancel an order', prompt: 'I want to cancel my order.' },
  { icon: Wallet, label: 'Refund status', prompt: 'How long does a refund take on UPI?' },
  { icon: BookOpen, label: 'Delivery charges', prompt: 'What are your delivery charges?' },
]

export function Support() {
  const { send, stage, setVoiceCallOpen } = useChat()

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-5 px-4 py-6 lg:flex-row lg:px-8">
      <div className="min-h-[540px] flex-1 lg:min-h-0">
        <ChatPanel />
      </div>

      <aside className="w-full shrink-0 space-y-4 lg:w-72">
        <Card className="border-brand-200 bg-gradient-to-br from-brand-50 via-white to-violet-50 p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-brand-600 text-white shadow-md">
              <Mic className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-ink-900">Voice Call with Aura</h2>
              <p className="text-[11px] text-ink-500">Speak live over microphone</p>
            </div>
          </div>
          <Button
            className="mt-3.5 w-full gap-2 bg-brand-600 hover:bg-brand-700 shadow-sm"
            onClick={() => setVoiceCallOpen(true)}
          >
            <Headphones className="h-4 w-4" />
            Start Voice Call
          </Button>
        </Card>

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

      </aside>
    </div>
  )
}
