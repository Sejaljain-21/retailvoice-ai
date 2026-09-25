import { Bot, ShieldCheck, Sparkles, Waves } from 'lucide-react'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button, Card, Field, Input } from '@/components/ui'
import { isStaff, useAuth } from '@/store/auth'

const DEMO_ACCOUNTS = [
  { label: 'Customer', email: 'customer@retailvoice.ai', password: 'Demo@1234',
    note: 'Gold tier, live orders' },
  { label: 'Support agent', email: 'agent1@retailvoice.ai', password: 'Demo@1234',
    note: 'Queue + tickets' },
  { label: 'Admin', email: 'admin@retailvoice.ai', password: 'Admin@123',
    note: 'Analytics + knowledge base' },
]

export function Login() {
  const { login, register, loading, error } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from

  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('customer@retailvoice.ai')
  const [password, setPassword] = useState('Demo@1234')
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setLocalError(null)

    if (mode === 'signup') {
      const cleanPhone = phone.trim()
      const digits = cleanPhone.replace(/\D/g, '')
      if (digits.length < 10 || digits.length > 15) {
        setLocalError('Please enter a valid mobile number with at least 10 digits (e.g. +91 98765 43210).')
        return
      }
    }

    try {
      const user =
        mode === 'signin'
          ? await login(email, password)
          : await register({ email, password, full_name: fullName, phone: phone.trim() || undefined })
      navigate(from ?? (isStaff(user) ? '/console/conversations' : '/'), { replace: true })
    } catch {
      /* the store already holds the message */
    }
  }

  function useDemo(account: (typeof DEMO_ACCOUNTS)[number]) {
    setMode('signin')
    setEmail(account.email)
    setPassword(account.password)
    setLocalError(null)
  }

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-ink-900 p-10 lg:flex">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-brand-600/20 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-brand-500/10 blur-3xl" />

        <div className="relative flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Bot className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold text-white">Retail Voice</span>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-3xl font-bold leading-tight text-white">
            An AI support agent that actually knows your orders.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-ink-300">
            Intelligent voice and chat support for retail. Every answer about an order,
            delivery, or policy is verified in real time against live store records.
          </p>

          <ul className="mt-8 space-y-4">
            {[
              { icon: Waves, title: 'Realtime voice',
                body: 'Streaming speech in, spoken answers out, with barge-in.' },
              { icon: Sparkles, title: 'Grounded answers',
                body: '13 tools over the live catalogue, orders and help centre.' },
              { icon: ShieldCheck, title: 'Guardrails',
                body: 'PII redaction, injection defence and rules-based escalation.' },
            ].map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-3">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-brand-400" />
                <div>
                  <p className="text-sm font-semibold text-white">{title}</p>
                  <p className="text-xs text-ink-400">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-ink-500">
          © {new Date().getFullYear()} NovaMart Retail · Customer Support &amp; Voice Assistance
        </p>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center bg-ink-50 p-6">
        <div className="w-full max-w-sm">
          <div className="mb-6 lg:hidden">
            <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Bot className="h-5 w-5" />
            </div>
            <h1 className="text-xl font-bold text-ink-900">Retail Voice</h1>
          </div>

          <Card className="p-6">
            <h2 className="text-lg font-bold text-ink-900">
              {mode === 'signin' ? 'Welcome back' : 'Create an account'}
            </h2>
            <p className="mt-1 text-sm text-ink-500">
              {mode === 'signin'
                ? 'Sign in to see your orders and talk to Aura.'
                : 'It takes a few seconds.'}
            </p>

            <form onSubmit={submit} className="mt-5 space-y-4">
              {mode === 'signup' && (
                <>
                  <Field label="Full name">
                    <Input
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="e.g. Priyanshu Sharma"
                      required
                      minLength={2}
                    />
                  </Field>
                  <Field label="Mobile Phone Number" hint="Used for SMS & OTP security verification">
                    <Input
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="+91 98765 43210"
                      required
                    />
                  </Field>
                </>
              )}

              <Field label="Email">
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="username"
                />
              </Field>

              <Field
                label="Password"
                hint={mode === 'signup' ? 'At least 8 characters.' : undefined}
              >
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={mode === 'signup' ? 8 : 1}
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                />
              </Field>

              {(error || localError) && (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {localError ?? error}
                </p>
              )}

              <Button type="submit" className="w-full" loading={loading}>
                {mode === 'signin' ? 'Sign in' : 'Create account'}
              </Button>
            </form>

            <button
              onClick={() => {
                setMode(mode === 'signin' ? 'signup' : 'signin')
                setLocalError(null)
              }}
              className="mt-4 w-full text-center text-sm text-ink-500 transition hover:text-brand-700"
            >
              {mode === 'signin'
                ? "Don't have an account? Sign up"
                : 'Already registered? Sign in'}
            </button>
          </Card>

          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Demo accounts
            </p>
            <div className="space-y-1.5">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  onClick={() => useDemo(account)}
                  className="flex w-full items-center justify-between gap-3 rounded-lg border border-ink-200 bg-white px-3 py-2 text-left transition hover:border-brand-300 hover:bg-brand-50"
                >
                  <span className="min-w-0">
                    <span className="block text-xs font-semibold text-ink-800">
                      {account.label}
                    </span>
                    <span className="block truncate text-[11px] text-ink-500">
                      {account.email}
                    </span>
                  </span>
                  <span className="shrink-0 text-[11px] text-ink-400">{account.note}</span>
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={() => navigate('/')}
            className="mt-4 w-full text-center text-sm text-ink-500 transition hover:text-brand-700"
          >
            Continue as a guest
          </button>
        </div>
      </div>
    </div>
  )
}
