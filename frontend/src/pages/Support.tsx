import {
  ArrowRight, Bot, ChevronRight, Clock,
  Headphones,
  Mic, Package, Play, RotateCcw, ShieldCheck, Sparkles,
  Store, Tag, Truck, UserCheck, UserCog, Volume2, Wrench, Zap,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { ChatPanel } from '@/components/chat/ChatPanel'
import { Badge, Button, Card } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useChat } from '@/store/chat'

interface DemoScenario {
  id: string
  title: string
  emoji: string
  reference: string
  prompt: string
  icon: typeof Truck
  badge: string
  accentColor: 'emerald' | 'violet' | 'amber' | 'cyan' | 'rose'
  reasoningSteps: string[]
  description: string
}

const EVALUATION_SCENARIOS: DemoScenario[] = [
  {
    id: 'track',
    title: 'Live Order Tracking',
    emoji: '📦',
    reference: 'ORD-2609-941316',
    prompt: 'Where is my order ORD-2609-941316?',
    icon: Truck,
    badge: 'Live Courier Telemetry',
    accentColor: 'emerald',
    description: 'Instant parcel milestone verification, live transit status, and courier ETA projection.',
    reasoningSteps: [
      'Ingest & Validate Tracking ID (ORD-2609-941316)',
      'Cross-check Real-Time Courier Milestones & GPS',
      'Compute Delivery SLA & Expected Delivery Date',
    ],
  },
  {
    id: 'return',
    title: 'Autonomous Voice Return & Refund',
    emoji: '🔄',
    reference: 'Noise-Cancelling Headphones',
    prompt: 'I received the Smart Noise-Cancelling Headphones yesterday and want to initiate a return.',
    icon: RotateCcw,
    badge: 'Autonomous Return Engine',
    accentColor: 'violet',
    description: 'Autonomous 7-day eligibility check, policy verification, and instant return scheduling.',
    reasoningSteps: [
      'Locate Recent Purchase in Order History',
      'Verify 7-Day Hassle-Free Return Policy Eligibility',
      'Generate RMA Return Tag & Schedule Courier Pickup',
    ],
  },
  {
    id: 'specs',
    title: 'Product Availability & Specs Inquiry',
    emoji: '⚡',
    reference: 'Inventory & Audio Specs',
    prompt: 'Do you have the Smart Noise Cancelling Headphones in stock and what are the main specs?',
    icon: Zap,
    badge: 'Real-Time Catalog Verification',
    accentColor: 'amber',
    description: 'Instant warehouse stock lookup, ANC battery specifications, and warranty details.',
    reasoningSteps: [
      'Query Warehouse Live Inventory Count',
      'Extract Verified Hardware & Acoustic Specifications',
      'Estimate Pincode-Specific Standard Delivery Window',
    ],
  },
  {
    id: 'sla',
    title: 'Refund & Delivery SLA Policy Inquiry',
    emoji: '🛡️',
    reference: 'UPI & Card SLA Timelines',
    prompt: 'How long does a refund take if I paid through UPI or Card?',
    icon: ShieldCheck,
    badge: 'Policy Knowledge Grounding',
    accentColor: 'cyan',
    description: 'Accurate policy citation for UPI (24-48h) and credit/debit card (3-5 business days).',
    reasoningSteps: [
      'Scan Store Policy & SLA Customer Agreement',
      'Differentiate Payment Gateway Processing Windows',
      'Provide Exact Refund Milestones & Bank SLA Timelines',
    ],
  },
  {
    id: 'escalate',
    title: 'Automated Human Supervisor Escalation',
    emoji: '🧑‍💼',
    reference: 'Critical Sentiment Queue',
    prompt: 'I am extremely frustrated with this delay, connect me to a human supervisor immediately.',
    icon: UserCog,
    badge: 'Intelligent Sentiment Handoff',
    accentColor: 'rose',
    description: 'Immediate sentiment detection, high-priority ticket generation, and supervisor routing.',
    reasoningSteps: [
      'Detect Negative Customer Sentiment & Escalation Trigger',
      'Generate Priority Escalation Ticket & Session Summary',
      'Route Active Session to Human Supervisor Support Desk',
    ],
  },
]

const ACCENT_STYLES = {
  emerald: {
    cardBg: 'from-slate-900/95 via-slate-900/90 to-emerald-950/40',
    border: 'border-emerald-500/30 hover:border-emerald-400/80',
    glow: 'hover:shadow-[0_0_30px_rgba(16,185,129,0.25)]',
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    iconBg: 'bg-emerald-500/20 text-emerald-400 group-hover:bg-emerald-500 group-hover:text-slate-950',
    stepDot: 'bg-emerald-400',
    button: 'from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20',
  },
  violet: {
    cardBg: 'from-slate-900/95 via-slate-900/90 to-violet-950/40',
    border: 'border-violet-500/30 hover:border-violet-400/80',
    glow: 'hover:shadow-[0_0_30px_rgba(139,92,246,0.25)]',
    badge: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    iconBg: 'bg-violet-500/20 text-violet-400 group-hover:bg-violet-500 group-hover:text-white',
    stepDot: 'bg-violet-400',
    button: 'from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 shadow-violet-500/20',
  },
  amber: {
    cardBg: 'from-slate-900/95 via-slate-900/90 to-amber-950/40',
    border: 'border-amber-500/30 hover:border-amber-400/80',
    glow: 'hover:shadow-[0_0_30px_rgba(245,158,11,0.25)]',
    badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    iconBg: 'bg-amber-500/20 text-amber-400 group-hover:bg-amber-500 group-hover:text-slate-950',
    stepDot: 'bg-amber-400',
    button: 'from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 shadow-amber-500/20',
  },
  cyan: {
    cardBg: 'from-slate-900/95 via-slate-900/90 to-cyan-950/40',
    border: 'border-cyan-500/30 hover:border-cyan-400/80',
    glow: 'hover:shadow-[0_0_30px_rgba(6,182,212,0.25)]',
    badge: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    iconBg: 'bg-cyan-500/20 text-cyan-400 group-hover:bg-cyan-500 group-hover:text-slate-950',
    stepDot: 'bg-cyan-400',
    button: 'from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 shadow-cyan-500/20',
  },
  rose: {
    cardBg: 'from-slate-900/95 via-slate-900/90 to-rose-950/40',
    border: 'border-rose-500/30 hover:border-rose-400/80',
    glow: 'hover:shadow-[0_0_30px_rgba(244,63,94,0.25)]',
    badge: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    iconBg: 'bg-rose-500/20 text-rose-400 group-hover:bg-rose-500 group-hover:text-white',
    stepDot: 'bg-rose-400',
    button: 'from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 shadow-rose-500/20',
  },
}

export function Support() {
  const { send, stage, setVoiceCallOpen } = useChat()
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null)

  const busy = stage !== 'idle'

  const handleRunScenario = (scenario: DemoScenario) => {
    setSelectedScenario(scenario.id)
    void send(scenario.prompt)
    // Scroll smoothly to terminal
    const terminalElement = document.getElementById('aura-terminal-section')
    if (terminalElement) {
      terminalElement.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-8">
      {/* Platform Hero Banner - Luminous Dark/Light Hybrid Aesthetic */}
      <section className="relative overflow-hidden rounded-3xl border border-violet-500/30 bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 p-6 sm:p-8 lg:p-10 text-white shadow-[0_0_40px_rgba(99,102,241,0.2)]">
        {/* Luminous Glow Orbs */}
        <div className="absolute -right-20 -top-20 h-96 w-96 rounded-full bg-violet-600/25 blur-3xl pointer-events-none" />
        <div className="absolute -left-20 -bottom-20 h-80 w-80 rounded-full bg-indigo-600/20 blur-3xl pointer-events-none" />
        <div className="absolute right-1/3 top-1/2 h-64 w-64 rounded-full bg-purple-500/15 blur-2xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">
          <div className="max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-violet-400/40 bg-violet-500/15 px-3.5 py-1 text-xs font-semibold text-violet-200 backdrop-blur-md shadow-xs">
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <Sparkles className="h-3.5 w-3.5 text-violet-300" />
              <span>Next-Gen Autonomous AI Voice & Customer Support Engine</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-[1.15]">
              Real-Time Voice Support <br className="hidden sm:inline" />
              <span className="bg-gradient-to-r from-violet-300 via-indigo-200 to-purple-400 bg-clip-text text-transparent">
                & Autonomous Agent Terminal
              </span>
            </h1>

            <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl">
              Meet <strong className="text-white font-semibold">Aura</strong> — your enterprise customer support agent capable of natural, hands-free voice dialogue, autonomous order tracking, instant policy returns, and seamless supervisor handoffs.
            </p>

            {/* Performance & Quality Metrics Ribbon */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-md transition hover:border-violet-400/30">
                <p className="text-[11px] font-semibold text-violet-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Clock className="h-3 w-3 text-amber-400" /> Response Time
                </p>
                <p className="mt-1 text-lg font-bold text-white">&lt; 1.2s</p>
                <p className="text-[10px] text-slate-400">Real-time voice & chat</p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-md transition hover:border-violet-400/30">
                <p className="text-[11px] font-semibold text-violet-300 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="h-3 w-3 text-emerald-400" /> Availability
                </p>
                <p className="mt-1 text-lg font-bold text-white">24/7 Active</p>
                <p className="text-[10px] text-slate-400">Always on & ready</p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-md transition hover:border-violet-400/30">
                <p className="text-[11px] font-semibold text-violet-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Zap className="h-3 w-3 text-violet-400" /> Autonomous
                </p>
                <p className="mt-1 text-lg font-bold text-white">Full Actions</p>
                <p className="text-[10px] text-slate-400">Orders, returns & specs</p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-md transition hover:border-violet-400/30">
                <p className="text-[11px] font-semibold text-violet-300 uppercase tracking-wider flex items-center gap-1.5">
                  <UserCheck className="h-3 w-3 text-cyan-400" /> Resolution
                </p>
                <p className="mt-1 text-lg font-bold text-white">94.2% FCR</p>
                <p className="text-[10px] text-slate-400">First-contact resolution rate</p>
              </div>
            </div>
          </div>

          {/* Voice Studio Launch Card with Animated Frequency Bars */}
          <div className="flex flex-col gap-3 shrink-0 lg:w-80">
            <div className="relative overflow-hidden rounded-2xl border border-violet-500/40 bg-gradient-to-b from-violet-950/70 via-slate-900/90 to-indigo-950/80 p-5 backdrop-blur-xl shadow-[0_0_30px_rgba(139,92,246,0.3)] text-center flex flex-col items-center">
              {/* Luminous Audio Frequency Equalizer Display */}
              <div className="flex items-center justify-center gap-1 h-8 mb-3 px-2">
                {[0.25, 0.6, 0.9, 0.4, 1.0, 0.7, 0.35, 0.85, 0.5, 0.95, 0.45, 0.8, 0.3, 0.7, 0.2].map((factor, i) => (
                  <span
                    key={i}
                    className="w-1 rounded-full bg-gradient-to-t from-violet-500 to-indigo-300 animate-soundwave"
                    style={{
                      animationDelay: `${(i * 0.08).toFixed(2)}s`,
                      animationDuration: `${(0.65 + factor * 0.45).toFixed(2)}s`,
                    }}
                  />
                ))}
              </div>

              <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
                <Volume2 className="h-4 w-4 text-violet-400" />
                Live Voice Call Studio
              </h2>
              <p className="mt-1 text-xs text-slate-300 max-w-[240px]">
                Speak hands-free with Aura. Real-time autonomous reasoning with zero latency speech.
              </p>

              <button
                onClick={() => setVoiceCallOpen(true)}
                className="mt-4 flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-purple-600 py-3 px-4 text-xs font-bold text-white shadow-lg shadow-violet-500/30 transition-all duration-300 hover:scale-[1.02] hover:shadow-violet-500/40 active:scale-95 border border-violet-400/40"
              >
                <Headphones className="h-4 w-4" />
                Launch Live Voice Session
              </button>
            </div>

            <Link
              to="/store"
              className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-300 transition hover:bg-white/10 hover:text-white backdrop-blur-md"
            >
              <div className="flex items-center gap-2">
                <Store className="h-4 w-4 text-violet-400" />
                <span>Visit Retail Sandbox (Catalog)</span>
              </div>
              <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
            </Link>
          </div>
        </div>
      </section>

      {/* Dedicated Demo & Evaluation Suite */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-ink-200/80 pb-3">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-violet-300/80 bg-violet-100/70 px-3 py-0.5 text-xs font-bold text-violet-800">
              <Sparkles className="h-3 w-3 text-violet-600" />
              <span>Interactive Support Scenarios</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-extrabold text-ink-900 tracking-tight">
              Quick Voice &amp; Chat Actions
            </h2>
            <p className="text-xs sm:text-sm text-ink-500">
              Select any scenario card below to interact with Aura for instant voice assistance, order queries, and resolutions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs bg-ink-100 text-ink-700 border-ink-300">
              5 Popular Actions
            </Badge>
          </div>
        </div>

        {/* 5 Evaluation Scenario Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {EVALUATION_SCENARIOS.map((scenario) => {
            const Icon = scenario.icon
            const styling = ACCENT_STYLES[scenario.accentColor]
            const isSelected = selectedScenario === scenario.id

            return (
              <div
                key={scenario.id}
                className={cn(
                  'group relative flex flex-col justify-between rounded-2xl border p-4.5 transition-all duration-300 backdrop-blur-md',
                  'bg-gradient-to-b',
                  styling.cardBg,
                  styling.border,
                  styling.glow,
                  isSelected ? 'ring-2 ring-violet-500 shadow-lg' : 'shadow-md',
                )}
              >
                <div className="space-y-3">
                  {/* Top Bar: Icon + Badge */}
                  <div className="flex items-start justify-between gap-2">
                    <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl transition duration-200 shadow-sm', styling.iconBg)}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-md border text-right', styling.badge)}>
                      {scenario.badge}
                    </span>
                  </div>

                  {/* Title & Reference */}
                  <div>
                    <h3 className="text-sm font-bold text-white group-hover:text-violet-200 transition">
                      {scenario.emoji} {scenario.title}
                    </h3>
                    <p className="mt-0.5 text-[11px] font-mono font-medium text-slate-300">
                      {scenario.reference}
                    </p>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-slate-300 leading-snug line-clamp-2">
                    {scenario.description}
                  </p>

                  {/* Step-by-Step Agent Reasoning Badges */}
                  <div className="space-y-1.5 pt-2 border-t border-white/10">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1">
                      <Zap className="h-2.5 w-2.5 text-violet-400" /> Step-by-Step Reasoning
                    </p>
                    <div className="space-y-1 text-[10px]">
                      {scenario.reasoningSteps.map((step, idx) => (
                        <div key={idx} className="flex items-center gap-1.5 text-slate-300 font-medium">
                          <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', styling.stepDot)} />
                          <span className="truncate">{step}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Bottom Trigger Action */}
                <div className="pt-4 mt-3 border-t border-white/10 space-y-2">
                  <div className="rounded-lg bg-black/40 p-2 border border-white/5 text-[11px] text-slate-300 italic truncate font-mono">
                    "{scenario.prompt}"
                  </div>

                  <button
                    disabled={busy}
                    onClick={() => handleRunScenario(scenario)}
                    className={cn(
                      'flex w-full items-center justify-center gap-2 rounded-xl py-2 px-3 text-xs font-bold text-white shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-95 disabled:opacity-50',
                      'bg-gradient-to-r',
                      styling.button,
                    )}
                  >
                    <Play className="h-3 w-3 fill-current" />
                    <span>Run Evaluation</span>
                    <ArrowRight className="h-3 w-3 ml-auto opacity-70 group-hover:translate-x-0.5 transition-transform" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Main Support Terminal & Live Autonomous Execution Monitor */}
      <section id="aura-terminal-section" className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Interactive Chat & Voice Terminal (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col h-[740px] rounded-2xl border border-ink-200 bg-white shadow-lg overflow-hidden">
          {/* Header Bar */}
          <div className="flex items-center justify-between border-b border-ink-200/80 bg-ink-50/70 px-5 py-3.5">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-violet-600 text-white shadow-md shadow-brand-500/20">
                  <Bot className="h-5 w-5" />
                </div>
                <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500 animate-pulse" />
              </div>
              <div>
                <p className="text-xs font-bold text-ink-900 flex items-center gap-1.5">
                  Aura Customer Support Terminal
                  <Badge variant="outline" className="text-[10px] py-0 px-1.5 bg-emerald-50 text-emerald-700 border-emerald-200">
                    Live
                  </Badge>
                </p>
                <p className="text-[11px] text-ink-500">Autonomous multi-step actions & voice assistance</p>
              </div>
            </div>

            <Button
              size="sm"
              variant="outline"
              onClick={() => setVoiceCallOpen(true)}
              className="gap-1.5 text-xs text-brand-700 border-brand-300 hover:bg-brand-50 shadow-2xs"
            >
              <Mic className="h-3.5 w-3.5 text-brand-600" />
              <span>Voice Studio</span>
            </Button>
          </div>

          <div className="flex-1 min-h-0">
            <ChatPanel variant="page" className="border-0 rounded-none h-full" />
          </div>
        </div>

        {/* Right Column: Live Autonomous Workflow & Execution Telemetry (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Live Autonomous Reasoning Card */}
          <Card className="p-5 border-violet-200/80 bg-gradient-to-br from-white via-violet-50/20 to-brand-50/30 shadow-md space-y-4">
            <div className="flex items-center justify-between border-b border-violet-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600 text-white shadow-xs">
                  <Wrench className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-ink-900">
                    Autonomous Tool Execution Engine
                  </h3>
                  <p className="text-[10px] text-ink-500">Step-by-step verified system grounding</p>
                </div>
              </div>
              <span className="flex items-center gap-1 text-[10px] font-semibold text-violet-700 bg-violet-100/70 px-2 py-0.5 rounded-full">
                <span className="h-1.5 w-1.5 rounded-full bg-violet-600 animate-pulse" />
                Ready
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-ink-200/80 shadow-2xs">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-500 text-white text-xs font-bold">
                  1
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-ink-900">Intent & Sentiment Ingestion</p>
                  <p className="text-[11px] text-ink-500 mt-0.5">
                    Parses customer requests, tracks sentiment urgency, and extracts key identifiers (order numbers, items).
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-ink-200/80 shadow-2xs">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-violet-600 text-white text-xs font-bold">
                  2
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-ink-900">Autonomous Database Execution</p>
                  <p className="text-[11px] text-ink-500 mt-0.5">
                    Directly queries order databases, courier tracking endpoints, warehouse stock, and store SLA policies.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-xl bg-white border border-ink-200/80 shadow-2xs">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white text-xs font-bold">
                  3
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-ink-900">Resolution or Supervisor Handoff</p>
                  <p className="text-[11px] text-ink-500 mt-0.5">
                    Synthesizes conversational spoken and text replies, or automatically escalates to a human agent.
                  </p>
                </div>
              </div>
            </div>
          </Card>

          {/* Key Enterprise Services Overview */}
          <Card className="p-4 space-y-3">
            <h3 className="text-xs font-bold text-ink-900 flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-violet-600" />
              Autonomous Capabilities Supported
            </h3>

            <div className="grid grid-cols-2 gap-2.5 text-xs">
              <div className="p-3 rounded-xl bg-ink-50 border border-ink-200/70">
                <p className="font-bold text-ink-900 flex items-center gap-1.5">
                  <Package className="h-3.5 w-3.5 text-emerald-600" />
                  Live Order Tracking
                </p>
                <p className="mt-1 text-[11px] text-ink-500">Real-time GPS parcel and courier milestones.</p>
              </div>

              <div className="p-3 rounded-xl bg-ink-50 border border-ink-200/70">
                <p className="font-bold text-ink-900 flex items-center gap-1.5">
                  <RotateCcw className="h-3.5 w-3.5 text-violet-600" />
                  Voice Returns
                </p>
                <p className="mt-1 text-[11px] text-ink-500">7-day policy validation & automated RMA labels.</p>
              </div>

              <div className="p-3 rounded-xl bg-ink-50 border border-ink-200/70">
                <p className="font-bold text-ink-900 flex items-center gap-1.5">
                  <Tag className="h-3.5 w-3.5 text-amber-600" />
                  Stock & Specs
                </p>
                <p className="mt-1 text-[11px] text-ink-500">Live inventory counts and audio device specs.</p>
              </div>

              <div className="p-3 rounded-xl bg-ink-50 border border-ink-200/70">
                <p className="font-bold text-ink-900 flex items-center gap-1.5">
                  <UserCog className="h-3.5 w-3.5 text-rose-600" />
                  Supervisor Handoff
                </p>
                <p className="mt-1 text-[11px] text-ink-500">Instant transfer to human support supervisors.</p>
              </div>
            </div>
          </Card>

          {/* Retail Sandbox Quick Access */}
          <Card className="p-4 border-indigo-200/80 bg-gradient-to-r from-indigo-50/50 via-violet-50/30 to-white shadow-xs">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-0.5">
                <p className="text-xs font-bold text-ink-900 flex items-center gap-1.5">
                  <Store className="h-4 w-4 text-indigo-600" />
                  Retail Sandbox & Catalog
                </p>
                <p className="text-[11px] text-ink-500">
                  Simulate new purchases to test Aura's tracking and returns live.
                </p>
              </div>
              <Link
                to="/store"
                className="shrink-0 inline-flex items-center gap-1 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 transition"
              >
                <span>Sandbox</span>
                <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </Card>
        </div>
      </section>
    </div>
  )
}
