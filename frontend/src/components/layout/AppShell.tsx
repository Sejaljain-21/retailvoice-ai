import {
  BarChart3, BookOpen, Bot, ChevronDown, LifeBuoy, LogOut, MessagesSquare,
  Menu, Package, Store, Ticket, X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { Badge, Button } from '@/components/ui'
import { api } from '@/lib/api'
import type { Capabilities } from '@/lib/types'
import { cn, initials, titleCase } from '@/lib/utils'
import { isStaff, useAuth } from '@/store/auth'

interface NavItem {
  to: string
  label: string
  icon: typeof Store
  staffOnly?: boolean
  authOnly?: boolean
}

const SHOP_NAV: NavItem[] = [
  { to: '/', label: 'Storefront', icon: Store },
  { to: '/support', label: 'Get support', icon: LifeBuoy },
  { to: '/orders', label: 'My orders', icon: Package, authOnly: true },
  { to: '/help', label: 'Help centre', icon: BookOpen },
]

const CONSOLE_NAV: NavItem[] = [
  { to: '/console/conversations', label: 'Conversations', icon: MessagesSquare, staffOnly: true },
  { to: '/console/tickets', label: 'Tickets', icon: Ticket, staffOnly: true },
  { to: '/console/knowledge', label: 'Knowledge base', icon: BookOpen, staffOnly: true },
  { to: '/console/analytics', label: 'Analytics', icon: BarChart3, staffOnly: true },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [menu, setMenu] = useState(false)
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)

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
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Bot className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-white">RetailVoice AI</p>
            <p className="truncate text-[11px] text-ink-400">NovaMart support</p>
          </div>
          <button
            className="ml-auto text-ink-400 lg:hidden"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto scroll-thin px-3 pb-4">
          <div className="space-y-1">
            <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-500">
              Shop
            </p>
            {renderNav(SHOP_NAV)}
          </div>

          {staff && (
            <div className="space-y-1">
              <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-500">
                Agent console
              </p>
              {renderNav(CONSOLE_NAV)}
            </div>
          )}
        </nav>

        {/* Runtime badge - shows which providers this deployment is using */}
        {capabilities && (
          <div className="mx-3 mb-3 rounded-lg bg-ink-800 px-3 py-2.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-500">
              Runtime
            </p>
            <dl className="mt-1.5 space-y-1 text-[11px] text-ink-300">
              <div className="flex justify-between gap-2">
                <dt className="text-ink-500">LLM</dt>
                <dd className="truncate font-medium">{capabilities.llm.provider}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-500">Speech</dt>
                <dd className="truncate font-medium">
                  {capabilities.speech.stt_provider} / {capabilities.speech.tts_provider}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-500">Tools</dt>
                <dd className="font-medium">{capabilities.tools.length}</dd>
              </div>
            </dl>
          </div>
        )}

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
                <div className="absolute bottom-full left-0 mb-1 w-full overflow-hidden rounded-lg border border-ink-700 bg-ink-800 shadow-xl">
                  <button
                    onClick={() => {
                      logout()
                      setMenu(false)
                      navigate('/')
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2.5 text-sm text-ink-200 transition hover:bg-ink-700"
                  >
                    <LogOut className="h-4 w-4" />
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

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-3 border-b border-ink-200 bg-white px-4 lg:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open navigation">
            <Menu className="h-5 w-5 text-ink-600" />
          </button>
          <span className="text-sm font-semibold text-ink-900">RetailVoice AI</span>
          {capabilities?.llm.provider === 'mock' && (
            <Badge className="ml-auto bg-amber-100 text-amber-700 ring-amber-600/20">
              offline mode
            </Badge>
          )}
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto scroll-thin bg-ink-50">
          <Outlet />
        </main>
      </div>
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
