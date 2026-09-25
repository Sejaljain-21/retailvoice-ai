import {
  BarChart3, BookOpen, Bot, ChevronDown, Headphones, LifeBuoy, LogOut, Mail, MessageSquare, MessagesSquare,
  Menu, Mic, Package, Phone, Radio, Sparkles, Store, Ticket, UserPlus, X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { ChatPanel } from '@/components/chat/ChatPanel'
import { VoiceCall } from '@/components/chat/VoiceCall'

import { Badge, Button } from '@/components/ui'
import { api } from '@/lib/api'
import type { Capabilities } from '@/lib/types'
import { cn, initials, titleCase } from '@/lib/utils'
import { isStaff, useAuth } from '@/store/auth'
import { useChat } from '@/store/chat'

interface NavItem {
  to: string
  label: string
  icon: typeof Store
  staffOnly?: boolean
  authOnly?: boolean
}

const AGENT_NAV: NavItem[] = [
  { to: '/', label: 'Voice & Support Studio', icon: Mic },
  { to: '/store', label: 'Retail Sandbox (Catalog)', icon: Store },
  { to: '/orders', label: 'My Orders & Returns', icon: Package, authOnly: true },
  { to: '/help', label: 'Knowledge & Policies', icon: BookOpen },
]

const CONSOLE_NAV: NavItem[] = [
  { to: '/console/conversations', label: 'Omnichannel Logs', icon: MessagesSquare, staffOnly: true },
  { to: '/console/tickets', label: 'Supervisor Tickets', icon: Ticket, staffOnly: true },
  { to: '/console/knowledge', label: 'Knowledge Base & FAQ', icon: BookOpen, staffOnly: true },
  { to: '/console/analytics', label: 'Support Analytics', icon: BarChart3, staffOnly: true },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [menu, setMenu] = useState(false)
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const { voiceCallOpen, setVoiceCallOpen } = useChat()

  useEffect(() => {
    api.capabilities().then(setCapabilities).catch(() => setCapabilities(null))
  }, [])

  useEffect(() => setOpen(false), [location.pathname])

  const staff = isStaff(user)

  const renderNav = (items: NavItem[]) =>
    items
      .filter((item) => (!item.staffOnly || staff) && (!item.authOnly || user))
      .map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
              isActive
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-ink-300 hover:bg-ink-800 hover:text-white',
            )
          }
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </NavLink>
      ))

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-ink-900 transition-transform lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center gap-3 px-5 py-5 border-b border-ink-800">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-brand-600 to-violet-500 text-white shadow-md">
            <Bot className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-white tracking-wide">Retail Voice</p>
            <p className="truncate text-[11px] font-medium text-brand-300 flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              AI Voice & Support Agent
            </p>
          </div>
          <button
            className="ml-auto text-ink-400 lg:hidden"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto scroll-thin px-3 py-4">
          <div className="space-y-1">
            <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
              AI Voice & Support
            </p>
            {renderNav(AGENT_NAV)}
          </div>

          {staff && (
            <div className="space-y-1">
              <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                Supervisor Console
              </p>
              {renderNav(CONSOLE_NAV)}
            </div>
          )}
        </nav>


        <div className="border-t border-ink-800 p-3">
          {user ? (
            <div className="relative">
              <button
                onClick={() => setMenu((v) => !v)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left transition hover:bg-ink-800"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-500 text-xs font-bold text-white">
                  {initials(user.full_name)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-white">
                    {user.full_name}
                  </span>
                  <span className="block truncate text-[11px] text-ink-400">
                    {titleCase(user.role)}
                    {user.profile && ` · ${titleCase(user.profile.tier)}`}
                  </span>
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-ink-400" />
              </button>

              {menu && (
                <div className="absolute bottom-full left-0 mb-1 w-full overflow-hidden rounded-xl border border-ink-700 bg-ink-900/95 backdrop-blur-md shadow-2xl p-1.5 space-y-1">
                  <div className="px-2.5 py-1.5 border-b border-ink-800 text-[11px] space-y-1">
                    <div className="flex items-center gap-1.5 text-ink-300 truncate">
                      <Mail className="h-3 w-3 text-ink-400 shrink-0" />
                      <span className="truncate">{user.email}</span>
                    </div>
                    {user.phone && (
                      <div className="flex items-center gap-1.5 text-ink-300 font-mono">
                        <Phone className="h-3 w-3 text-ink-400 shrink-0" />
                        <span>{user.phone}</span>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      logout()
                      setMenu(false)
                      navigate('/login')
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-medium text-brand-300 transition hover:bg-ink-800"
                  >
                    <UserPlus className="h-3.5 w-3.5 text-brand-400" />
                    Switch / Create New Profile
                  </button>
                  <button
                    onClick={() => {
                      logout()
                      setMenu(false)
                      navigate('/')
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-medium text-red-300 transition hover:bg-ink-800"
                  >
                    <LogOut className="h-3.5 w-3.5 text-red-400" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Button className="w-full" onClick={() => navigate('/login')}>
              Sign in
            </Button>
          )}
        </div>
      </aside>

      {open && (
        <div
          className="fixed inset-0 z-30 bg-ink-950/40 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden
        />
      )}

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Unified Top Platform Header Bar */}
        <header className="flex h-16 items-center justify-between border-b border-ink-200/80 bg-white/90 px-4 sm:px-6 backdrop-blur-md sticky top-0 z-20 shadow-xs">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
              className="rounded-lg p-1.5 text-ink-600 hover:bg-ink-100 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600 lg:hidden">
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm sm:text-base font-bold text-ink-900 tracking-tight">
                    {location.pathname === '/'
                      ? 'AI Voice & Support Studio'
                      : location.pathname === '/store'
                        ? 'Retail Sandbox & Catalog'
                        : location.pathname.startsWith('/console')
                          ? 'Supervisor Console'
                          : location.pathname === '/orders'
                            ? 'Customer Orders & Returns'
                            : 'Retail Voice'}
                  </h1>
                  <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-600/20">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Aura Live
                  </span>
                </div>
                <p className="hidden md:block text-[11px] text-ink-500">
                  Instant Voice & Chat Assistance · Real-Time Order & Return Resolution
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {capabilities?.llm.provider === 'mock' && (
              <Badge className="bg-amber-100 text-amber-700 ring-amber-600/20">
                offline mode
              </Badge>
            )}

            {/* Quick 1-Click Voice Call Button in Header */}
            <button
              onClick={() => setVoiceCallOpen(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:from-brand-700 hover:to-violet-700 active:scale-95"
            >
              <Headphones className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Start Voice Session</span>
              <span className="sm:hidden">Voice Call</span>
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto scroll-thin bg-ink-50">
          <Outlet />
        </main>
      </div>

      {/* Global Voice Call Modal */}
      <VoiceCall open={voiceCallOpen} onClose={() => setVoiceCallOpen(false)} />

      {/* Floating Audio & Chat Action Bar (available on sandbox and console pages) */}
      {location.pathname !== '/' && (
        <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-3">
          {chatOpen && (
            <div className="h-[560px] w-[380px] max-w-[calc(100vw-2.5rem)] animate-fade-up overflow-hidden rounded-xl border border-ink-200 bg-white shadow-2xl">
              <ChatPanel variant="widget" />
            </div>
          )}

          <div className="flex items-center gap-2.5">
            {/* Direct Floating Voice Call Button */}
            <button
              onClick={() => setVoiceCallOpen(true)}
              className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-600 text-white shadow-xl transition-all duration-200 hover:scale-105 hover:bg-brand-700 active:scale-95"
              aria-label="Start voice call with Aura"
              title="Voice call with Aura"
            >
              <Mic className="h-5 w-5" />
            </button>

            {/* Floating Chat Toggle Button */}
            <button
              onClick={() => setChatOpen((v) => !v)}
              className={cn(
                'flex h-12 w-12 items-center justify-center rounded-full text-white shadow-xl transition-all duration-200 hover:scale-105 active:scale-95',
                chatOpen ? 'bg-ink-800 hover:bg-ink-900' : 'bg-brand-600 hover:bg-brand-700',
              )}
              aria-label={chatOpen ? 'Close support chat' : 'Open support chat'}
              title={chatOpen ? 'Close chat' : 'Chat with Aura'}
            >
              {chatOpen ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function PageHeader({
  title, description, action,
}: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-bold text-ink-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}
